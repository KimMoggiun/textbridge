/*
 * TextBridge - BLE-to-HID text injection
 * Phase 3: Protocol parsing and HID injection
 *
 * Receives keycode+modifier pairs over BLE GATT, injects them as
 * HID keystrokes via USB. Uses ACK-based flow control.
 *
 * GATT service on BT_ID_DEFAULT (identity 0) coexists with
 * ZMK's BLE profiles (identities 1-4).
 */

#include <zephyr/device.h>
#include <zephyr/init.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/settings/settings.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/conn.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/bluetooth/uuid.h>
#include <zmk/hid.h>
#include <zmk/endpoints.h>
#include <zmk/event_manager.h>
#include <zmk/events/position_state_changed.h>
#include <zmk/events/endpoint_changed.h>
#include <zmk/endpoints_types.h>

LOG_MODULE_REGISTER(textbridge, CONFIG_ZMK_LOG_LEVEL);

/* ---------- UUIDs ---------- */
#define TB_UUID(num) BT_UUID_128_ENCODE(num, 0x1234, 0x1234, 0x1234, 0x123456789abc)

static struct bt_uuid_128 tb_svc_uuid  = BT_UUID_INIT_128(TB_UUID(0x12340000));
static struct bt_uuid_128 tb_tx_uuid   = BT_UUID_INIT_128(TB_UUID(0x12340001));
static struct bt_uuid_128 tb_rx_uuid   = BT_UUID_INIT_128(TB_UUID(0x12340002));

/* ---------- Protocol constants ---------- */
/* Commands: phone -> keyboard (TX Write) */
#define TB_CMD_KEYCODE  0x01
#define TB_CMD_START    0x02
#define TB_CMD_DONE     0x03
#define TB_CMD_ABORT    0x04

/* Responses: keyboard -> phone (RX Notify) */
#define TB_RESP_ACK     0x01
#define TB_RESP_NACK    0x02
#define TB_RESP_READY   0x03
#define TB_RESP_DONE    0x04
#define TB_RESP_ERROR   0x05

/* Error codes */
#define TB_ERR_OVERFLOW 0x03
#define TB_ERR_SEQ      0x04

#define TB_MAX_KEYCODES     32
#define TB_HID_DELAY_MS     5
#define TB_TOGGLE_DELAY_MS  100
#define TB_SESSION_TIMEOUT_S 30

/* ---------- State ---------- */
static struct bt_conn *tb_conn;
static bool tb_notify_enabled;

/* Protocol state */
static bool tb_transmitting;
static bool tb_injecting;
static uint8_t tb_last_seq;

struct tb_keycode_item {
    uint8_t keycode;
    uint8_t modifier;
};

static struct tb_keycode_item tb_kc_buf[TB_MAX_KEYCODES];
static uint8_t tb_kc_count;
static uint8_t tb_current_seq;
static uint8_t tb_active_mods;

/* ---------- Forward declarations ---------- */
static ssize_t tb_tx_write_cb(struct bt_conn *conn,
                               const struct bt_gatt_attr *attr,
                               const void *buf, uint16_t len,
                               uint16_t offset, uint8_t flags);
static void tb_rx_ccc_changed(const struct bt_gatt_attr *attr, uint16_t value);
static void tb_stop_advertising(void);

/* ---------- GATT service definition ---------- */
/*
 * Attribute index:
 *   [0] Primary Service
 *   [1] TX Char Declaration
 *   [2] TX Char Value        <- Write callback
 *   [3] RX Char Declaration
 *   [4] RX Char Value        <- Notify target
 *   [5] CCC Descriptor
 */
BT_GATT_SERVICE_DEFINE(tb_svc,
    BT_GATT_PRIMARY_SERVICE(&tb_svc_uuid),
    BT_GATT_CHARACTERISTIC(&tb_tx_uuid.uuid,
                           BT_GATT_CHRC_WRITE_WITHOUT_RESP,
                           BT_GATT_PERM_WRITE,
                           NULL, tb_tx_write_cb, NULL),
    BT_GATT_CHARACTERISTIC(&tb_rx_uuid.uuid,
                           BT_GATT_CHRC_NOTIFY,
                           BT_GATT_PERM_NONE,
                           NULL, NULL, NULL),
    BT_GATT_CCC(tb_rx_ccc_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),
);

/* ---------- Notify helpers ---------- */
static void tb_send_response(uint8_t resp, uint8_t seq)
{
    if (!tb_conn || !tb_notify_enabled) {
        return;
    }
    uint8_t data[2] = { resp, seq };
    bt_gatt_notify(tb_conn, &tb_svc.attrs[4], data, sizeof(data));
}

