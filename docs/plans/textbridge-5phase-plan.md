# TextBridge 5단계 개발 계획

**작성일:** 2026-02-08
**기반 문서:** [2026-02-06-textbridge-design.md](./2026-02-06-textbridge-design.md)
**방법론:** 최소 단위 MVP에서 점진적 기능 추가

---

## 단계별 의존성

```
Phase 1 (HID 주입)  ──→  Phase 2 (BLE 연결)  ──→  Phase 3 (프로토콜)
                                                         │
                                                         ↓
                         Phase 5 (한글 + 프로덕션)  ←──  Phase 4 (Flutter 앱)
```

각 단계는 이전 단계의 **성공 기준을 모두 통과한 후** 진행한다.

---

## Phase 1: HID 주입 검증 (최소 MVP)

### 1.1 목표

USB 모드에서 펌웨어가 프로그래밍 방식으로 PC에 HID 키스트로크를 주입할 수 있는지 검증한다. BLE 없이 순수 HID 경로만 테스트한다.

**핵심 가설:** `zmk_hid_keyboard_press()` → `zmk_endpoints_send_report()` → `zmk_hid_keyboard_release()` 시퀀스로 PC가 키 입력을 인식한다.

### 1.2 파일 변경

| 구분 | 파일 | 변경 내용 |
|------|------|----------|
| 신규 | `app/src/textbridge.c` | TextBridge 모듈 전체 |
| 수정 | `app/CMakeLists.txt` | `target_sources` 1줄 추가 |

### 1.3 구현 상세

#### textbridge.c 핵심 구조

```c
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zmk/hid.h>
#include <zmk/endpoints.h>

LOG_MODULE_REGISTER(textbridge, CONFIG_ZMK_LOG_LEVEL);

static void textbridge_work_handler(struct k_work *work);
K_WORK_DELAYABLE_DEFINE(textbridge_timer_work, textbridge_work_handler);

static void textbridge_work_handler(struct k_work *work) {
    // USB 모드 확인 (0 = ZMK_TRANSPORT_USB)
    extern uint8_t get_current_transport(void);
    if (get_current_transport() != 0) {
        LOG_INF("Not in USB mode, skipping");
        k_work_reschedule(&textbridge_timer_work, K_MSEC(3000));
        return;
    }

    LOG_INF("TextBridge: Injecting key '1'");

    // '1' 키 = HID keycode 0x1E
    zmk_hid_keyboard_press(0x1E);
    zmk_endpoints_send_report(0x07);  // HID_USAGE_KEY
    k_msleep(5);

    zmk_hid_keyboard_release(0x1E);
    zmk_endpoints_send_report(0x07);

    k_work_reschedule(&textbridge_timer_work, K_MSEC(3000));
}

static int textbridge_init(const struct device *dev) {
    LOG_INF("TextBridge Phase 1 initialized");
    k_work_reschedule(&textbridge_timer_work, K_MSEC(5000));  // 부팅 후 5초 대기
    return 0;
}

// priority 91 = endpoints.c(90) 이후
SYS_INIT(textbridge_init, APPLICATION, 91);
```

#### CMakeLists.txt 수정

108줄 `zephyr_cc_option` 앞에 추가:

```cmake
target_sources(app PRIVATE src/textbridge.c)
```

#### 사용하는 ZMK API

| API | 위치 | 역할 |
|-----|------|------|
| `zmk_hid_keyboard_press(keycode)` | hid.c:144 | HID 리포트 버퍼에 키코드 추가 |
| `zmk_hid_keyboard_release(keycode)` | hid.c:149 | HID 리포트 버퍼에서 키코드 제거 |
| `zmk_endpoints_send_report(usage)` | endpoints.c | 활성 endpoint로 HID 리포트 전송 |
| `get_current_transport()` | endpoints.c | 현재 transport 모드 반환 (0=USB) |

#### 설계 결정

- **5초 초기 대기:** USB enumeration + Mac HID 드라이버 준비 대기
- **3초 반복 간격:** 자동 입력과 수동 타이핑 구분 용이, 로그 확인 편리
- **work queue:** ZMK behavior 처리와 동일한 시스템 work queue 사용 → 직렬화 보장, race condition 없음

### 1.4 빌드

```bash
source ~/.zmk_env/bin/activate && \
export ZEPHYR_SDK_INSTALL_DIR=~/.zephyr-sdk-0.16.3 && \
cd ~/project/textbridge/zmk_keychron/app && \
west build --pristine -b keychron -- -DSHIELD=keychron_b6_us
```

Kconfig 변경 없음. 기존 `CONFIG_ZMK_USB=y`, `CONFIG_ZMK_LOG_LEVEL` 활용.

### 1.5 테스트

#### 플래시

```bash
python3 ~/project/textbridge/tools/enter_dfu.py && \
sleep 2 && cp build/zephyr/zmk.uf2 /Volumes/NRF52BOOT/
```

#### 시리얼 로그 확인

```bash
screen /dev/tty.usbmodem* 115200
```

예상 출력:
```
[00:00:00.345] <inf> textbridge: TextBridge Phase 1 initialized
[00:00:05.345] <inf> textbridge: TextBridge: Injecting key '1'
[00:00:08.345] <inf> textbridge: TextBridge: Injecting key '1'
```

#### HID 입력 확인

