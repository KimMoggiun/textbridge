# TextBridge 설계 문서

**작성일:** 2026-02-06
**최종 수정:** 2026-02-07
**목적:** 폐쇄망 회사 PC에 휴대폰에서 텍스트 전송 (프로그래밍 소스 코드)

---

## 1. 전체 아키텍처

```
┌─────────────┐     BLE      ┌─────────────┐     USB
│  Flutter 앱  │ ──────────→ │   B6 Pro    │ ──────────→  회사 PC
│  (iOS/Andr) │  TextBridge  │  (nRF52840) │    (유선)
└─────────────┘   GATT 서비스  └─────────────┘
      │                            │
   텍스트 입력              키코드→HID 변환
   키코드 변환                 ACK 응답
   청크 전송
   재전송 처리
```

### 연결 구성

| 연결 | 방식 | 비고 |
|---|---|---|
| **회사 PC** | USB 유선 | 1000Hz 폴링, 안정적 |
| **휴대폰** | BLE | TextBridge 커스텀 GATT 서비스 |

### 연결 제약 사항

nRF52840은 라디오가 1개이며, BLE와 2.4GHz ESB가 같은 라디오를 사용한다.
키크론 펌웨어는 MPSL(Multiprotocol Service Layer) 미사용, ESB는 프리컴파일 바이너리.

| PC 연결 | 라디오 상태 | 폰 BLE 연결 | TextBridge |
|---|---|---|---|
| **USB (유선)** | **미사용** | **가능** | **지원** |
| BLE | BLE 사용 중 | - | **미지원** |
| 2.4GHz 동글 | ESB 독점 | **불가** | **미지원** |

> **설계 결정:** TextBridge는 USB 모드 전용.
> BLE 모드: ZMK BLE 프로필 관리와 충돌 → 미지원.
> 2.4GHz 모드: ESB가 라디오 독점 → 미지원.

---

## 2. 전체 라이프사이클

```
① 최초 페어링  Fn+1 → TextBridge 페어링 모드 → 폰과 본딩 (1회)
                                                    ↓
② 자동 연결    USB 부팅 → BLE 자동 광고 (본딩된 폰 전용) → 폰 연결
                                                    ↓
③ 텍스트 전송  폰: 키코드 Write → 키보드: HID 주입 → 키보드: ACK Notify
               반복 (청크 단위)
                                                    ↓
④ 완료         폰: 완료 신호 → 키보드: DONE 응답 → 대기 상태 복귀
```

### 보안: BLE 본딩

- 최초 1회: Fn+1로 페어링 모드 진입 → 폰과 본딩
- 이후: `CONFIG_BT_FILTER_ACCEPT_LIST=y` → 본딩된 폰만 자동 연결 허용
- 타인 연결 불가 (본딩되지 않은 기기 차단)
- 재페어링: Fn+1로 새 기기 등록 (기존 본딩 교체)

---

## 3. 프로젝트 구조

```
textbridge/
├── docs/plans/
│   └── 2026-02-06-textbridge-design.md
├── tools/
│   └── enter_dfu.py               ← PC에서 DFU 모드 진입
├── zmk_keychron/                   ← Keychron ZMK 펌웨어 전체 소스
│   ├── app/
│   │   ├── src/
│   │   │   ├── ble.c              ← BLE 연결 관리 (수정: 수 줄)
│   │   │   ├── behaviors/         ← 변경 없음
│   │   │   ├── textbridge.c       ← [신규] TextBridge 모듈
│   │   │   ├── hid.c, endpoints.c, hog.c  ← 변경 없음
│   │   │   └── 24G/               ← 2.4GHz ESB (변경 없음)
│   │   ├── boards/                ← 보드 정의, 키맵 (변경 없음)
│   │   └── CMakeLists.txt         ← 빌드 설정 (수정: 1줄)
│   ├── zephyr/                    ← .gitignore (빌드 의존성)
│   └── modules/                   ← .gitignore (빌드 의존성)
├── .gitignore
└── README.md
```

---

## 4. ZMK 펌웨어 변경 상세

### 4.1 신규 파일: textbridge.c

