# BLE GATT Protocol Contract: TextBridge

## Service Definition

| Item | Value |
|------|-------|
| Service UUID | `12340000-1234-1234-1234-123456789abc` |
| TX Characteristic | `12340001-1234-1234-1234-123456789abc` (Write Without Response) |
| RX Characteristic | `12340002-1234-1234-1234-123456789abc` (Notify) |
| Advertising Name | `B6 TextBridge` |
| BLE Identity | `BT_ID_DEFAULT` (0) |

## TX Commands (Phone → Keyboard)

### START (0x02)

전송 세션 시작.

```
Byte 0: 0x02 (TB_CMD_START)
Byte 1: sequence number
Byte 2: total chunks (high byte)
Byte 3: total chunks (low byte)
```

**Expected Response**: READY (0x03)

### KEYCODE (0x01)

키코드 데이터 청크.

```
Byte 0:     0x01 (TB_CMD_KEYCODE)
Byte 1:     sequence number
Byte 2:     count (keycode pair 개수, 1~119)
Byte 3:     keycode_1
Byte 4:     modifier_1
Byte 5:     keycode_2
Byte 6:     modifier_2
...
Byte 3+2N-2: keycode_N
Byte 3+2N-1: modifier_N
```

**Precondition**: START가 먼저 전송되어야 함
**Expected Response**: ACK (0x01) 또는 NACK (0x02) 또는 ERROR (0x05)

### DONE (0x03)

전송 세션 완료.

```
Byte 0: 0x03 (TB_CMD_DONE)
Byte 1: sequence number
```

**Expected Response**: DONE (0x04)

### ABORT (0x04)

전송 세션 중단.

```
Byte 0: 0x04 (TB_CMD_ABORT)
Byte 1: sequence number
```

**Expected Response**: ACK (0x01)
**Side Effect**: 펌웨어가 HID 리포트를 즉시 클리어

### SET_DELAY (0x05)

HID 주입 타이밍 파라미터 설정. 세션 외(IDLE 상태)에서 전송.

```
Byte 0: 0x05 (TB_CMD_SET_DELAY)
Byte 1: press_delay (1~255 ms) — 키 누르는 시간 (press duration)
Byte 2: release_delay (1~255 ms) — 키 간 딜레이 (release → next press)
Byte 3: combo_delay (1~255 ms) — modifier 조합 내 딜레이 (modifier press → key press)
Byte 4: toggle_press (1~255 ms) — IME 토글키 누르는 시간 (press duration)
Byte 5: toggle_delay (1~255 ms) — IME 토글키 release 후 대기 시간
Byte 6: warmup_delay (1~255 ms) — 세션 첫 청크 시작 전 USB 호스트 동기화 대기 (이후 청크는 스킵)
```

**Expected Response**: ACK (0x01)
**Firmware Fallback Values**: press_delay=5, release_delay=5, combo_delay=2, toggle_press=20, toggle_delay=100, warmup_delay=50
**App Recommended toggle_delay**: macOS=300ms, Windows=100ms (앱이 OS별 권장값을 초기화하고 `CMD_SET_DELAY`로 전송)

## RX Responses (Keyboard → Phone)

### ACK (0x01)

```
Byte 0: 0x01 (TB_RESP_ACK)
Byte 1: sequence number (처리 완료한 청크의 seq)
```

### NACK (0x02)

```
Byte 0: 0x02 (TB_RESP_NACK)
Byte 1: sequence number
```

**Meaning**: 이전 청크 주입 중 (busy). 재전송 필요.

### READY (0x03)

```
Byte 0: 0x03 (TB_RESP_READY)
Byte 1: sequence number
```

**Meaning**: START 수신 완료, 첫 KEYCODE 청크 전송 가능.

### DONE (0x04)

```
Byte 0: 0x04 (TB_RESP_DONE)
Byte 1: sequence number
```

### ERROR (0x05)

```
Byte 0: 0x05 (TB_RESP_ERROR)
Byte 1: sequence number
Byte 2: error code
```