1. Mac에서 텍스트 에디터 열기
2. 3초마다 "1"이 자동 입력되는지 확인 (최소 10회)
3. 일반 타이핑 동시 테스트: `hello` 입력 시 `hel1lo` 등 3초 간격 "1" 삽입 확인

#### Transport 모드 전환 테스트

1. Fn+B (BLE 모드) 전환 → 로그에 `"Not in USB mode, skipping"` 확인
2. 텍스트 에디터에 "1" 입력 안 됨 확인
3. Fn+C (USB 모드) 복귀 → 다시 자동 입력 시작

### 1.6 성공 기준

- [ ] 빌드 에러 없이 `zmk.uf2` 생성
- [ ] USB 모드에서 3초마다 "1" 자동 입력 (10회 연속)
- [ ] BLE/2.4G 모드에서 동작 안 함
- [ ] 일반 키보드 타이핑 정상 동작
- [ ] 시리얼 로그 정상 출력

### 1.7 위험 및 완화

| 위험 | 증상 | 완화 |
|------|------|------|
| USB enumeration 미완료 | 로그는 나오지만 Mac에 입력 안됨 | 초기 대기 5→10초로 증가 |
| HID 리포트 전송 실패 | `send_report` 에러 | `zmk_usb_get_status()` 확인 추가 |
| 빌드 실패 | include 경로 에러 | `zmk/hid.h` 경로 확인 |
| DFU 진입 실패 | NRF52BOOT 마운트 안됨 | 수동 DFU (ESC+U 홀드) |

---

## Phase 2: BLE GATT 서비스 등록

### 2.1 목표

USB 모드에서 BLE 스택을 독립적으로 초기화하고, 커스텀 GATT 서비스를 등록하여 폰에서 연결할 수 있게 한다. 데이터 처리 없이 연결 자체만 검증.

**핵심 가설:**
- ZMK HOG 서비스와 충돌 없이 커스텀 GATT 서비스 등록 가능
- USB 모드에서도 BLE 라디오를 활성화하여 폰과 연결 가능
- Fn+1 키를 후킹하여 TextBridge 페어링 모드 진입 가능

### 2.2 파일 변경

| 구분 | 파일 | 변경 내용 |
|------|------|----------|
| 수정 | `app/src/ble.c` | `bt_enable()` 중복 허용 + USB 모드 페어링 훅 |
| 확장 | `app/src/textbridge.c` | BLE 초기화, GATT 서비스, 광고, 연결 콜백 |

### 2.3 구현 상세

#### ble.c 수정 1: bt_enable() 중복 호출 허용 (1209줄)

```c
// 기존:
int err = bt_enable(NULL);
if (err) { ... }

// 수정:
int err = bt_enable(NULL);
if (err && err != -EALREADY) { ... }
```

TextBridge가 USB 부팅 시 먼저 `bt_enable()` 호출 → 이후 BLE 모드 전환 시 ZMK의 `zmk_ble_init()`이 재호출해도 `-EALREADY` 무시.

#### ble.c 수정 2: USB 모드 페어링 훅 (675줄 이전)

```c
// 기존 분기 (669-678):
if(get_current_transport()==ZMK_TRANSPORT_24G) {
    if(index ==3) zmk_24g_pair();
    return 0;
}
// ===== TextBridge 훅 삽입 =====
if(get_current_transport()==ZMK_TRANSPORT_USB) {
    extern int zmk_textbridge_pair_start(void);
    return zmk_textbridge_pair_start();
}
// ==============================
if(get_current_transport()!=ZMK_TRANSPORT_BLE || (index>=3)) {
    return -ENOTSUP;
}
```

#### textbridge.c 확장: GATT 서비스

**UUID 정의:**

| 구분 | UUID |
|------|------|
| 서비스 | `12340000-1234-1234-1234-123456789abc` |
| TX (폰→키보드) | `12340001-1234-1234-1234-123456789abc` |
| RX (키보드→폰) | `12340002-1234-1234-1234-123456789abc` |

**GATT 서비스:**

```c
BT_GATT_SERVICE_DEFINE(textbridge_svc,
    BT_GATT_PRIMARY_SERVICE(BT_UUID_DECLARE_128(TB_SERVICE_UUID)),

    // TX: Write Without Response (폰 → 키보드)
    BT_GATT_CHARACTERISTIC(BT_UUID_DECLARE_128(TB_TX_CHAR_UUID),
        BT_GATT_CHRC_WRITE_WITHOUT_RESP,
        BT_GATT_PERM_WRITE_ENCRYPT,
        NULL, tb_on_receive, NULL),

    // RX: Notify (키보드 → 폰)
    BT_GATT_CHARACTERISTIC(BT_UUID_DECLARE_128(TB_RX_CHAR_UUID),
        BT_GATT_CHRC_NOTIFY, BT_GATT_PERM_NONE,
        NULL, NULL, NULL),
    BT_GATT_CCC(tb_ccc_changed,
        BT_GATT_PERM_READ_ENCRYPT | BT_GATT_PERM_WRITE_ENCRYPT),
);
```

**광고 데이터:**

```c
static const struct bt_data tb_ad[] = {
    BT_DATA_BYTES(BT_DATA_FLAGS, BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR),
    BT_DATA_BYTES(BT_DATA_UUID128_ALL, TB_SERVICE_UUID),
};
static const struct bt_data tb_sd[] = {
    BT_DATA(BT_DATA_NAME_COMPLETE, "B6 TextBridge", 14),
};
```