static void tb_send_error(uint8_t seq, uint8_t err_code)
{
    if (!tb_conn || !tb_notify_enabled) {
        return;
    }
    uint8_t data[3] = { TB_RESP_ERROR, seq, err_code };
    bt_gatt_notify(tb_conn, &tb_svc.attrs[4], data, sizeof(data));
}

/* ---------- Transmission cleanup ---------- */
static void tb_cleanup_transmission(void)
{
    tb_transmitting = false;
    tb_injecting = false;
    if (tb_active_mods) {
        zmk_hid_unregister_mods(tb_active_mods);
        tb_active_mods = 0;
    }
    zmk_hid_keyboard_clear();
    zmk_endpoints_send_report(0x07);
}

/* ---------- Session timeout ---------- */
static void tb_session_timeout_handler(struct k_work *work);
K_WORK_DELAYABLE_DEFINE(tb_session_timeout_work, tb_session_timeout_handler);

static void tb_session_timeout_handler(struct k_work *work)
{
    if (tb_transmitting) {
        LOG_WRN("TB session timeout (%ds), cleaning up", TB_SESSION_TIMEOUT_S);
        tb_cleanup_transmission();
    }
}

static void tb_reset_session_timer(void)
{
    k_work_reschedule(&tb_session_timeout_work, K_SECONDS(TB_SESSION_TIMEOUT_S));
}

static void tb_cancel_session_timer(void)
{
    k_work_cancel_delayable(&tb_session_timeout_work);
}

/* ---------- HID injection work ---------- */
static void tb_inject_work_handler(struct k_work *work);
K_WORK_DEFINE(tb_inject_work, tb_inject_work_handler);

static void tb_inject_work_handler(struct k_work *work)
{
    for (int i = 0; i < tb_kc_count; i++) {
        if (!tb_injecting) {
            break; /* ABORT received */
        }

        uint8_t kc = tb_kc_buf[i].keycode;
        uint8_t mod = tb_kc_buf[i].modifier;

        /* Register modifier + press key in same report (atomic)
         * Avoids macOS interpreting lone Shift as CJK→English toggle */
        if (mod) {
            zmk_hid_register_mods(mod);
            tb_active_mods = mod;
        }
        zmk_hid_keyboard_press(kc);
        zmk_endpoints_send_report(0x07);
        k_msleep(TB_HID_DELAY_MS);

        /* Release key + modifier in same report */
        zmk_hid_keyboard_release(kc);
        if (mod) {
            zmk_hid_unregister_mods(mod);
            tb_active_mods = 0;
        }
        zmk_endpoints_send_report(0x07);

        /* Extra delay after IME toggle keys */
        if (kc == 0x90 || (kc >= 0xE0 && kc <= 0xE7) ||
            (kc == 0x2C && mod == 0x01)) {  /* Ctrl+Space */
            k_msleep(TB_TOGGLE_DELAY_MS);
        } else {
            k_msleep(TB_HID_DELAY_MS);
        }
    }

    /* Send ACK if not aborted */
    if (tb_injecting) {
        tb_injecting = false;
        tb_send_response(TB_RESP_ACK, tb_current_seq);
        tb_last_seq = tb_current_seq;
    }
}