TextBridge 전체 기능을 담당하는 단일 모듈:
- BLE 스택 초기화 (`bt_enable`)
- 커스텀 GATT 서비스 등록
- BLE 광고 관리 (페어링 모드 / 본딩 기기 전용)
- 키코드 수신 → HID 순차 주입
- ACK/상태 Notify

### 4.2 수정: ble.c (수 줄)

**변경 1: `bt_enable()` 중복 호출 허용 (line 1209)**

```c
// 기존:
int err = bt_enable(NULL);
if (err) {

// 수정:
int err = bt_enable(NULL);
if (err && err != -EALREADY) {
```

TextBridge가 먼저 `bt_enable()`을 호출해도 이후 BLE 모드 전환 시 정상 동작.

> **부팅 순서 주의:** USB 모드에서 ZMK은 `bt_enable()`을 호출하지 않을 수 있다.
> TextBridge는 자체적으로 `bt_enable()`을 호출하여 BLE 스택을 초기화한다.
> Phase 1 PoC에서 USB 모드 부팅 시 `bt_enable()` 호출 여부를 확인할 것.

**변경 2: USB 모드 TextBridge 페어링 훅 (`zmk_ble_prof_pair_start()`, line 675 이전)**

```c
// 기존 코드 (ble.c:669-678):
if(get_current_transport()==ZMK_TRANSPORT_24G) {
    if(index == 3) zmk_24g_pair();
    return 0;
}
// ===== TextBridge 훅 삽입 =====
if(get_current_transport()==ZMK_TRANSPORT_USB) {
    return zmk_textbridge_pair_start();
}
// ==============================
if(get_current_transport()!=ZMK_TRANSPORT_BLE || (index>=3)) {
    return -ENOTSUP;
}
```

기존 transport 디스패치 패턴(24G → `zmk_24g_pair()`)과 동일한 방식.
USB 모드에서 Fn+1 → TextBridge 페어링. BLE/2.4G → 기존 동작 그대로.

> **behavior_bt.c는 변경하지 않는다.**
> behavior_bt.c는 transport 인식 없는 순수 디스패처이며,
> `zmk_ble_prof_pair_start()`에 이미 transport별 분기가 존재한다.

### 4.3 수정: CMakeLists.txt (1줄)

```cmake
target_sources(app PRIVATE src/textbridge.c)
```

---

## 5. HID 키 입력 경로

### 코드 경로 (분석 완료)

```
zmk_hid_keyboard_press(keycode)           ← hid.c: 리포트에 키 추가
    ↓
zmk_endpoints_send_report(HID_USAGE_KEY)  ← endpoints.c: USB로 전송
    ↓
zmk_hid_keyboard_release(keycode)
    ↓
zmk_endpoints_send_report(HID_USAGE_KEY)
```

### 핵심 API

```c
int zmk_hid_keyboard_press(zmk_key_t code);          // 0x04 = A
int zmk_hid_keyboard_release(zmk_key_t code);
int zmk_hid_register_mod(zmk_mod_t modifier);        // Shift, Ctrl 등
int zmk_hid_unregister_mod(zmk_mod_t modifier);
int zmk_endpoints_send_report(uint16_t usage_page);   // HID_USAGE_KEY
uint8_t get_current_transport(void);                   // 현재 모드 확인
```

### 동시성

- TextBridge HID 주입과 ZMK 키맵 처리 모두 시스템 work queue 사용
- 같은 work queue → 직렬화 → 경쟁 조건 없음

---

## 6. BLE 커스텀 GATT 서비스

### UUID

```
서비스:         TB_SERVICE_UUID      (커스텀 128-bit)
TX (Write):    TB_TX_CHAR_UUID      (폰 → 키보드)
RX (Notify):   TB_RX_CHAR_UUID      (키보드 → 폰)
```

### 서비스 등록 (BT_GATT_SERVICE_DEFINE)