**페어링 시작 함수:**

```c
int zmk_textbridge_pair_start(void) {
    struct bt_le_adv_param adv_param = {
        .id = BT_ID_DEFAULT,
        .options = BT_LE_ADV_OPT_CONNECTABLE | BT_LE_ADV_OPT_USE_IDENTITY,
        .interval_min = BT_GAP_ADV_FAST_INT_MIN_2,  // 100ms
        .interval_max = BT_GAP_ADV_FAST_INT_MAX_2,  // 150ms
    };
    return bt_le_adv_start(&adv_param, tb_ad, ARRAY_SIZE(tb_ad),
                           tb_sd, ARRAY_SIZE(tb_sd));
}
```

**연결 콜백:**

```c
static struct bt_conn *tb_conn = NULL;
static bool ccc_enabled = false;

BT_CONN_CB_DEFINE(tb_conn_callbacks) = {
    .connected = tb_connected,      // tb_conn = bt_conn_ref(conn);
    .disconnected = tb_disconnected, // bt_conn_unref(); tb_conn = NULL;
};
```

#### GATT 속성 인덱스 (Notify 전송 시 참조)

```
[0] Primary Service
[1] TX Characteristic Declaration
[2] TX Characteristic Value        ← Write 콜백
[3] RX Characteristic Declaration
[4] RX Characteristic Value        ← Notify 대상
[5] CCC Descriptor                 ← Notify Enable/Disable
```

### 2.4 테스트

#### nRF Connect 앱 (iOS) 테스트 절차

1. 키보드 USB 연결 → Fn+1 홀드 (3초 이상)
2. nRF Connect SCAN → "B6 TextBridge" 검색
3. CONNECT → 연결 성공 (2-3초)
4. Services 탭에서 확인:
   - `12340000-...` (Primary Service)
   - `12340001-...` (TX - Write Without Response)
   - `12340002-...` (RX - Notify)
5. RX Characteristic → "Enable notify" 스위치 ON
6. TX Characteristic → Write: `0102030405` (Hex)
7. 시리얼 로그에서 `"TextBridge RX: 5 bytes"` + hexdump 확인
8. DISCONNECT → 연결 해제 로그 확인

#### 시리얼 로그 예상

```
[INF] textbridge: TextBridge Phase 2 initialized
[INF] textbridge: TextBridge BLE stack ready
[INF] textbridge: TextBridge pairing mode          ← Fn+1
[INF] textbridge: TextBridge advertising started
[INF] textbridge: TextBridge connected: XX:XX:XX   ← nRF Connect
[INF] textbridge: TextBridge CCC: enabled          ← Notify ON
[INF] textbridge: TextBridge RX: 5 bytes           ← Write
[INF] textbridge: TextBridge disconnected (reason 19)
```

### 2.5 성공 기준

- [ ] nRF Connect에서 "B6 TextBridge" 검색 성공
- [ ] 연결 성공 + GATT 서비스 3개 특성 표시
- [ ] Notify 활성화 성공 (CCC 로그)
- [ ] Write 데이터 수신 확인 (hexdump 로그)
- [ ] 연결/해제 로그 정상
- [ ] USB HID 일반 타이핑 정상 유지
- [ ] BLE/2.4G 모드에서 Fn+1 시 TextBridge 비활성화

### 2.6 위험 및 완화

| 위험 | 설명 | 완화 |
|------|------|------|
| HOG 서비스 충돌 | 연결 후 iOS가 HID 키보드로 인식 | 광고에 HID UUID 미포함으로 회피, 연결 후 GATT 노출은 Phase 5에서 대응 |
| BLE 메모리 부족 | HOG + TextBridge 동시 등록 | nRF52840 256KB RAM 충분, 빌드 시 메모리 경고 확인 |
| 페어링 상태 충돌 | 기존 BLE 프로필 본딩 손상 | TextBridge는 BT_ID_DEFAULT(0) 사용, ZMK 프로필은 ID 1-3 |

---

## Phase 3: BLE-to-HID 프로토콜

### 3.1 목표

BLE Write로 수신한 키코드를 파싱하여 HID 리포트로 변환, ACK 기반 흐름 제어 구현. nRF Connect에서 수동으로 바이트를 보내 Mac에 키 입력이 나타나는 전체 파이프라인을 검증.

### 3.2 프로토콜 정의

#### 명령 (폰 → 키보드, TX Characteristic Write)

| 명령 | 코드 | 포맷 | 설명 |
|------|------|------|------|
| START | `0x02` | `[02, seq, total_hi, total_lo]` | 전송 세션 시작 |
| KEYCODE | `0x01` | `[01, seq, count, kc1, mod1, kc2, mod2, ...]` | 키코드 청크 |
| DONE | `0x03` | `[03, seq]` | 전송 완료 |
| ABORT | `0x04` | `[04, seq]` | 전송 중단 |

#### 응답 (키보드 → 폰, RX Characteristic Notify)

| 응답 | 코드 | 포맷 | 설명 |
|------|------|------|------|
| ACK | `0x01` | `[01, seq]` | 청크 처리 완료 |
| NACK | `0x02` | `[02, seq]` | 재전송 요청 |
| READY | `0x03` | `[03, seq]` | 다음 청크 요청 가능 |
| DONE | `0x04` | `[04, seq]` | 전체 완료 확인 |
| ERROR | `0x05` | `[05, seq, error_code]` | 에러 발생 |