/* ---------- TX write callback (protocol parser) ---------- */
static ssize_t tb_tx_write_cb(struct bt_conn *conn,
                               const struct bt_gatt_attr *attr,
                               const void *buf, uint16_t len,
                               uint16_t offset, uint8_t flags)
{
    /* Ensure tb_conn is set: the connected callback may filter by identity,
     * but if we're receiving GATT writes, the client is definitely connected. */
    if (!tb_conn && conn) {
        LOG_INF("TB: adopting conn from write callback");
        tb_conn = bt_conn_ref(conn);
    }

    const uint8_t *data = buf;

    if (len < 1) {
        return len;
    }

    uint8_t cmd = data[0];

    switch (cmd) {
    case TB_CMD_START: {
        if (len < 2) {
            break;
        }
        uint8_t seq = data[1];
        uint16_t total = (len >= 4) ? ((data[2] << 8) | data[3]) : 0;
        tb_transmitting = true;
        tb_last_seq = 0xFF;
        tb_reset_session_timer();
        LOG_INF("TB START seq=%d total=%d", seq, total);
        tb_send_response(TB_RESP_READY, seq);
        break;
    }

    case TB_CMD_KEYCODE: {
        if (len < 3) {
            break;
        }
        uint8_t seq = data[1];
        uint8_t count = data[2];

        if (!tb_transmitting) {
            LOG_WRN("TB KEYCODE without START");
            tb_send_error(seq, TB_ERR_SEQ);
            break;
        }

        /* Duplicate detection */
        if (seq == tb_last_seq) {
            LOG_WRN("TB duplicate seq=%d", seq);
            tb_send_response(TB_RESP_ACK, seq);
            break;
        }

        /* Busy: previous chunk still injecting */
        if (tb_injecting) {
            LOG_WRN("TB busy, NACK seq=%d", seq);
            tb_send_response(TB_RESP_NACK, seq);
            break;
        }

        /* Validate count */
        if (count > TB_MAX_KEYCODES) {
            LOG_ERR("TB overflow count=%d", count);
            tb_send_error(seq, TB_ERR_OVERFLOW);
            break;
        }

        /* Validate packet length: header(3) + count * 2 bytes */
        if (len < 3 + count * 2) {
            LOG_ERR("TB short pkt: need %d got %d", 3 + count * 2, len);
            tb_send_error(seq, TB_ERR_OVERFLOW);
            break;
        }

        /* Copy keycode pairs to buffer */
        tb_kc_count = count;
        tb_current_seq = seq;
        for (int i = 0; i < count; i++) {
            tb_kc_buf[i].keycode  = data[3 + i * 2];
            tb_kc_buf[i].modifier = data[3 + i * 2 + 1];
        }

        LOG_INF("TB KEYCODE seq=%d count=%d", seq, count);
        tb_reset_session_timer();
        tb_injecting = true;
        k_work_submit(&tb_inject_work);
        break;
    }

    case TB_CMD_DONE: {
        if (len < 2) {
            break;
        }
        uint8_t seq = data[1];
        tb_transmitting = false;
        tb_cancel_session_timer();
        LOG_INF("TB DONE seq=%d", seq);
        tb_send_response(TB_RESP_DONE, seq);
        break;
    }

    case TB_CMD_ABORT: {
        if (len < 2) {
            break;
        }
        uint8_t seq = data[1];
        LOG_INF("TB ABORT seq=%d", seq);
        tb_cancel_session_timer();
        tb_cleanup_transmission();
        tb_send_response(TB_RESP_ACK, seq);
        break;
    }

    default:
        LOG_WRN("TB unknown cmd 0x%02x", cmd);
        break;
    }

    return len;
}

/* ---------- Key blocking during transmission ---------- */
static int tb_key_listener(const zmk_event_t *eh)
{
    if (tb_transmitting || tb_injecting) {
        LOG_DBG("TB blocking key event during transmission");
        return ZMK_EV_EVENT_HANDLED;
    }
    return ZMK_EV_EVENT_BUBBLE;
}

ZMK_LISTENER(tb_key_blocker, tb_key_listener);
ZMK_SUBSCRIPTION(tb_key_blocker, zmk_position_state_changed);

/* ---------- USB mode switch detection ---------- */
static int tb_endpoint_listener(const zmk_event_t *eh)
{
    const struct zmk_endpoint_changed *ev = as_zmk_endpoint_changed(eh);
    if (ev && ev->endpoint.transport != ZMK_TRANSPORT_USB) {
        LOG_INF("TB endpoint switched away from USB, shutting down");
        tb_cancel_session_timer();
        if (tb_transmitting || tb_injecting) {
            tb_cleanup_transmission();
        }
        tb_stop_advertising();
        if (tb_conn) {
            bt_conn_disconnect(tb_conn, BT_HCI_ERR_REMOTE_USER_TERM_CONN);
        }
    }
    return ZMK_EV_EVENT_BUBBLE;
}

ZMK_LISTENER(tb_endpoint_watcher, tb_endpoint_listener);
ZMK_SUBSCRIPTION(tb_endpoint_watcher, zmk_endpoint_changed);

/* ---------- RX CCC changed ---------- */
static void tb_rx_ccc_changed(const struct bt_gatt_attr *attr, uint16_t value)
{
    tb_notify_enabled = (value == BT_GATT_CCC_NOTIFY);
    LOG_INF("RX notify %s", tb_notify_enabled ? "enabled" : "disabled");
}

/* ---------- Advertising ---------- */
#define TB_DEVICE_NAME "B6 TextBridge"
#define TB_DEVICE_NAME_LEN (sizeof(TB_DEVICE_NAME) - 1)