```c
BT_GATT_SERVICE_DEFINE(textbridge_svc,
    BT_GATT_PRIMARY_SERVICE(BT_UUID_DECLARE_128(TB_SERVICE_UUID)),

    // TX: 폰 → 키보드 (Write Without Response)
    BT_GATT_CHARACTERISTIC(BT_UUID_DECLARE_128(TB_TX_CHAR_UUID),
        BT_GATT_CHRC_WRITE_WITHOUT_RESP,
        BT_GATT_PERM_WRITE_ENCRYPT,
        NULL, tb_on_receive, NULL),

    // RX: 키보드 → 폰 (Notify)
    BT_GATT_CHARACTERISTIC(BT_UUID_DECLARE_128(TB_RX_CHAR_UUID),
        BT_GATT_CHRC_NOTIFY,
        BT_GATT_PERM_NONE,
        NULL, NULL, NULL),
    BT_GATT_CCC(tb_ccc_changed,
        BT_GATT_PERM_READ_ENCRYPT | BT_GATT_PERM_WRITE_ENCRYPT),
);
```

### BLE 광고

```c
// USB 모드 부팅 시 자동 광고 (본딩된 기기 전용)
static const struct bt_data ad[] = {
    BT_DATA_BYTES(BT_DATA_FLAGS, BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR),
    BT_DATA_BYTES(BT_DATA_UUID128_ALL, TB_SERVICE_UUID),
};
static const struct bt_data sd[] = {
    BT_DATA(BT_DATA_NAME_COMPLETE, "B6 TextBridge", 13),
};
```

### HID 서비스 격리

TextBridge BLE 광고는 ZMK의 기존 BLE HID 서비스(HOG)와 독립적으로 동작해야 한다.
USB 모드에서는 ZMK이 BLE 광고를 하지 않으므로 TextBridge만 광고하면 충돌 없음.

- TextBridge 광고 데이터에 커스텀 UUID만 포함 (HID UUID 미포함)
- 폰이 키보드로 인식하지 않음 (HID 서비스 미노출)

### 본딩 전용 광고 (Filter Accept List)

ZMK에 이미 `CONFIG_BT_FILTER_ACCEPT_LIST=y`가 활성화되어 있고,
`setup_accept_list()` + `BT_LE_ADV_OPT_FILTER_SCAN_REQ | FILTER_CONN` 패턴이 구현되어 있다.
TextBridge도 동일한 Zephyr API를 사용:

```c
// 본딩 기기 전용 광고 파라미터
adv_param.options |= BT_LE_ADV_OPT_FILTER_SCAN_REQ;
adv_param.options |= BT_LE_ADV_OPT_FILTER_CONN;
```

### USB 모드 벗어날 때 동작

TextBridge는 USB 모드 전용. USB 모드를 벗어나면 즉시 중지:

- ZMK `zmk_endpoint_changed` 이벤트 구독 (ZMK_LISTENER)
- USB → BLE/2.4G 전환 감지 시:
  1. 진행 중인 전송 즉시 중단
  2. HID 리포트 클리어 (`zmk_hid_keyboard_clear()` + `send_report()`)
  3. BLE 연결 끊기 (`bt_conn_disconnect()`)
  4. BLE 광고 중지 (`bt_le_adv_stop()`)
  5. 대기 상태로 복귀
- USB 모드로 돌아오면 자동으로 BLE 광고 재시작 (본딩된 폰 전용)

---

## 7. 통신 프로토콜

### TX 데이터 포맷 (폰 → 키보드)

```
[0]    명령 타입
[1]    시퀀스 번호
[2..N] 페이로드

명령 타입:
  0x01 = 키코드 데이터
  0x02 = 전송 시작 (총 청크 수 포함)
  0x03 = 전송 완료
  0x04 = 전송 중지
```

### 키코드 데이터 청크 (명령 0x01)

```
[0]    0x01
[1]    시퀀스 번호
[2]    키코드 개수 (N)
[3]    keycode_1
[4]    modifier_1
[5]    keycode_2
[6]    modifier_2
...
[3+2N-1] 마지막 modifier

BLE MTU 기본 23bytes → 헤더 3bytes → 페이로드 20bytes → 키코드 10개/청크
MTU 협상 후 최대 244bytes → 키코드 ~120개/청크
```

### 앱-펌웨어 역할 분리

앱은 **(keycode, modifier) 쌍**을 전송하고, 펌웨어가 **HID press/release 시퀀스**를 실행한다.