#### 키코드 쌍 포맷

```
[keycode (1 byte)] [modifier (1 byte)]

modifier 비트:
  bit 0: Left Ctrl    bit 4: Right Ctrl
  bit 1: Left Shift   bit 5: Right Shift
  bit 2: Left Alt     bit 6: Right Alt
  bit 3: Left GUI     bit 7: Right GUI
```

#### 청크 용량

- BLE 최소 MTU 23bytes → ATT 페이로드 20bytes → 앱 헤더 3bytes = **17bytes** → **8 키코드 쌍**/청크
- MTU 협상 후 최대 244bytes → **119 키코드 쌍**/청크

### 3.3 파일 변경

| 구분 | 파일 | 변경 내용 |
|------|------|----------|
| 확장 | `app/src/textbridge.c` | 프로토콜 파싱, 키코드 버퍼, HID 주입 work, ACK 전송, 중복 감지 (~265줄 추가) |

빌드 설정 변경 없음.

### 3.4 구현 상세

#### 상태 변수

```c
#define TB_CMD_KEYCODE  0x01
#define TB_CMD_START    0x02
#define TB_CMD_DONE     0x03
#define TB_CMD_ABORT    0x04

#define TB_RESP_ACK     0x01
#define TB_RESP_READY   0x03
#define TB_RESP_DONE    0x04
#define TB_RESP_ERROR   0x05

#define MAX_KEYCODES_PER_CHUNK 32
#define HID_INJECTION_DELAY_MS 5

static bool transmitting = false;
static uint8_t last_seq = 0xFF;

struct keycode_item { uint8_t keycode; uint8_t modifier; };
static struct keycode_item keycode_buffer[MAX_KEYCODES_PER_CHUNK];
static uint8_t keycode_count = 0;
static uint8_t current_seq = 0;
```

#### HID 주입 Work Handler

```c
static void inject_hid_work_handler(struct k_work *work) {
    for (int i = 0; i < keycode_count; i++) {
        uint8_t keycode = keycode_buffer[i].keycode;
        uint8_t modifier = keycode_buffer[i].modifier;

        if (modifier) {
            zmk_hid_register_mod(modifier);
            zmk_endpoints_send_report(0x07);
            k_msleep(HID_INJECTION_DELAY_MS);
        }

        zmk_hid_keyboard_press(keycode);
        zmk_endpoints_send_report(0x07);
        k_msleep(HID_INJECTION_DELAY_MS);

        zmk_hid_keyboard_release(keycode);
        zmk_endpoints_send_report(0x07);

        if (modifier) {
            k_msleep(HID_INJECTION_DELAY_MS);
            zmk_hid_unregister_mod(modifier);
            zmk_endpoints_send_report(0x07);
        }

        k_msleep(HID_INJECTION_DELAY_MS);
    }

    send_ack(current_seq);
    last_seq = current_seq;
}
```

**타이밍:** modifier 없는 키 = 10ms, modifier 있는 키 = 20ms

#### 중복 청크 감지

```c
if (cmd == TB_CMD_KEYCODE && seq == last_seq) {
    LOG_WRN("Duplicate chunk seq=%d, skip HID", seq);
    send_ack(seq);  // ACK만 재전송
    return len;
}
```

**필요 이유:** BLE Notify(ACK)는 best-effort. ACK 손실 시 폰이 재전송하면 중복 입력 방지.

#### ABORT 처리

```c
case TB_CMD_ABORT:
    transmitting = false;
    k_work_cancel_delayable(&inject_hid_work);
    zmk_hid_keyboard_clear();       // 모든 키 + modifier 해제
    zmk_endpoints_send_report(0x07);
    break;
```

### 3.5 테스트

#### nRF Connect 수동 바이트 전송

**테스트 1: 단일 키 'a'**

```
Write: 02 00 00 00     → START (seq=0)
  ← Notify: 03 00      → READY

Write: 01 01 01 04 00  → KEYCODE (seq=1, count=1, keycode=0x04, mod=0x00)
  ← Notify: 01 01      → ACK
  → Mac 화면: 'a'

Write: 03 02            → DONE (seq=2)
  ← Notify: 04 02      → DONE
```

**테스트 2: 대문자 'A' (Shift+a)**

```
Write: 02 00 00 00
Write: 01 01 01 04 02  → keycode=0x04, mod=0x02 (Shift)
  → Mac 화면: 'A'
Write: 03 02
```

**테스트 3: 여러 키 'ab'**

```
Write: 02 00 00 00
Write: 01 01 02 04 00 05 00  → count=2, 'a'(0x04), 'b'(0x05)
  → Mac 화면: 'ab'
Write: 03 02
```

**테스트 4: 중복 감지**

```
Write: 02 00 00 00
Write: 01 01 01 04 00  → 'a' (seq=1)
  ← ACK: 01 01
Write: 01 01 01 04 00  → 동일 seq=1 재전송
  ← ACK: 01 01         → ACK 재전송
  → Mac 화면: 'a' 1회만
```

**테스트 5: ABORT**

```
Write: 02 00 00 00
Write: 01 01 05 04 00 05 00 06 00 07 00 08 00  → 'abcde'
Write: 04 02            → ABORT (전송 중 즉시)
  → Mac 화면: 일부만 입력 (예: 'abc')
  → 키보드 일반 타이핑 정상 복구
```

