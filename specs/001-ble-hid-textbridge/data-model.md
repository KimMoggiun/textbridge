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

**Compressed mode 특성**: hex 문자(0-9, a-f)만 전송하므로 modifier는 항상 0x00.
Shift나 IME 전환 키코드가 포함되지 않는다.

### Chunk

BLE 패킷 하나에 담기는 키코드 쌍의 묶음.

| Field | Type | Size | Description |
|-------|------|------|-------------|
| command | uint8 | 1B | TB_CMD_KEYCODE (0x01) |
| sequence | uint8 | 1B | 1~255 순환 시퀀스 번호 (0은 사용 안 함) |
| count | uint8 | 1B | 키코드 쌍 개수 (1~32) |
| pairs | KeycodePair[] | count×2B | 키코드 쌍 배열 |

**Constraints**:
- 최대 크기: 3 (헤더) + count × 2 ≤ BLE MTU ATT payload
- MTU 23B → 최대 8쌍, MTU 244B → 최대 119쌍 (상한: TB_MAX_KEYCODES=32)
- count ≤ TB_MAX_KEYCODES (펌웨어 버퍼 크기, 현재 32)

### TransmissionSession

SET_DELAY + START~DONE/ABORT 사이의 전송 단위.

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
IDLE ──SET_DELAY──→ IDLE ──START──→ READY ──KEYCODE──→ SENDING ──ACK──→ READY
  ↑                                                         │              │
  │                                                       NACK──→ RETRY ──┘
  │                                                         │
  │                                                      3회 실패──→ ERROR──→ IDLE
  │                                                         │
  ├─────────────────────────DONE───────────────────────────←┘
  ├─────────────────────────ABORT─────────────────────────←─(어느 상태에서든)
  └─────────────────────────DISCONNECT────────────────────←─(어느 상태에서든)
```

| State | Description |
|-------|-------------|
| IDLE | 대기 상태. 전송 중 아님 |
| READY | START 응답(READY) 수신 또는 ACK 수신. 다음 청크 전송 가능 |
| SENDING | 청크 전송 후 ACK 대기 중 (동적 타임아웃) |
| RETRY | ACK 타임아웃으로 동일 청크 재전송 (최대 3회) |
| ERROR | 재전송 3회 실패. 사용자에게 알림 후 IDLE 전환 |

### BLEBond

키보드-폰 간 영구 연결 정보.

| Field | Type | Description |
|-------|------|-------------|
| address | BT_ADDR_LE | 폰의 BLE MAC 주소 |
| ltk | 128-bit | Long Term Key (암호화) |
| identity | uint8 | BT_ID_DEFAULT (0) — ZMK 프로필(ID 1-4)과 분리 |

**Lifecycle**: 최초 Fn+1 홀드 시 생성 → 이후 자동 연결 → 새 폰 페어링 시 교체

### CompressionService

텍스트를 전송 가능한 hex 문자열로 변환하는 서비스.

**Pipeline**: 원문 텍스트 → UTF-8 인코딩 → zlib 압축 → lowercase hex 인코딩

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| compressToHex | String | String | 원문을 hex 문자열로 변환 |
| compressionInfo | String | {originalBytes, compressedBytes, hexChars} | 압축 통계 (UI 표시용) |
| decoderJava | — | String | H.java 디코더 소스 (PC 배포용 상수) |

**특성**:
- 출력은 0-9, a-f 만 포함 (총 16종 문자)
- Shift modifier 불필요, IME 전환 불필요
- 한글/이모지/이진 데이터 등 모든 입력을 동일하게 처리

### AppSettings

사용자 앱 설정 (영속화).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| transmissionMode | enum | compressed | direct / compressed |
| pressDelay | int | 1 | 키 press 지속 시간 ms (1~255) |
| releaseDelay | int | 1 | release → next press 간격 ms (1~255) |
| comboDelay | int | 2 | modifier 조합 내 딜레이 ms (modifier → key, 1~255) |
| warmupDelay | int | 50 | 각 청크 시작 전 USB 호스트 동기화 대기 ms (1~255) |
| lastDeviceAddress | String? | null | 마지막 연결 기기 BLE 주소 |

**Storage**: SharedPreferences (key-value)
**Sync**: BLE 연결 후 전송 시작 시 `CMD_SET_DELAY` (0x05)로 펌웨어에 전송

### TransmissionMode

```dart
enum TransmissionMode { direct, compressed }
```

| Value | Description |
|-------|-------------|
| compressed | 기본 모드. 텍스트를 UTF-8 → zlib → hex로 변환 후 전송. PC에서 H.java 디코더로 복원. |
| direct | 디코더 배포 전용. ASCII 텍스트를 키코드로 직접 전송. 한글/이모지 불가. |

### Protocol Commands

| Command | Code | Direction | Payload | Description |
|---------|------|-----------|---------|-------------|
| CMD_KEYCODE | 0x01 | phone→kb | seq(1) + count(1) + pairs(count×2) | 키코드 청크 전송 |
| CMD_START | 0x02 | phone→kb | seq(1) + totalChunks(2, big-endian) | 전송 세션 시작 |
| CMD_DONE | 0x03 | phone→kb | seq(1) | 전송 완료 |
| CMD_ABORT | 0x04 | phone→kb | seq(1) | 전송 중단 |
| CMD_SET_DELAY | 0x05 | phone→kb | pressDelay(1) + releaseDelay(1) + comboDelay(1) + warmupDelay(1) | 딜레이 설정 (4 params) |

### Protocol Responses

| Response | Code | Direction | Description |
|----------|------|-----------|-------------|
| RESP_ACK | 0x01 | kb→phone | 청크 처리 완료 |
| RESP_NACK | 0x02 | kb→phone | 청크 재전송 요청 |
| RESP_READY | 0x03 | kb→phone | START 수신 후 준비 완료 |
| RESP_DONE | 0x04 | kb→phone | DONE 수신 확인 |
| RESP_ERROR | 0x05 | kb→phone | 오류 (프로토콜 위반, 버퍼 초과 등) |

### BLE Service

| Attribute | Value |
|-----------|-------|
| Service UUID | `12340000-1234-1234-1234-123456789abc` |
| TX Characteristic (phone→kb write) | `12340001-1234-1234-1234-123456789abc` |
| RX Characteristic (kb→phone notify) | `12340002-1234-1234-1234-123456789abc` |
| Device Name (advertised) | `TextBridge` |
| BT Identity | BT_ID_DEFAULT (0) — ZMK profiles use ID 1-4 |

## Relationships

```
AppSettings ──1:1──→ TransmissionSession (설정값 참조)
TransmissionSession ──1:N──→ Chunk (세션당 여러 청크)
Chunk ──1:N──→ KeycodePair (청크당 여러 키코드 쌍)
CompressionService ──transforms──→ String (원문) → String (hex)
BLEBond ──1:1──→ 키보드 (1:1 폰-키보드)
```

## Removed Entities (historical)

다음 엔티티는 이전 설계에 있었으나 현재 구현에서 제거되었다.

| Entity | 제거 이유 |
|--------|---------|
| HangulSyllable | Compressed mode에서 한글을 직접 분해할 필요 없음. zlib → hex 파이프라인이 모든 유니코드를 처리. |
| TargetOS | Compressed mode는 IME 전환 불필요. OS 종류와 무관하게 동작. |
| toggleDelay | IME 토글 키코드 자체가 제거됨. CMD_SET_DELAY에서 toggleDelay 파라미터 삭제. |
| HangulService | hangul_service.dart 파일 삭제됨. Dubeolsik 매핑 불필요. |