| Error Code | Name | Description |
|------------|------|-------------|
| 0x03 | OVERFLOW | 청크 키코드 수 초과 (> TB_MAX_KEYCODES) |
| 0x04 | SEQ | START 없이 KEYCODE 수신 |

## Flow Control

### Normal Flow

```
Phone                    Keyboard
  │                         │
  │── START (seq=0) ───────→│
  │←── READY (seq=0) ──────│
  │                         │
  │── KEYCODE (seq=1) ─────→│  ← HID 주입 시작
  │←── ACK (seq=1) ────────│  ← 주입 완료
  │                         │
  │── KEYCODE (seq=2) ─────→│
  │←── ACK (seq=2) ────────│
  │                         │
  │── DONE (seq=3) ────────→│
  │←── DONE (seq=3) ───────│
```

### Toggle Key Flow (한영 전환)

토글키(한영 전환)는 반드시 단독 청크(1개 키코드)로 분리하여 전송한다.
키보드는 토글키 HID 주입 후 `toggle_delay` (앱이 OS별 권장값 전송: macOS=300ms, Windows=100ms. 펌웨어 폴백=100ms) 딜레이를 거친 뒤 ACK를 전송한다.
앱은 ACK를 수신한 후에 다음 키코드 청크를 전송한다.

```
Phone                    Keyboard
  │                         │
  │── START (seq=0) ───────→│
  │←── READY (seq=0) ──────│
  │                         │
  │── KEYCODE (seq=1) ─────→│  ← "Hello " 영문 키코드 (6쌍)
  │←── ACK (seq=1) ────────│
  │                         │
  │── KEYCODE (seq=2) ─────→│  ← 토글키 1개만 (Ctrl+Space 또는 LANG1)
  │  (keyboard: HID inject   │
  │   + 100ms delay + ACK)   │
  │←── ACK (seq=2) ────────│  ← OS 입력기 전환 완료 보장
  │                         │
  │── KEYCODE (seq=3) ─────→│  ← "안녕" 한글 자모 키코드
  │←── ACK (seq=3) ────────│
  │                         │
  │── KEYCODE (seq=4) ─────→│  ← 토글키 1개만 (영문 복귀)
  │←── ACK (seq=4) ────────│
  │                         │
  │── KEYCODE (seq=5) ─────→│  ← " World" 영문 키코드
  │←── ACK (seq=5) ────────│
  │                         │
  │── DONE (seq=6) ────────→│
  │←── DONE (seq=6) ───────│
```

**규칙**: 앱의 `textToKeycodes()`에서 토글키를 청크 경계로 강제 분리한다.
토글키가 청크 중간에 있으면 해당 위치에서 청크를 분할한다.

### Retry Flow (ACK Timeout)

```
Phone                    Keyboard
  │                         │
  │── KEYCODE (seq=1) ─────→│
  │    (500ms timeout)       │  ← ACK 손실
  │── KEYCODE (seq=1) ─────→│  ← 재전송 (retry 1)
  │←── ACK (seq=1) ────────│  ← 중복 감지, HID 건너뜀, ACK만 재전송
```

### Duplicate Detection

- 펌웨어는 `tb_last_seq`에 마지막 처리한 시퀀스 저장
- 수신 seq == tb_last_seq → HID 주입 건너뜀, ACK만 재전송
- 수신 seq != tb_last_seq → 정상 처리

### Timeout Rules

| Side | Timeout | Action |
|------|---------|--------|
| App | 500ms per ACK | 동일 청크 재전송 (최대 3회) |
| Firmware | 30초 전체 세션 | 전송 중단, HID 클리어, IDLE 복귀 |

## MTU & Chunk Size

```
BLE MTU (negotiated) → ATT payload = MTU - 3
App header = 3 bytes (cmd + seq + count)
Available for keycodes = ATT payload - 3
Max keycode pairs = Available / 2

Example:
  MTU 23  → ATT 20  → keycodes 17 → 8 pairs
  MTU 185 → ATT 182 → keycodes 179 → 89 pairs
  MTU 244 → ATT 241 → keycodes 238 → 119 pairs
```