#### HID 키코드 참조

| 문자 | HID keycode | modifier |
|------|-------------|----------|
| a-z | 0x04-0x1D | 0x00 |
| A-Z | 0x04-0x1D | 0x02 (Shift) |
| 1-9 | 0x1E-0x26 | 0x00 |
| 0 | 0x27 | 0x00 |
| Space | 0x2C | 0x00 |
| Enter | 0x28 | 0x00 |
| ! | 0x1E | 0x02 |
| @ | 0x1F | 0x02 |

### 3.6 성공 기준

- [ ] nRF Connect에서 'a' 전송 → Mac에 'a' 입력
- [ ] Shift+'a' → 'A' 입력 (modifier 정상)
- [ ] 여러 키 순서 유지 ('hello' 순서대로)
- [ ] ACK/READY/DONE Notify 정상 수신
- [ ] 중복 청크 감지 → 1회만 입력
- [ ] ABORT → 즉시 중단 + 키보드 복구
- [ ] USB HID 일반 타이핑 정상

### 3.7 위험 및 완화

| 위험 | 완화 |
|------|------|
| BLE Notify 손실 → 무한 대기 | Phase 5에서 30초 타임아웃 추가. Phase 3에서는 연결 끊기로 복구 |
| modifier 누적 (unregister 누락) | ABORT/연결해제 시 `zmk_hid_keyboard_clear()` 호출 |
| 버퍼 오버플로우 | `count > MAX_KEYCODES_PER_CHUNK` 검증 + 패킷 길이 검증 |
| USB 모드 이탈 중 HID 주입 | 주입 시작 전 `get_current_transport()` 확인 |

---

## Phase 4: Flutter 모바일 앱

### 4.1 목표

실제 사용 가능한 모바일 앱. 텍스트를 입력하면 키코드로 변환하여 BLE로 전송하고, PC에 타이핑으로 나타나게 한다.

### 4.2 화면 흐름

```
[BLE 스캔 화면]  →  [메인 화면]  →  [설정 화면]
  - 장치 검색         - 연결 상태      - 타이핑 속도
  - 연결 버튼         - OS 선택        - 재전송 횟수
                      - 텍스트 입력
                      - 전송/중지 버튼
                      - 진행률 바
```

### 4.3 프로젝트 구조

```
textbridge_app/
├── lib/
│   ├── main.dart
│   ├── models/
│   │   └── textbridge_protocol.dart   # 프로토콜 상수, KeycodePair, KeycodeChunk
│   ├── services/
│   │   ├── ble_service.dart           # BLE 스캔/연결/Write/Notify
│   │   ├── keycode_service.dart       # 텍스트→키코드 변환, 청킹
│   │   └── transmission_service.dart  # 전송 로직, ACK 대기, 재전송
│   ├── screens/
│   │   ├── scan_screen.dart
│   │   ├── home_screen.dart
│   │   └── settings_screen.dart
│   └── widgets/
│       ├── connection_status_widget.dart
│       └── progress_indicator_widget.dart
├── test/
│   └── keycode_service_test.dart
└── pubspec.yaml
```

### 4.4 핵심 의존성

```yaml
dependencies:
  flutter_blue_plus: ^1.32.0   # BLE 통신
  provider: ^6.1.0              # 상태 관리
  permission_handler: ^11.0.0   # Bluetooth 권한
```

### 4.5 BLE 통신

#### 스캔

```dart
FlutterBluePlus.startScan(
  timeout: Duration(seconds: 10),
  withServices: [Guid("12340000-1234-1234-1234-123456789abc")],
);
```

#### 연결 + 서비스 탐색

```dart
await device.connect(timeout: Duration(seconds: 15));
List<BluetoothService> services = await device.discoverServices();
// TX Characteristic (12340001-...) → Write Without Response
// RX Characteristic (12340002-...) → Notify 활성화
```

#### MTU 협상

```dart
try {
  int mtu = await device.requestMtu(244);
  chunkSize = (mtu - 3 - 3) ~/ 2;  // 최대 키코드 쌍 수
} catch (e) {
  chunkSize = 8;  // 기본값
}
```

### 4.6 텍스트→키코드 변환

#### ASCII 매핑

```dart
static final Map<int, KeycodePair> asciiMap = {
  // 소문자 a-z
  0x61: KeycodePair(0x04, 0x00), // a
  0x62: KeycodePair(0x05, 0x00), // b
  // ...
  0x7A: KeycodePair(0x1D, 0x00), // z

  // 대문자 A-Z (Shift)
  0x41: KeycodePair(0x04, 0x02), // A
  // ...

  // 숫자
  0x31: KeycodePair(0x1E, 0x00), // 1
  0x30: KeycodePair(0x27, 0x00), // 0

  // 특수문자
  0x20: KeycodePair(0x2C, 0x00), // Space
  0x0A: KeycodePair(0x28, 0x00), // Enter
  0x21: KeycodePair(0x1E, 0x02), // !
  0x40: KeycodePair(0x1F, 0x02), // @
  // ... (전체 ASCII 테이블)
};
```

#### 청킹 알고리즘