| 역할 | 앱 (Flutter) | 펌웨어 (textbridge.c) |
|---|---|---|
| 문자 분해 | "왂" → ㅇ, ㅗ, ㅏ, ㄲ | - |
| 키코드 변환 | ㄲ → (R, Shift) | - |
| 청크 패킹 | (D,0x00), (H,0x00), (K,0x00), (R,0x02) | - |
| HID 시퀀스 | - | modifier 있으면 register_mod → press → send → delay → release → unregister_mod → send |
| HID 전송 | - | `zmk_endpoints_send_report()` via USB |

펌웨어는 언어를 모른다. `(keycode, modifier)` 쌍을 받아 press/release로 확장할 뿐이다.

### RX 데이터 포맷 (키보드 → 폰)

```
[0]    응답 타입
[1]    시퀀스 번호
[2..N] 페이로드

응답 타입:
  0x01 = ACK (청크 처리 완료)
  0x02 = NACK (재전송 요청)
  0x03 = READY (다음 청크 요청)
  0x04 = DONE (전체 완료)
  0x05 = ERROR (에러 코드 포함)
```

### 흐름 제어

```
폰: [시작 0x02] ──→ 키보드: [READY 0x03]  ──→ 폰
폰: [청크 0x01] ──→ 키보드: HID 처리 → [ACK 0x01] ──→ 폰
폰: [청크 0x01] ──→ 키보드: HID 처리 → [ACK 0x01] ──→ 폰
...
폰: [완료 0x03] ──→ 키보드: [DONE 0x04] ──→ 폰
```

키보드가 ACK을 보내야 폰이 다음 청크 전송 → 버퍼 오버플로우 방지.

### 시퀀스 번호

시퀀스 번호는 1바이트(0-255)이며 256에서 0으로 순환한다.
ACK 기반 흐름 제어이므로 한 번에 미확인 청크는 최대 1개 → 순환해도 모호성 없음.

### 전송 Timeout

키보드가 전송 모드에서 빠져나오지 못하는 상황 방지:

| 상황 | Timeout | 동작 |
|---|---|---|
| 전송 중 폰 무응답 | 30초 | 전송 중단, 대기 상태 복귀 |
| BLE 연결 끊김 | 즉시 | 전송 중단, 대기 상태 복귀 |

- BLE 연결 끊김: Zephyr `BT_CONN_DISCONNECTED` 콜백에서 즉시 상태 초기화
- 폰 무응답: `k_work_delayable`로 30초 타이머, 청크 ACK 수신 시 리셋
- 상태 복귀 시 HID 리포트 클리어 (`zmk_hid_keyboard_clear()` + `send_report()`)

---

## 8. 키코드 시퀀스 처리

### HID 주입 타이밍

```
[modifier 없는 키]            [modifier 있는 키]
press(a)        +0ms         press(shift)      +0ms
send_report()   +0ms         send_report()     +0ms
delay           +5ms         press(a)          +5ms
release(a)      +5ms         send_report()     +5ms
send_report()   +5ms         delay             +10ms
→ 5ms/char                   release(a)        +10ms
                             send_report()     +10ms
                             release(shift)    +15ms
                             send_report()     +15ms
                             → 15ms/char
```

- 기본 간격: 5ms (보수적, 안정적)
- 앱에서 조절 가능: 1ms~10ms
- press/release를 k_work_delayable로 분리 (work queue 블로킹 없음)

### 전송 중 일반 타이핑 처리

TextBridge 전송 중 사용자가 키보드를 직접 누르면 **무시 (차단)**.
전송 완료 후 정상 복귀. 가장 단순하고 안전한 방식.

---

## 9. 문자 → 키코드 변환 (Flutter 앱)

모든 문자 → 키코드 변환은 앱에서 처리한다. 펌웨어에는 `(keycode, modifier)` 쌍만 전달.

### 변환 예시

```
ASCII:  'A' → (0x04, 0x02)              // KEY_A + Shift
        '{' → (0x2F, 0x02)              // KEY_[ + Shift
        '\n' → (0x28, 0x00)             // KEY_ENTER

한글:   "왂" → 한영키, D, H, K, Shift+R, 한영키
        분해: ㅇ(초성) → (D, 0x00)
              ㅘ(중성, 복합) → (H, 0x00), (K, 0x00)
              ㄲ(종성, 쌍자음) → (R, 0x02)
```

