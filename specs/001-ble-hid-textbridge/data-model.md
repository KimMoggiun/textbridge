# Data Model: TextBridge

## Entities

### KeycodePair

단일 키 입력을 나타내는 최소 단위.

| Field | Type | Size | Description |
|-------|------|------|-------------|
| keycode | uint8 | 1B | USB HID keycode (0x04~0xE7) |
| modifier | uint8 | 1B | HID modifier bitmask (0x00=없음, 0x02=Shift 등) |

**Validation**:
- keycode: 0x00 (reserved) 외의 유효한 HID keycode
- modifier: 0x00~0xFF (Ctrl/Shift/Alt/GUI 비트 조합)

### Chunk

BLE 패킷 하나에 담기는 키코드 쌍의 묶음.

| Field | Type | Size | Description |
|-------|------|------|-------------|
| command | uint8 | 1B | TB_CMD_KEYCODE (0x01) |
| sequence | uint8 | 1B | 0~255 순환 시퀀스 번호 |
| count | uint8 | 1B | 키코드 쌍 개수 (1~119) |
| pairs | KeycodePair[] | count×2B | 키코드 쌍 배열 |

**Constraints**:
- 최대 크기: 3 (헤더) + count × 2 ≤ BLE MTU ATT payload
- MTU 23B → 최대 8쌍, MTU 244B → 최대 119쌍
- count ≤ TB_MAX_KEYCODES (펌웨어 버퍼 크기, 현재 32)

### TransmissionSession

START~DONE/ABORT 사이의 전송 단위.

| Field | Type | Description |
|-------|------|-------------|
| state | SessionState | 현재 상태 (아래 상태 전이 참조) |
| totalChunks | uint16 | 전체 청크 수 (START에서 전송) |
| currentSeq | uint8 | 현재 시퀀스 번호 |
| lastAckedSeq | uint8 | 마지막 ACK 받은 시퀀스 |
| retryCount | uint8 | 현재 청크 재전송 횟수 (최대 3) |
| failedAt | int? | 실패 시 마지막 성공 키코드 위치 (앱 표시용) |

### SessionState (상태 전이)

```
IDLE ──START──→ READY ──KEYCODE──→ SENDING ──ACK──→ READY
  ↑                                    │              │
  │                                  NACK──→ RETRY ──┘
  │                                    │
  │                                 3회 실패──→ ERROR──→ IDLE
  │                                    │
  ├────────────────DONE───────────────←┘
  ├────────────────ABORT──────────────←─(어느 상태에서든)
  └────────────────DISCONNECT─────────←─(어느 상태에서든)
```

| State | Description |
|-------|-------------|
| IDLE | 대기 상태. 전송 중 아님 |
| READY | START 응답(READY) 수신 또는 ACK 수신. 다음 청크 전송 가능 |
| SENDING | 청크 전송 후 ACK 대기 중 (500ms 타이머) |
| RETRY | ACK 타임아웃으로 동일 청크 재전송 (최대 3회) |
| ERROR | 재전송 3회 실패. 사용자에게 알림 후 IDLE 전환 |

### BLEBond

키보드-폰 간 영구 연결 정보.

| Field | Type | Description |
|-------|------|-------------|
| address | BT_ADDR_LE | 폰의 BLE MAC 주소 |
| ltk | 128-bit | Long Term Key (암호화) |
| identity | uint8 | BT_ID_DEFAULT (0) — ZMK 프로필과 분리 |

**Lifecycle**: 최초 Fn+1 홀드 시 생성 → 이후 자동 연결 → 새 폰 페어링 시 교체

### HangulSyllable

한글 음절 분해 결과.

| Field | Type | Description |
|-------|------|-------------|
| codepoint | uint32 | 유니코드 코드포인트 (0xAC00~0xD7A3) |
| chosung | uint8 | 초성 인덱스 (0~18) |
| jungsung | uint8 | 중성 인덱스 (0~20) |
| jongsung | uint8 | 종성 인덱스 (0~27, 0=없음) |

**Decomposition**: `code = codepoint - 0xAC00; cho = code/588; jung = (code%588)/28; jong = code%28`

### AppSettings

사용자 앱 설정 (영속화).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| targetOS | enum | Windows | Windows / macOS |
| typingSpeed | enum | Normal | Safe(10ms) / Normal(5ms) / Fast(1ms) |
| lastDeviceAddress | String? | null | 마지막 연결 기기 BLE 주소 |

**Storage**: SharedPreferences (key-value)

## Relationships

```
AppSettings ──1:1──→ TransmissionSession (설정값 참조)
TransmissionSession ──1:N──→ Chunk (세션당 여러 청크)
Chunk ──1:N──→ KeycodePair (청크당 여러 키코드 쌍)
HangulSyllable ──1:N──→ KeycodePair (음절당 2~7개 키코드)
BLEBond ──1:1──→ 키보드 (1:1 폰-키보드)
```