```dart
List<KeycodeChunk> createChunks(List<KeycodePair> keycodes, {int chunkSize = 8}) {
  List<KeycodeChunk> chunks = [];
  int seq = 1;
  for (int i = 0; i < keycodes.length; i += chunkSize) {
    int end = min(i + chunkSize, keycodes.length);
    chunks.add(KeycodeChunk(sequence: seq, keycodes: keycodes.sublist(i, end)));
    seq = (seq + 1) % 256;
  }
  return chunks;
}
```

### 4.7 전송 흐름 제어

```dart
Future<TransmissionResult> transmit(String text, TargetOS os) async {
  List<KeycodePair> keycodes = keycodeService.textToKeycodes(text, os);
  List<KeycodeChunk> chunks = keycodeService.createChunks(keycodes);

  // 1. START
  await bleService.write([0x02, 0x00, chunks.length >> 8, chunks.length & 0xFF]);
  await waitForResponse(0x03, timeout: 5s);  // READY

  // 2. 청크 전송 (ACK 대기)
  for (var chunk in chunks) {
    await sendChunkWithRetry(chunk, maxRetries: 3, ackTimeout: 5s);
    onProgress(chunk.sequence / chunks.length);
  }

  // 3. DONE
  await bleService.write([0x03, 0xFF]);
  await waitForResponse(0x04, timeout: 5s);  // DONE
}
```

**재전송:** ACK 타임아웃 5초 → 100ms 대기 → 재전송. 최대 3회 실패 시 에러.

### 4.8 UI

- **연결 상태:** 초록/빨강 배지 + 장치명
- **OS 선택:** macOS / Windows 드롭다운
- **텍스트 입력:** 멀티라인 TextField (코드 입력 가능, monospace 폰트)
- **통계:** 글자 수, 예상 시간
- **진행률:** LinearProgressIndicator + 퍼센트
- **전송/중지:** 전송 중에는 빨간 "중지" 버튼 표시

### 4.9 테스트

#### 단위 테스트

```dart
test('ASCII lowercase', () {
  var result = service.textToKeycodes('abc', TargetOS.macOS);
  expect(result[0].keycode, 0x04);
  expect(result[0].modifier, 0x00);
});

test('Chunking', () {
  var keycodes = List.generate(20, (i) => KeycodePair(0x04 + i, 0x00));
  var chunks = service.createChunks(keycodes, chunkSize: 8);
  expect(chunks.length, 3);  // 8 + 8 + 4
});
```

#### End-to-End 테스트 시나리오

| # | 입력 | 검증 |
|---|------|------|
| 1 | `hello world` | Mac에 정확히 입력, 진행률 100% |
| 2 | Python 코드 (들여쓰기, 따옴표, 괄호) | 코드 실행 가능할 정도로 정확 |
| 3 | 1000자 텍스트 | 에러 없이 완료 |
| 4 | 전송 중 "중지" 클릭 | 즉시 중단, 키보드 복구 |
| 5 | BLE 연결 끊김 | 에러 표시 + 재연결 버튼 |

### 4.10 성공 기준

- [ ] BLE 연결 성공률 95% 이상
- [ ] ASCII 텍스트 정확도 100%
- [ ] 1000자 에러 없이 완료
- [ ] 진행률 표시 동작
- [ ] 전송 중지 정상
- [ ] ACK 재전송 동작 (최대 3회)

### 4.11 위험 및 완화

| 위험 | 완화 |
|------|------|
| MTU 협상 실패 → 느린 전송 | 기본 8쌍/청크 (보수적), 협상 성공 시 자동 증가 |
| iOS 백그라운드 BLE 끊김 | 포그라운드에서만 전송 허용 |
| ACK Notify 손실 → 무한 대기 | 5초 타임아웃 + 3회 재시도 |

---

## Phase 5: 한국어 지원 + 프로덕션

### 5.1 목표

한글 텍스트 지원, 프로덕션 안정성 (타임아웃, 에러 복구), 보안 강화 (본딩 전용 연결).

### 5.2 한글 유니코드 분해

한글 완성형 (U+AC00 "가" ~ U+D7A3 "힣") 분해 공식:

```
code = unicode - 0xAC00
초성 = code / (21 × 28)           // 인덱스 0~18
중성 = (code % (21 × 28)) / 28     // 인덱스 0~20
종성 = code % 28                    // 인덱스 0~27 (0=없음)
```

**예시: "한" (U+D55C)**
```
code = 0xD55C - 0xAC00 = 11100
초성 = 11100 / 588 = 18 → ㅎ
중성 = (11100 % 588) / 28 = 18 → ㅏ
종성 = 11100 % 28 = 12 → ㄴ
```

### 5.3 두벌식 키 매핑 테이블

#### 초성 (19개)

| # | 자모 | 키 | HID | mod |
|---|------|-----|-----|-----|
| 0 | ㄱ | r | 0x15 | 0x00 |
| 1 | ㄲ | R | 0x15 | 0x02 |
| 2 | ㄴ | s | 0x16 | 0x00 |
| 3 | ㄷ | e | 0x08 | 0x00 |
| 4 | ㄸ | E | 0x08 | 0x02 |
| 5 | ㄹ | f | 0x09 | 0x00 |
| 6 | ㅁ | a | 0x04 | 0x00 |
| 7 | ㅂ | q | 0x14 | 0x00 |
| 8 | ㅃ | Q | 0x14 | 0x02 |
| 9 | ㅅ | t | 0x17 | 0x00 |
| 10 | ㅆ | T | 0x17 | 0x02 |
| 11 | ㅇ | d | 0x07 | 0x00 |
| 12 | ㅈ | w | 0x1A | 0x00 |
| 13 | ㅉ | W | 0x1A | 0x02 |
| 14 | ㅊ | c | 0x06 | 0x00 |
| 15 | ㅋ | z | 0x1D | 0x00 |
| 16 | ㅌ | x | 0x1B | 0x00 |
| 17 | ㅍ | v | 0x19 | 0x00 |
| 18 | ㅎ | g | 0x0A | 0x00 |