### 한글 처리 개요

1. 유니코드 음절 분해: `code = char - 0xAC00` → 초성/중성/종성 인덱스
2. 각 자모 → 두벌식 키코드 변환 (룩업 테이블)
3. 쌍자음(ㄲ,ㄸ,ㅃ,ㅆ,ㅉ) → modifier에 Shift 추가
4. 복합 모음(ㅘ,ㅙ 등) → 2개 키코드로 확장
5. 겹받침(ㄳ,ㄺ 등) → 2개 키코드로 확장
6. 한글 구간 전후에 한/영 전환키 삽입

상세 변환 테이블은 앱 구현 시 정의.

### OS별 한영전환 키

| OS | 키 | HID 키코드 |
|---|---|---|
| Windows | 한/영 | 0x90 (Lang1) |
| macOS | 오른쪽 Cmd | 0xE7 (Right GUI) |

---

## 10. 타이핑 속도

### 이론적 최대

- USB 1000Hz → 1ms/report
- modifier 없는 키: 2ms/char (press+release) → 500 chars/sec
- modifier 있는 키: 4ms/char → 250 chars/sec

### 실제 예상 (5ms 간격 기본)

- modifier 없는 키: 5ms/char → 200 chars/sec
- modifier 있는 키: 15ms/char → 66 chars/sec
- 소스 코드 평균 (혼합): ~150 chars/sec
- 1000자 전송: ~7초

---

## 11. Flutter 앱 UI

### 메인 화면

```
┌────────────────────────────────┐
│  TextBridge           [설정]   │
├────────────────────────────────┤
│  연결: B6 Pro ✓  (연결됨)      │
│  대상 OS: [Windows ▼]          │
├────────────────────────────────┤
│ ┌────────────────────────────┐ │
│ │                            │ │
│ │   (텍스트 입력 영역)        │ │
│ │                            │ │
│ └────────────────────────────┘ │
│                                │
│  글자 수: 1,234 | 예상: 8초     │
│                                │
│     [ 전송 ]    [ 중지 ]       │
│                                │
│  진행: ████████░░ 80%          │
└────────────────────────────────┘
```

### 기능

- BLE 스캔 / 연결
- 대상 OS 선택 (Windows / macOS)
- 텍스트 입력 (대용량 붙여넣기 가능)
- 전송 진행률 표시
- 전송 중지 기능
- 예상 소요 시간 표시

### 설정 화면

- 타이핑 속도 조절 (안전 10ms / 보통 5ms / 최대 1ms)
- 재전송 횟수 설정 (기본 3회)

---

## 12. 구현 순서

### Phase 1: HID 주입 PoC

- `textbridge.c` 생성, `CMakeLists.txt` 1줄 추가
- 3초마다 'a' 키 자동 입력
- USB 모드에서 동작 확인
- **변경:** textbridge.c(신규), CMakeLists.txt(1줄)

### Phase 2: BLE GATT 서비스

- `ble.c` 수정 (`-EALREADY` 허용 + TextBridge 페어링 훅)
- 커스텀 GATT 서비스 등록 + BLE 광고 (본딩 전용)
- 폰에서 BLE 연결 테스트 (nRF Connect 앱으로 검증)
- **변경:** ble.c(수 줄), textbridge.c(확장)

### Phase 3: 키코드 수신 → HID 출력

- BLE Write 수신 → 키코드 순차 HID 주입
- ACK/상태 Notify 응답
- 흐름 제어 (청크 단위 ACK)
- nRF Connect 앱에서 수동 테스트
- **변경:** textbridge.c(확장)

### Phase 4: Flutter 앱

- BLE 연결 + 서비스 탐색
- 텍스트 → 키코드 변환 (ASCII)
- 한글 자모 분해 + 키코드 변환
- UI 구현 (진행률, 설정)
- **신규:** Flutter 프로젝트

### Phase 5: 통합 테스트

- Mac에서 테스트 후 Windows 검증
- 대용량 텍스트 전송 안정성 확인
- 타이핑 속도 최적화

---

## 13. 빌드 & 플래시

