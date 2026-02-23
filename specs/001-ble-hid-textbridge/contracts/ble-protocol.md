# BLE GATT Protocol Contract: TextBridge

## Service Definition

| Item | Value |
|------|-------|
| Service UUID | `12340000-1234-1234-1234-123456789abc` |
| TX Characteristic | `12340001-1234-1234-1234-123456789abc` (Write Without Response) |
| RX Characteristic | `12340002-1234-1234-1234-123456789abc` (Notify) |
| Advertising Name | `TextBridge` |
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
Byte 4: warmup_delay (1~255 ms) — 세션 첫 청크 시작 전 USB 호스트 동기화 대기 (이후 청크는 스킵)
```

**Expected Response**: ACK (0x01)
**Firmware Fallback Values**: press_delay=1, release_delay=1, combo_delay=2, warmup_delay=50

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

### Encoding Note

프로토콜은 인코딩에 무관하다. 키코드 페어의 내용은 앱이 결정한다.

- **Direct mode**: 앱이 텍스트를 ASCII/Hangul HID 키코드로 직접 변환하여 전송
- **Compressed mode**: 앱이 텍스트를 zlib 압축 후 hex 인코딩(0-9, a-f)하여 전송. hex 문자는 Shift 없이 키코드로 표현 가능하여 딜레이를 최소화할 수 있다

키보드 펌웨어는 수신된 키코드를 그대로 HID로 주입한다. 모드 구분 없음.

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
