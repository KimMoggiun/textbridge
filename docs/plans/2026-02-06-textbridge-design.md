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
키크론 펌웨어는 MPSL(Multiprotocol Service Layer) 미사용으로 동시 구동 불가.

| PC 연결 | 라디오 상태 | 폰 BLE 연결 | TextBridge |
|---|---|---|---|
| **USB (유선)** | 미사용 | **가능** | **지원** |
| BLE | BLE 사용 중 | 가능 (다중 프로필) | 지원 가능 |
| 2.4GHz 동글 | ESB 독점 | **불가** | **미지원** |

> **설계 결정:** PC는 USB 유선 연결, 폰은 BLE 연결으로 확정.
> 2.4GHz 모드에서는 TextBridge 미지원 (하드웨어 제약).

---

## 2. 프로젝트 구조

### 키크론 ZMK 소스 (빌드용)
```
~/zmk_keychron/                    ← 키크론 ZMK 포크 (전체 소스)
├── app/
│   ├── src/
│   │   ├── ble.c                  ← BLE 연결 관리 (수정: 1줄)
│   │   ├── hog.c                  ← HID over GATT
│   │   ├── hid.c                  ← HID 리포트 생성
│   │   ├── endpoints.c            ← USB/BLE/2.4G 전송 라우팅
│   │   ├── textbridge.c           ← [신규] TextBridge 모듈
│   │   └── 24G/                   ← 2.4GHz ESB (프리컴파일)
│   ├── boards/arm/keychron/       ← 보드 정의
│   ├── boards/shields/keychron/   ← 키맵, 오버레이
│   └── CMakeLists.txt             ← 빌드 설정 (수정: 1줄)
└── zephyr/                        ← Zephyr RTOS
```

### 설정 백업 (이 저장소)
```
/Users/evan/project/
├── textbridge/
│   └── docs/plans/               ← 설계 문서
└── zmkflash/
    └── zmk-b6pro-backup/         ← 설정 백업, 패치
```

---

## 3. HID 키 입력 경로 (분석 완료)

### 코드 경로

```
zmk_hid_keyboard_press(keycode)        ← hid.c: 리포트에 키 추가
    ↓
zmk_endpoints_send_report(HID_USAGE_KEY)  ← endpoints.c: 활성 전송으로 라우팅
    ↓                                         ├→ USB: zmk_usb_hid_send_report()
    ↓                                         ├→ BLE: zmk_hog_send_keyboard_report()
    ↓                                         └→ 2.4G: zmk_24g_send_report()
zmk_hid_keyboard_release(keycode)
    ↓
zmk_endpoints_send_report(HID_USAGE_KEY)
```

### 핵심 API (app/include/zmk/hid.h)

```c
int zmk_hid_keyboard_press(zmk_key_t code);   // 키 누름 (HID_USAGE_KEY_KEYBOARD_A = 0x04)
int zmk_hid_keyboard_release(zmk_key_t code);  // 키 뗌
int zmk_endpoints_send_report(uint16_t usage_page);  // HID_USAGE_KEY로 전송
uint8_t get_current_transport(void);            // 현재 전송 모드 확인
```

### 동시성 안전

- `zmk_hid_keyboard_press/release`는 전역 `keyboard_report` 수정
- ZMK 키맵 처리와 TextBridge 모두 시스템 work queue 사용
- 같은 work queue → 직렬화 → 경쟁 조건 없음

---

## 4. BLE 활성화 전략 (USB 모드)

### 문제

USB 모드로 부팅 시 `zmk_ble_init()`이 호출되지 않아 `bt_enable()` 실행 안 됨.
라디오는 비어있으므로 BLE를 켜도 USB와 충돌 없음.

### 해결: ble.c 최소 수정 (1줄)

```c
// ble.c의 zmk_ble_init() 내부 — 기존:
int err = bt_enable(NULL);
if (err) {
    LOG_ERR("BLUETOOTH FAILED (%d)", err);
    return err;
}

// 수정 후:
int err = bt_enable(NULL);
if (err && err != -EALREADY) {    // ← 이 조건만 추가
    LOG_ERR("BLUETOOTH FAILED (%d)", err);
    return err;
}
```

### 동작 흐름

1. 키보드 부팅 → USB 모드
2. `textbridge.c`의 `SYS_INIT` → `bt_enable()` 호출 → BLE 스택 활성화
3. TextBridge GATT 서비스 등록 + 광고 시작
4. 휴대폰 연결 가능
5. (나중에 BLE 모드 전환 시) `zmk_ble_init()` → `bt_enable()` → `-EALREADY` → 무시 후 정상 진행