### 빌드 환경

```bash
source ~/.zmk_env/bin/activate
export ZEPHYR_SDK_INSTALL_DIR=~/.zephyr-sdk-0.16.3
```

### 빌드

```bash
cd ~/project/textbridge/zmk_keychron/app
west build --pristine -b keychron -- -DSHIELD=keychron_b6_us
```

### 플래시

```bash
# DFU 모드 진입 (방법 1: Python 스크립트)
python3 ~/project/textbridge/tools/enter_dfu.py

# DFU 모드 진입 (방법 2: 키보드에서 ESC+U 동시 누르기)

# 2초 대기 후 플래시
sleep 2 && cp build/zephyr/zmk.uf2 /Volumes/NRF52BOOT/
```

### 빌드 + 플래시 한번에

```bash
source ~/.zmk_env/bin/activate && \
export ZEPHYR_SDK_INSTALL_DIR=~/.zephyr-sdk-0.16.3 && \
cd ~/project/textbridge/zmk_keychron/app && \
west build -b keychron -- -DSHIELD=keychron_b6_us && \
python3 ~/project/textbridge/tools/enter_dfu.py && \
sleep 2 && cp build/zephyr/zmk.uf2 /Volumes/NRF52BOOT/
```

### Zephyr 패치 (최초 1회)

```bash
cd ~/project/textbridge/zmk_keychron/zephyr
git apply ../0001-esb-nrf-fix.patch
```

---

## 14. 테스트 도구

### 통합 테스트 스크립트: `tools/textbridge_test.py`

Mac이 USB (HID 수신)와 BLE (TextBridge GATT) 양쪽에 동시 접근 가능하므로 하나의 도구로 통합.

```
┌──────────────────────┐
│  textbridge_test.py  │
│                      │
│  BLE ──→ 키보드      │  bleak: GATT Write/Notify
│  USB ←── 키보드      │  pynput: 키 이벤트 캡처
│                      │
│  보낸 것 vs 받은 것   │  비교 검증
└──────────────────────┘
```

### 모드

| 명령 | 기능 | 대상 Phase |
|---|---|---|
| `scan` | TextBridge BLE 장치 검색 (GATT UUID 스캔) | 2 |
| `monitor` | USB HID 키 이벤트 캡처 + 로그 | 1 |
| `connect` | BLE 연결 + GATT 서비스 탐색 + Write 테스트 | 2 |
| `send "text"` | 키코드 청크 전송 + ACK 수신 + HID 검증 | 3 |

### Phase별 테스트 방법

**Phase 1 (HID PoC):**
- 펌웨어 플래시 후 `monitor` 모드 실행
- 키보드가 3초마다 자동 출력하는 'a'를 캡처 확인

**Phase 2 (BLE GATT):**
- `scan`으로 "B6 TextBridge" 장치 발견 확인
- `connect`로 GATT 서비스/특성 목록 출력, Write 테스트

**Phase 3 (전체 파이프라인):**
- `send "hello"`로 키코드 전송
- BLE 측: ACK 수신 확인
- USB 측: "hello" 키스트로크 수신 확인
- 보낸 것과 받은 것 자동 비교

### 의존성

```
bleak     # BLE GATT 클라이언트
pynput    # macOS 키 이벤트 캡처 (접근성 권한 필요)
asyncio   # 비동기 처리
```

---

## 15. ZMK 펌웨어 변경 총정리


### 신규 파일 (1개)

| 파일 | 목적 |
|---|---|
| `app/src/textbridge.c` | TextBridge 전체 (BLE GATT + HID 주입 + 광고 + 페어링) |

### 수정 파일 (2개, 최소 변경)

| 파일 | 변경량 | 내용 |
|---|---|---|
| `app/CMakeLists.txt` | 1줄 추가 | `target_sources(app PRIVATE src/textbridge.c)` |
| `app/src/ble.c` | 수 줄 | `bt_enable()` `-EALREADY` 허용 + `zmk_ble_prof_pair_start()`에 USB 모드 TextBridge 훅 |

### 변경하지 않는 파일

behavior_bt.c, hid.c, endpoints.c, hog.c, keymap, DTS, defconfig, 24G — 전부 그대로.
