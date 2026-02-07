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
| BLE | BLE 사용 중 | 가능 (다중 프로필) | 지원 가능 |
| 2.4GHz 동글 | ESB 독점 | **불가** | **미지원** |

> **설계 결정:** PC는 USB 유선 연결, 폰은 BLE 연결으로 확정.
> 2.4GHz 모드에서는 TextBridge 미지원 (하드웨어 제약).

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

### 키크론 ZMK 소스 (빌드용)
```
~/zmk_keychron/
├── app/
│   ├── src/
│   │   ├── ble.c                  ← BLE 연결 관리 (수정: 1줄)
│   │   ├── hog.c                  ← HID over GATT (변경 없음)
│   │   ├── hid.c                  ← HID 리포트 생성 (변경 없음)
│   │   ├── endpoints.c            ← USB/BLE/2.4G 전송 라우팅 (변경 없음)
│   │   ├── behaviors/
│   │   │   └── behavior_bt.c      ← BT 비헤이비어 (수정: 수 줄)
│   │   ├── textbridge.c           ← [신규] TextBridge 모듈
│   │   └── 24G/                   ← 2.4GHz ESB (변경 없음)
│   ├── boards/arm/keychron/       ← 보드 정의 (변경 없음)
│   ├── boards/shields/keychron/   ← 키맵 (변경 없음)
│   └── CMakeLists.txt             ← 빌드 설정 (수정: 1줄)
└── zephyr/                        ← Zephyr RTOS (변경 없음)
```

### TextBridge 저장소 (이 저장소)
```
/Users/evan/textbridge/
├── README.md
└── docs/plans/
    └── 2026-02-06-textbridge-design.md
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

### 4.2 수정: ble.c (1줄)

```c
// 기존:
int err = bt_enable(NULL);
if (err) {

// 수정:
int err = bt_enable(NULL);
if (err && err != -EALREADY) {
```

TextBridge가 먼저 `bt_enable()`을 호출해도 이후 BLE 모드 전환 시 정상 동작.

### 4.3 수정: behavior_bt.c (수 줄)

```c
// BT_PAIR_CMD 분기에 추가:
case BT_PAIR_CMD:
    if (get_current_transport() == ZMK_TRANSPORT_USB) {
        return zmk_textbridge_pair_start();
    }
    return zmk_ble_prof_pair_start(binding->param2);
```

USB 모드에서 Fn+1 → TextBridge 페어링. BLE 모드에서 Fn+1 → 기존 BT 페어링.

### 4.4 수정: CMakeLists.txt (1줄)

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

### ASCII 변환

```
'a' → (0x04, 0x00)        // KEY_A, no modifier
'A' → (0x04, 0x02)        // KEY_A + Left Shift
'1' → (0x1E, 0x00)        // KEY_1
'!' → (0x1E, 0x02)        // KEY_1 + Left Shift
'{' → (0x2F, 0x02)        // KEY_[ + Left Shift
'\n' → (0x28, 0x00)       // KEY_ENTER
'\t' → (0x2B, 0x00)       // KEY_TAB
' '  → (0x2C, 0x00)       // KEY_SPACE
```

### 한글 변환 (자모 분해)

```
"간" (U+AC04)
  → 초성: ㄱ (index 0)
  → 중성: ㅏ (index 0)
  → 종성: ㄴ (index 2)

전송 순서: 한/영키 → ㄱ → ㅏ → ㄴ → 한/영키
```

### 한글 유니코드 분해 공식

```
code = char - 0xAC00
초성 = code / 588
중성 = (code % 588) / 28
종성 = code % 28
```

### 자모 → 키코드 매핑 (두벌식)

```
초성: ㄱ→R, ㄴ→S, ㄷ→E, ㄹ→F, ㅁ→A, ㅂ→Q, ㅅ→T, ㅇ→D, ㅈ→W, ㅊ→C, ㅋ→Z, ㅌ→X, ㅍ→V, ㅎ→G
중성: ㅏ→K, ㅓ→J, ㅗ→H, ㅜ→N, ㅡ→M, ㅣ→L, ㅐ→O, ㅔ→P...
```

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

- `ble.c` 1줄 수정 (`-EALREADY` 허용)
- `behavior_bt.c` 수정 (USB 모드 Fn+1 → TextBridge 페어링)
- 커스텀 GATT 서비스 등록 + BLE 광고
- 폰에서 BLE 연결 테스트 (nRF Connect 앱으로 검증)
- **변경:** ble.c(1줄), behavior_bt.c(수 줄), textbridge.c(확장)

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

## 13. ZMK 펌웨어 변경 총정리

### 신규 파일 (1개)

| 파일 | 목적 |
|---|---|
| `app/src/textbridge.c` | TextBridge 전체 (BLE GATT + HID 주입 + 광고 + 페어링) |

### 수정 파일 (3개, 최소 변경)

| 파일 | 변경량 | 내용 |
|---|---|---|
| `app/CMakeLists.txt` | 1줄 추가 | `target_sources(app PRIVATE src/textbridge.c)` |
| `app/src/ble.c` | 1줄 수정 | `bt_enable()` 리턴값 `-EALREADY` 허용 |
| `app/src/behaviors/behavior_bt.c` | 수 줄 추가 | USB 모드 Fn+1 → TextBridge 페어링 분기 |

### 변경하지 않는 파일

hid.c, endpoints.c, hog.c, keymap, DTS, defconfig, 24G — 전부 그대로.
