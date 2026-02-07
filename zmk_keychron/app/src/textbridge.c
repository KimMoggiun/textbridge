/*
 * TextBridge - BLE-to-USB HID text injection module
 * Phase 1: HID injection proof-of-concept
 *
 * Auto-types '1' every 3 seconds in USB mode to validate the HID injection path.
 */

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zmk/hid.h>
#include <zmk/endpoints.h>
#include <dt-bindings/zmk/hid_usage_pages.h>

LOG_MODULE_REGISTER(textbridge, CONFIG_ZMK_LOG_LEVEL);

/* HID keycode for '1' key */
#define HID_KEY_1 0x1E

extern uint8_t get_current_transport(void);

static void textbridge_work_handler(struct k_work *work);
K_WORK_DELAYABLE_DEFINE(textbridge_timer_work, textbridge_work_handler);

static void textbridge_work_handler(struct k_work *work) {
    /* Only inject in USB mode (transport 0) */
    if (get_current_transport() != 0) {
        k_work_reschedule(&textbridge_timer_work, K_MSEC(3000));
        return;
    }

    LOG_INF("TextBridge: Injecting key '1'");

    zmk_hid_keyboard_press(HID_KEY_1);
    zmk_endpoints_send_report(HID_USAGE_KEY);
    k_msleep(5);

    zmk_hid_keyboard_release(HID_KEY_1);
    zmk_endpoints_send_report(HID_USAGE_KEY);

    k_work_reschedule(&textbridge_timer_work, K_MSEC(3000));
}

static int textbridge_init(const struct device *_arg) {
    LOG_INF("TextBridge Phase 1 initialized - will inject '1' every 3s in USB mode");
    k_work_reschedule(&textbridge_timer_work, K_MSEC(5000));
    return 0;
}

SYS_INIT(textbridge_init, APPLICATION, 91);