static const struct bt_data tb_ad[] = {
    BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),
    BT_DATA(BT_DATA_NAME_COMPLETE, TB_DEVICE_NAME, TB_DEVICE_NAME_LEN),
};

static const uint8_t tb_svc_uuid_bytes[] = {
    TB_UUID(0x12340000)
};

static const struct bt_data tb_sd[] = {
    BT_DATA(BT_DATA_UUID128_ALL, tb_svc_uuid_bytes, sizeof(tb_svc_uuid_bytes)),
};

static bool tb_advertising;

static int tb_start_advertising(void)
{
    if (tb_advertising) {
        LOG_INF("TextBridge already advertising");
        return 0;
    }

    struct bt_le_adv_param adv_param = *BT_LE_ADV_CONN;
    adv_param.id = BT_ID_DEFAULT;
    adv_param.options |= BT_LE_ADV_OPT_USE_IDENTITY;

    int err = bt_le_adv_start(&adv_param, tb_ad, ARRAY_SIZE(tb_ad),
                               tb_sd, ARRAY_SIZE(tb_sd));
    if (err) {
        LOG_ERR("TextBridge advertising failed (err %d)", err);
        return err;
    }

    tb_advertising = true;
    LOG_INF("TextBridge pairing mode - advertising as '%s'", TB_DEVICE_NAME);
    return 0;
}

static void tb_stop_advertising(void)
{
    if (!tb_advertising) {
        return;
    }
    bt_le_adv_stop();
    tb_advertising = false;
    LOG_INF("TextBridge advertising stopped");
}

/* ---------- Connection callbacks ---------- */
static void tb_connected(struct bt_conn *conn, uint8_t err)
{
    struct bt_conn_info info;

    if (err) {
        LOG_ERR("TextBridge connection failed (err %d)", err);
        return;
    }

    bt_conn_get_info(conn, &info);

    if (info.id != BT_ID_DEFAULT) {
        return;
    }

    char addr[BT_ADDR_LE_STR_LEN];
    bt_addr_le_to_str(bt_conn_get_dst(conn), addr, sizeof(addr));
    LOG_INF("TextBridge connected: %s", addr);

    tb_conn = bt_conn_ref(conn);
    tb_advertising = false;
}

static void tb_disconnected(struct bt_conn *conn, uint8_t reason)
{
    if (conn != tb_conn) {
        return;
    }

    /* Abort any in-progress transmission */
    tb_cancel_session_timer();
    if (tb_transmitting || tb_injecting) {
        tb_cleanup_transmission();
        LOG_INF("TextBridge: transmission aborted on disconnect");
    }

    char addr[BT_ADDR_LE_STR_LEN];
    bt_addr_le_to_str(bt_conn_get_dst(conn), addr, sizeof(addr));
    LOG_INF("TextBridge disconnected: %s (reason 0x%02x)", addr, reason);

    bt_conn_unref(tb_conn);
    tb_conn = NULL;
    tb_notify_enabled = false;
}

BT_CONN_CB_DEFINE(tb_conn_cb) = {
    .connected = tb_connected,
    .disconnected = tb_disconnected,
};

/* ---------- BLE enable (deferred work) ---------- */
static bool tb_ble_ready;

static void tb_bt_enable_work_handler(struct k_work *work);
K_WORK_DELAYABLE_DEFINE(tb_bt_enable_work, tb_bt_enable_work_handler);

static void tb_bt_enable_work_handler(struct k_work *work)
{
    int err = bt_enable(NULL);
    if (err == -EALREADY) {
        err = 0;
    }
    if (err) {
        LOG_ERR("TextBridge: bt_enable failed (%d)", err);
        return;
    }

    settings_subsys_init();
    settings_load_subtree("bt");

    tb_ble_ready = true;
    LOG_INF("TextBridge: BLE stack ready");
}

/* ---------- Public API ---------- */

int zmk_textbridge_pair_start(void)
{
    LOG_INF("TextBridge pair start requested");

    if (!tb_ble_ready) {
        LOG_ERR("TextBridge: BLE not ready yet");
        return -EAGAIN;
    }

    if (tb_conn) {
        LOG_INF("TextBridge already connected, ignoring");
        return 0;
    }

    return tb_start_advertising();
}

/* ---------- Initialization ---------- */
static int textbridge_init(const struct device *_arg)
{
    LOG_INF("TextBridge Phase 3 initialized");
    k_work_reschedule(&tb_bt_enable_work, K_MSEC(3000));
    return 0;
}

SYS_INIT(textbridge_init, APPLICATION, 91);