#### 중성 (21개)

단일 모음 (1타):

| # | 자모 | 키 | HID |
|---|------|-----|-----|
| 0 | ㅏ | k | 0x0E |
| 2 | ㅑ | i | 0x0C |
| 4 | ㅓ | j | 0x0D |
| 6 | ㅕ | u | 0x18 |
| 8 | ㅗ | h | 0x0B |
| 12 | ㅛ | y | 0x1C |
| 13 | ㅜ | n | 0x11 |
| 17 | ㅠ | b | 0x05 |
| 18 | ㅡ | m | 0x10 |
| 20 | ㅣ | l | 0x0F |

복합 모음 (2~3타):

| # | 자모 | 조합 | 키 시퀀스 |
|---|------|------|----------|
| 1 | ㅐ | ㅏ+ㅣ | k, l |
| 3 | ㅒ | ㅑ+ㅣ | i, l |
| 5 | ㅔ | ㅓ+ㅣ | j, l |
| 7 | ㅖ | ㅕ+ㅣ | u, l |
| 9 | ㅘ | ㅗ+ㅏ | h, k |
| 10 | ㅙ | ㅗ+ㅐ | h, k, l |
| 11 | ㅚ | ㅗ+ㅣ | h, l |
| 14 | ㅝ | ㅜ+ㅓ | n, j |
| 15 | ㅞ | ㅜ+ㅔ | n, j, l |
| 16 | ㅟ | ㅜ+ㅣ | n, l |
| 19 | ㅢ | ㅡ+ㅣ | m, l |

#### 종성 (27개, 0=없음 제외)

단일 자음 (16개): 초성과 동일 매핑

겹받침 (11개, 2타):

| # | 자모 | 분해 | 키 시퀀스 |
|---|------|------|----------|
| 3 | ㄳ | ㄱ+ㅅ | r, t |
| 5 | ㄵ | ㄴ+ㅈ | s, w |
| 6 | ㄶ | ㄴ+ㅎ | s, g |
| 9 | ㄺ | ㄹ+ㄱ | f, r |
| 10 | ㄻ | ㄹ+ㅁ | f, a |
| 11 | ㄼ | ㄹ+ㅂ | f, q |
| 12 | ㄽ | ㄹ+ㅅ | f, t |
| 13 | ㄾ | ㄹ+ㅌ | f, x |
| 14 | ㄿ | ㄹ+ㅍ | f, v |
| 15 | ㅀ | ㄹ+ㅎ | f, g |
| 18 | ㅄ | ㅂ+ㅅ | q, t |

### 5.4 IME 전환 로직

#### 한/영 전환 키

| OS | 키 | HID keycode |
|----|----|-------------|
| Windows | 한/영 (Lang1) | 0x90 |
| macOS | Right Command | 0xE7 |

#### 전환 삽입 규칙

텍스트를 순회하며 IME 상태를 추적. 한글↔영문 경계에서 전환 키 삽입:

```
"hello안녕world"
→ h,e,l,l,o, [한/영], ㅇ,ㅏ,ㄴ,ㄴ,ㅕ,ㅇ, [한/영], w,o,r,l,d
```

전송 완료 후 마지막이 한글이면 영문 모드 복귀를 위해 한/영 키 1회 추가.

### 5.5 프로덕션 강화 (펌웨어)

#### 전송 타임아웃 (30초)

```c
#define TRANSMISSION_TIMEOUT_MS 30000

K_WORK_DELAYABLE_DEFINE(transmission_timeout_work, transmission_timeout_handler);

// CMD_START/CMD_KEYCODE 수신 시 타이머 리셋
k_work_reschedule(&transmission_timeout_work, K_MSEC(TRANSMISSION_TIMEOUT_MS));

// CMD_DONE 수신 시 타이머 취소
k_work_cancel_delayable(&transmission_timeout_work);

// 타임아웃 시:
static void transmission_timeout_handler(struct k_work *work) {
    transmitting = false;
    zmk_hid_keyboard_clear();
    zmk_endpoints_send_report(0x07);
    // ERROR Notify (error_code=0x01 timeout)
}
```

#### USB 모드 이탈 감지

```c
#include <zmk/event_manager.h>
#include <zmk/events/endpoint_changed.h>

static int textbridge_endpoint_listener(const zmk_event_t *eh) {
    if (get_current_transport() != ZMK_TRANSPORT_USB) {
        // 전송 중단, HID 클리어, BLE 연결 끊기, 광고 중지
    }
    return 0;
}

ZMK_LISTENER(textbridge, textbridge_endpoint_listener);
ZMK_SUBSCRIPTION(textbridge, zmk_endpoint_changed);
```

#### 본딩 전용 광고