---

## 5. BLE 커스텀 GATT 서비스

> **상태:** 설계 진행 중

### 기본 구조
- `BT_GATT_SERVICE_DEFINE`으로 정적 등록 (split 서비스 패턴 참고)
- 커스텀 128-bit UUID
- Write Characteristic: 앱 → 키보드 (키코드 데이터)
- Notify Characteristic: 키보드 → 앱 (ACK/상태)

### 참고 코드
- `app/src/split/bluetooth/service.c` — 커스텀 GATT 서비스 예시
- `app/include/zmk/split/bluetooth/uuid.h` — UUID 정의 패턴

---

## 6. 문자 → 키코드 변환 (앱에서 처리)

### ASCII 변환
```
'a' → (0x04, 0)           // KEY_A, no modifier
'A' → (0x04, SHIFT)       // KEY_A + Shift
'1' → (0x1E, 0)           // KEY_1
'!' → (0x1E, SHIFT)       // KEY_1 + Shift
'{' → (0x2F, SHIFT)       // KEY_[ + Shift
'\n' → (0x28, 0)          // KEY_ENTER
```

### 한글 변환 (자모 분해)
```
"간" (U+AC04)
  → 초성: ㄱ (index 0)
  → 중성: ㅏ (index 0)
  → 종성: ㄴ (index 2)

전송 순서: 한/영 → ㄱ → ㅏ → ㄴ → 한/영
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

---

## 7. OS별 한영전환 키

| OS | 키 | HID 키코드 |
|---|---|---|
| Windows | 한/영 | 0x90 (Lang1) |
| macOS | 오른쪽 Cmd | 0xE7 (Right GUI) |

앱에서 대상 OS 선택 → 해당 키코드로 한영전환

---

## 8. 타이핑 속도

### 목표
- 500+ chars/sec

### HID 제약
- USB: 1000Hz (1ms 간격)
- 표준 HID: 6키 동시 리포트 가능

### 타이밍
```
키 다운: 1ms
키 업: 1ms
총: 2ms/char = 500 chars/sec
```

### Modifier 키 처리
```
'A' 입력:
1. Shift 다운 (1ms)
2. A 다운 (1ms)
3. A 업 (1ms)
4. Shift 업 (1ms)
→ 4ms (대문자/특수문자)
```

---

## 9. Flutter 앱 UI

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
│  글자 수: 1,234 | 예상: 3초     │
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

---

## 10. ZMK 펌웨어 변경 요약

### 신규 파일

| 파일 | 목적 |
|---|---|
| `app/src/textbridge.c` | TextBridge 메인 모듈 (BLE GATT + HID 주입) |

### 수정 파일 (최소)

| 파일 | 변경 | 내용 |
|---|---|---|
| `app/CMakeLists.txt` | 1줄 추가 | `target_sources(app PRIVATE src/textbridge.c)` |
| `app/src/ble.c` | 1줄 수정 | `bt_enable()` 리턴값에 `-EALREADY` 허용 |

### 변경하지 않는 파일

hid.c, endpoints.c, hog.c, keymap, DTS, defconfig — 전부 그대로.
기존 공개 API만 호출하여 HID 키 입력 주입.

---

## 11. 구현 순서

### Phase 1: HID 주입 PoC
- `textbridge.c` 생성
- 3초마다 'a' 키 자동 입력
- USB 모드에서 동작 확인

### Phase 2: BLE GATT 서비스
- 커스텀 GATT 서비스 추가
- USB 모드에서 BLE 동시 활성화
- 폰에서 BLE 연결 → 키코드 전송 → HID 출력

### Phase 3: Flutter 앱
- BLE 연결 + 키코드 변환 + UI
- 한글 자모 분해 구현

### Phase 4: 통합 테스트
- Mac에서 테스트 후 Windows 검증
- 대용량 텍스트 전송 안정성 확인

---

## 12. 미결정 사항

- [ ] BLE GATT 서비스 UUID 및 Characteristic 상세
- [ ] BLE 프로토콜 상세 (청크 포맷, ACK 구조)
- [ ] 청크 크기 최적값
- [ ] 에러 처리 상세 로직
- [ ] TextBridge BLE 광고 방식 (기존 광고 vs 독립 광고)
- [ ] 키보드 일반 사용 중 TextBridge 입력 충돌 방지