```c
// 부팅 시 (USB 모드): 2초 후 자동 광고 시작
// 본딩된 기기 있으면: Filter Accept List 활성화 → 타인 연결 차단
// 본딩 없으면: 필터 없이 광고 (첫 페어링 허용)

// Fn+1 홀드 (3초): 페어링 모드 → 필터 없이 광고 (새 기기 연결)
// Fn+1 탭: 재연결 → 필터 있이 광고 (본딩 기기만)
```

#### 에러 코드

| 코드 | 의미 |
|------|------|
| 0x01 | 전송 타임아웃 |
| 0x02 | USB 모드 아님 |
| 0x03 | 버퍼 오버플로우 |
| 0x04 | 시퀀스 오류 |
| 0x05 | HID 주입 실패 |

### 5.6 테스트

#### 한글 테스트

| # | 입력 | 검증 |
|---|------|------|
| 1 | "안녕하세요" | 5음절 정확 출력 |
| 2 | "까짝" | 쌍자음 Shift 정상 |
| 3 | "왜웨의" | 3타 복합 모음 정상 |
| 4 | "값삯" | 겹받침 2타 분해 정상 |
| 5 | "hello안녕world" | 한/영 전환 2회 |
| 6 | 5000자 한글 문서 | 에러율 0% |
| 7 | "변수명: userName123" | 혼용 + 특수문자 |

#### 프로덕션 안정성 테스트

| # | 시나리오 | 예상 동작 |
|---|---------|----------|
| 1 | 전송 중 USB 뽑기 | 즉시 중단, BLE 해제, 로그 출력 |
| 2 | 전송 중 앱 강제 종료 | 30초 후 타임아웃, 키보드 복구 |
| 3 | 타인 폰 연결 시도 | Accept List 필터로 차단 |
| 4 | Fn+1 홀드 (3초) | 새 기기 페어링 모드 |
| 5 | 키보드 재부팅 (USB) | 본딩 기기 자동 광고 |

### 5.7 성공 기준

#### 기능

- [ ] 11,172개 한글 음절 분해 정확도 100% (단위 테스트)
- [ ] 쌍자음 5개, 복합 모음 11개, 겹받침 11개 정상
- [ ] 한/영 전환 정확도 100%
- [ ] 10,000자 한영 혼용 전송 에러율 0%

#### 안정성

- [ ] 타임아웃 30초 후 자동 복구
- [ ] USB 이탈 100ms 이내 감지
- [ ] 에러 발생 후 키보드 정상 복구율 100%

#### 보안

- [ ] 본딩 전용 광고: 타인 연결 0건
- [ ] GATT 암호화 강제 (Write/CCC)

#### 성능

- [ ] 기본 5ms → ~150 chars/sec
- [ ] 최대 1ms → ~400 chars/sec
- [ ] 5000자 한글 전송 < 120초

### 5.8 위험 및 완화

| 위험 | 완화 |
|------|------|
| Windows/macOS IME 상태 불일치 | Windows 우선 지원, macOS는 "IME 초기화" 옵션 |
| 한글 자모 분해 버그 | 11,172개 전수 단위 테스트 |
| 타이핑 속도 과다 → PC 버퍼 오버플로우 | 기본 5ms, 1ms 선택 시 경고 표시 |
| 본딩 정보 손실 (펌웨어 업데이트) | `CONFIG_BT_SETTINGS=y` 영구 저장소 사용 |

---

## 부록 A: 빌드 & 테스트 도구

### 빌드 명령어

```bash
source ~/.zmk_env/bin/activate && \
export ZEPHYR_SDK_INSTALL_DIR=~/.zephyr-sdk-0.16.3 && \
cd ~/project/textbridge/zmk_keychron/app && \
west build --pristine -b keychron -- -DSHIELD=keychron_b6_us
```

### 플래시 명령어

```bash
python3 ~/project/textbridge/tools/enter_dfu.py && \
sleep 2 && cp build/zephyr/zmk.uf2 /Volumes/NRF52BOOT/
```

### 시리얼 모니터

```bash
screen /dev/tty.usbmodem* 115200
```

### Flutter 앱 실행

```bash
cd ~/project/textbridge/textbridge_app && \
flutter pub get && flutter run
```

---

## 부록 B: 전체 파일 변경 요약

| Phase | 파일 | 변경 | 코드량 |
|-------|------|------|--------|
| 1 | `app/src/textbridge.c` | 신규 | ~65줄 |
| 1 | `app/CMakeLists.txt` | +1줄 | |
| 2 | `app/src/ble.c` | +10줄 | bt_enable + 페어링 훅 |
| 2 | `app/src/textbridge.c` | 확장 | ~310줄 |
| 3 | `app/src/textbridge.c` | 확장 | ~575줄 |
| 4 | `textbridge_app/` | 신규 Flutter 프로젝트 | ~2000줄 |
| 5 | `app/src/textbridge.c` | 확장 | ~750줄 |
| 5 | `textbridge_app/` | 확장 | ~3000줄 |

---

## 부록 C: 전송 시간 계산

| 텍스트 | 글자 수 | 키 수 | 시간 (5ms) | 시간 (1ms) |
|--------|---------|-------|-----------|-----------|
| "hello world" | 11 | 11 | 0.11초 | 0.02초 |
| 1000자 영문 | 1000 | ~1200 | 12초 | 2.4초 |
| 1000자 한글 | 1000 | ~3010 | 30초 | 6초 |
| 5000자 혼용 | 5000 | ~7850 | 78초 | 16초 |
