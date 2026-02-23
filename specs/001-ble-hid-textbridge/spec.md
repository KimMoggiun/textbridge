# 기능 명세: TextBridge BLE-to-USB HID 텍스트 브릿지

**Feature Branch**: `001-ble-hid-textbridge`
**Created**: 2026-02-08
**Status**: Active

**Input**: 폐쇄망 회사 PC에 휴대폰에서 프로그래밍 소스 코드를 전송하는 시스템.
Keychron B6 Pro 키보드(nRF52840)를 BLE-to-USB HID 브릿지로 활용.

## Architecture Overview

```
Phone (Flutter) → BLE GATT → Keyboard (nRF52840) → USB HID → PC
```

**전송 파이프라인 (Compressed mode)**:

```
원문 텍스트 → UTF-8 → zlib 압축 → lowercase hex 문자열 → ASCII keycode 목록 → BLE 청크 → USB HID
```

**전송 파이프라인 (Direct mode — decoder 배포 전용)**:

```
원문 텍스트(ASCII) → ASCII keycode 목록 → BLE 청크 → USB HID
```

PC에서는 H.java 디코더가 hex 파일을 역변환하여 원문을 복원한다.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 텍스트 전송 (Compressed mode, Priority: P1)

사용자는 휴대폰에서 임의의 텍스트(소스 코드, 한글, 이모지 포함 가능)를 입력하고,
앱이 이를 zlib 압축 후 hex 인코딩하여 키보드를 통해 PC에 타이핑한다.
PC에서는 H.java 디코더로 hex 파일을 원문으로 복원한다.

키보드는 USB로 PC에 연결되어 있으며, 휴대폰은 BLE로 키보드와 연결된다.
앱은 hex 문자(0-9, a-f)만 전송하므로 Shift나 IME 전환이 불필요하다.

**Why this priority**: 프로젝트의 핵심 가치. 폐쇄망 PC에 임의의 텍스트를 전달하는 유일한 경로.
ASCII, 한글, 이모지, 이진 데이터 등 모든 컨텐츠를 단일 파이프라인으로 처리한다.

**Independent Test**: 앱에서 `print("hello world")` 를 입력하고 compressed mode로 전송하면,
PC에서 `java H data.txt` 를 실행했을 때 원문이 그대로 복원된다.

**Acceptance Scenarios**:

1. **Given** 키보드가 USB로 PC에 연결되고 폰이 BLE로 키보드에 연결된 상태,
   **When** 사용자가 앱에서 `console.log("test");` 를 compressed mode로 전송하면,
   **Then** PC의 활성 창에 hex 문자열이 타이핑되고, `java H` 디코더로 원문이 복원된다.
2. **Given** BLE 연결이 완료된 상태,
   **When** 사용자가 500자의 소스 코드를 붙여넣기하고 전송하면,
   **Then** 전체 텍스트가 진행률 표시와 함께 정확하게 전송되고,
   완료 후 "전송 완료" 알림이 표시된다.
3. **Given** 전송이 진행 중인 상태,
   **When** 사용자가 "중지" 버튼을 누르면,
   **Then** 전송이 즉시 중단되고 키보드는 정상 상태로 복귀한다.

---

### User Story 2 - Decoder 배포 (Direct mode, Priority: P2)

사용자는 PC에 H.java 디코더를 최초 1회 배포해야 한다. 이를 위해 앱에서 direct mode로
H.java 소스 코드를 전송하여 PC에 파일을 생성한다.

**Why this priority**: Compressed mode의 전제 조건. 디코더 없이는 hex를 원문으로 복원할 수 없다.
단, 배포는 1회성이며 이후에는 compressed mode만 사용한다.

**Independent Test**: 앱의 decoder 배포 버튼을 누르면 H.java 소스가 direct mode로 전송되고,
PC에서 `javac H.java` 가 성공한다.

**Acceptance Scenarios**:

1. **Given** BLE 연결 상태이고 앱이 direct mode 상태,
   **When** 사용자가 "decoder 전송" 버튼을 누르면,
   **Then** H.java 소스 코드가 ASCII 키코드로 전송되어 PC 텍스트 편집기에 타이핑된다.
2. **Given** PC에 H.java가 생성된 상태,
   **When** 사용자가 `javac H.java` 를 실행하면,
   **Then** 컴파일이 성공하고 `java H data.txt` 로 hex 파일을 복원할 수 있다.

---

### User Story 3 - BLE 페어링 및 연결 관리 (Priority: P3)

사용자는 최초 1회 물리적 키 조작으로 키보드와 휴대폰을 페어링한다.
이후에는 키보드를 USB로 PC에 연결하면 자동으로 BLE 광고가 시작되고,
앱에서 한 번 탭하면 연결된다.

**Why this priority**: 텍스트 전송의 전제 조건. 안정적인 BLE 연결 없이는
텍스트 전송이 불가능하다.

**Independent Test**: 키보드에서 Fn+1을 3초 이상 누르면 앱의 스캔 화면에
"TextBridge"가 나타나고, 탭하면 "연결됨" 상태로 전환된다.

**Acceptance Scenarios**:

1. **Given** 키보드가 USB로 연결되어 있고 아직 페어링된 적 없는 상태,
   **When** 사용자가 키보드에서 Fn+1을 3초 이상 누르면,
   **Then** 앱의 BLE 스캔 목록에 "TextBridge" 장치가 나타난다.
2. **Given** 앱 스캔 목록에 "TextBridge"가 표시된 상태,
   **When** 사용자가 해당 장치를 탭하면,
   **Then** BLE 본딩이 수행되고 앱에 "연결됨" 상태가 표시된다.
3. **Given** 이미 본딩된 폰과 키보드가 있고 키보드를 USB로 PC에 연결한 상태,
   **When** 앱을 열고 장치를 선택하면,
   **Then** 별도의 페어링 절차 없이 즉시 연결된다.
4. **Given** BLE 연결이 활성화된 상태에서 키보드의 USB 케이블을 뽑으면,
   **When** BLE 연결이 끊어지면,
   **Then** 앱에 "연결 끊김" 상태가 즉시 표시되고, 진행 중이던 전송이
   있었다면 중단되며 키보드는 정상 상태로 복귀한다.

---

### User Story 4 - 전송 설정 (Priority: P4)

사용자는 타이핑 속도(딜레이)를 조절할 수 있다. 설정은 앱에 저장되어 다음 실행 시에도
유지된다.

**Why this priority**: 전송 안정성과 속도 간의 균형을 사용자가 제어할 수 있게 한다.

**Independent Test**: 설정 화면에서 압축 모드 press delay를 2ms로 변경한 후 앱을 종료했다가
다시 열면 설정이 유지되어 있다.

**Acceptance Scenarios**:

1. **Given** 설정 화면,
   **When** press/release/warmup delay를 조절하면,
   **Then** 다음 전송부터 선택된 간격으로 키 입력이 주입된다.
2. **Given** 설정을 변경한 후 앱을 완전히 종료,
   **When** 앱을 다시 실행하면,
   **Then** 이전에 저장한 설정이 그대로 유지된다.

---

### User Story 5 - 전송 안정성 및 오류 복구 (Priority: P5)

대용량 텍스트(수천 자) 전송 시에도 데이터가 손실되지 않으며, BLE 연결 불안정
또는 예기치 못한 상황에서도 키보드가 비정상 상태에 빠지지 않는다.

**Independent Test**: 5,000자의 소스 코드를 전송하고, PC에서 디코더로 복원한 텍스트와
원본을 비교하여 100% 일치하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** BLE 연결 상태,
   **When** 5,000자의 소스 코드를 compressed mode로 전송하면,
   **Then** PC에서 디코더로 복원된 텍스트가 원본과 100% 일치한다.
2. **Given** 전송 중 BLE 신호가 일시적으로 약해져 ACK가 지연되는 상황,
   **When** 앱이 ACK 타임아웃을 감지하면,
   **Then** 해당 청크를 자동으로 재전송하고(최대 3회), 성공 시 전송을
   이어간다.
3. **Given** 전송 중 BLE 연결이 완전히 끊어진 상태,
   **When** 키보드가 연결 끊김을 감지하면,
   **Then** 진행 중인 HID 주입을 즉시 중단하고, 모든 눌린 키를 해제하며,
   정상 키보드 상태로 복귀한다.
4. **Given** 전송 시작 후 폰이 30초간 다음 청크를 보내지 않는 상태,
   **When** 키보드의 30초 타임아웃이 만료되면,
   **Then** 키보드가 자동으로 전송을 중단하고 대기 상태로 복귀한다.
5. **Given** 키보드가 USB 모드에서 BLE/2.4GHz 모드로 전환된 상태,
   **When** 모드 전환이 감지되면,
   **Then** TextBridge가 즉시 비활성화되고, BLE 광고를 중지하며,
   진행 중인 전송이 있었다면 중단한다.

---

### Edge Cases

- 전송 중 사용자가 키보드를 직접 누르면 해당 입력은 차단(무시)되며,
  전송 완료 후 키보드가 정상 동작으로 복귀한다.
- 전송 중단(BLE 끊김, 재전송 3회 실패) 후 재연결 시 이어보내기(resume)는
  지원하지 않으며, 전체 텍스트를 처음부터 다시 전송해야 한다.
  앱은 마지막 전송 실패 위치를 표시하여 사용자가 수동으로 텍스트를
  편집(이미 전송된 부분 삭제)할 수 있도록 돕는다.
- 빈 텍스트로 전송을 시도하면 "전송할 텍스트가 없습니다" 오류를 표시한다.
- BLE 권한이 거부된 상태에서 스캔을 시도하면 권한 요청 안내를 표시한다.
- 이미 본딩된 폰이 있는 상태에서 새 폰으로 페어링을 시도하면(Fn+1 홀드),
  기존 본딩을 교체하고 새 폰과 본딩한다.
- Compressed mode에서 입력 텍스트는 모두 UTF-8 → zlib → hex로 변환되므로,
  이모지, 한글, 한자 등 비ASCII 문자도 지원된다. 변환 불가 문자란 개념이 없다.
- Direct mode에서는 ASCII 범위를 벗어나는 문자는 건너뛰고 skippedCount를 반환한다.

## Requirements *(mandatory)*

### Functional Requirements

**BLE 연결 관리**

- **FR-001**: 키보드 펌웨어는 USB 모드 부팅 시 BLE 스택을 자동으로
  초기화하고 본딩된 기기 전용으로 광고를 시작해야 한다.
- **FR-002**: 최초 페어링은 반드시 물리적 키 조작(Fn+1, 3초 이상 홀드)을
  통해서만 가능해야 한다.
- **FR-003**: 본딩되지 않은 기기의 연결 시도는 반드시 거부해야 한다
  (Filter Accept List).
- **FR-004**: TextBridge BLE 연결은 키보드의 기존 BLE 프로필과 독립된
  별도의 Identity(ID 0)를 사용해야 한다.
- **FR-005**: 앱은 TextBridge 전용 서비스 UUID로 BLE 장치를 필터링하여
  스캔해야 한다.

**텍스트 전송**

- **FR-006**: Compressed mode에서 앱은 텍스트를 UTF-8로 인코딩 후 zlib으로
  압축하고, 결과를 lowercase hex 문자열로 인코딩하여 전송한다. hex 문자는
  0-9, a-f만 사용하므로 Shift modifier나 IME 전환이 불필요하다.
- **FR-007**: Direct mode는 ASCII 텍스트를 keycode 쌍으로 직접 변환하여 전송한다.
  이 모드는 PC에 H.java 디코더를 배포할 때만 사용한다.
- **FR-008**: 전송은 청크 단위로 이루어지며, 각 청크에 대해 키보드가 ACK를
  보낸 후에 다음 청크를 전송해야 한다(한 번에 미확인 청크 최대 1개).
- **FR-009**: 시퀀스 번호(0-255 순환)를 통해 중복 청크를 감지하고,
  이미 처리된 청크의 재수신 시 HID 주입을 건너뛰고 ACK만 재전송해야 한다.
- **FR-010**: 전송 프로토콜은 SET_DELAY → START → KEYCODE(반복) → DONE 순서를
  준수해야 하며, START 수신 전 KEYCODE를 보내면 오류로 처리해야 한다.
- **FR-011**: 전송 중 사용자가 중지를 요청하면 ABORT 명령을 보내고,
  키보드는 즉시 모든 키를 해제하고 대기 상태로 복귀해야 한다.

**설정 및 UI**

- **FR-012**: 앱은 전송 모드(compressed/direct)를 선택할 수 있어야 하며,
  기본값은 compressed이다.
- **FR-013**: 앱은 compressed mode 딜레이 설정(pressDelay, releaseDelay,
  comboDelay, warmupDelay, 각 1-255ms)을 조절할 수 있어야 한다.
- **FR-014**: 사용자 설정(mode, delays)은 앱 종료 후에도 유지되어야 한다.
- **FR-015**: 앱은 전송 진행률(현재 청크/전체 청크), 전체 키코드 수,
  압축 효율(원본 바이트/압축 바이트/hex 문자 수)을 표시해야 한다.
- **FR-016**: 앱은 "Decoder 배포" 버튼으로 H.java 소스를 direct mode로 전송하는
  기능을 제공해야 한다.

**안정성 및 안전**

- **FR-017**: 키보드 펌웨어는 전송 중 30초간 폰으로부터 응답이 없으면
  자동으로 전송을 중단하고 대기 상태로 복귀해야 한다.
- **FR-018**: BLE 연결 끊김 시 키보드는 즉시 모든 HID 키를 해제하고
  전송 상태를 초기화해야 한다.
- **FR-019**: USB 모드에서 BLE/2.4GHz 모드로 전환되면 TextBridge는 즉시
  비활성화(BLE 광고 중지, 연결 종료, 전송 중단)되어야 한다.
- **FR-020**: 전송 중 사용자의 직접 키보드 입력은 차단(무시)하고, 전송
  완료 후 정상 동작으로 복귀해야 한다.
- **FR-021**: 앱은 ACK를 동적 타임아웃(warmup + 주입 예상 시간 + 500ms 버퍼)
  동안 대기하고, 타임아웃 시 동일 청크를 최대 3회까지 자동으로 재전송해야 한다.
  3회 실패 시 전송을 중단하고 사용자에게 오류를 알린다.

### Key Entities

- **키코드 쌍 (Keycode Pair)**: HID keycode(1바이트)와 modifier(1바이트)로
  구성된 단일 키 입력 단위. compressed mode에서는 0-9/a-f 만 사용하므로
  modifier는 항상 0x00이다.
- **청크 (Chunk)**: 하나의 BLE Write 패킷에 담기는 키코드 쌍의 묶음.
  BLE MTU에 따라 8~32쌍이 포함되며, 시퀀스 번호로 식별된다.
- **전송 세션 (Transmission Session)**: SET_DELAY, START 명령부터 DONE/ABORT까지의
  하나의 전송 단위. 시퀀스 번호가 1부터 시작하며, 세션 내에서 순차 증가한다.
- **BLE 본딩 (BLE Bond)**: 키보드와 폰 사이의 암호화된 영구 연결 정보.
  최초 페어링 시 생성되며, 이후 자동 연결에 사용된다.
- **CompressionService**: UTF-8 → zlib → hex 파이프라인. 입력 텍스트를 전송
  가능한 hex 문자열로 변환한다.

## Assumptions

- PC의 키보드 레이아웃은 US ANSI (QWERTY)이다.
- PC에 Java Runtime이 설치되어 있으며, H.java 디코더를 컴파일/실행할 수 있다.
- Compressed mode에서는 PC의 입력 소스 상태(한/영)와 무관하게 동작한다.
  hex 문자(0-9, a-f)는 어떤 IME 상태에서도 동일하게 타이핑된다.
- BLE MTU 협상은 운영체제(iOS/Android)에 의해 자동으로 처리되며,
  앱이 협상된 MTU 값을 읽어 청크 크기를 결정한다.
- 키보드의 USB 연결은 안정적이며 1000Hz 폴링을 지원한다.
- 한 번에 하나의 폰만 키보드에 연결된다 (멀티 연결 미지원).

## Clarifications

### Session 2026-02-08

- Q: 앱의 ACK 타임아웃 시간 → A: 동적 타임아웃 (warmup + 주입 예상 시간 + 500ms 버퍼). 첫 청크는 warmupDelay 포함.
- Q: 전송 실패 후 이어보내기(resume) 지원 여부 → A: 미지원. 처음부터 재전송한다.

### Session 2026-02-09

- Q: macOS 한영 전환키 관련 → A: Compressed mode에서는 IME 전환 자체가 불필요. hex 문자만 전송하므로 OS 종류와 무관하다.
- Q: 전송 모드 분리 전략 → A: Compressed mode가 주요 모드. Direct mode는 H.java 디코더 배포 전용으로만 사용. TargetOS 선택은 제거됨.

### Session 2026-02-23

- Q: SET_DELAY 파라미터 수 → A: 4개 (pressDelay, releaseDelay, comboDelay, warmupDelay). toggleDelay 제거됨.
- Q: HangulService / 한글 직접 분해 지원 여부 → A: 제거됨. Compressed mode에서 모든 텍스트(한글 포함)를 hex로 처리하므로 Hangul 분해가 불필요해졌다.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 사용자가 폰에서 1,000자의 소스 코드를 compressed mode로 전송하면
  10초 이내에 PC에서 디코더로 100% 정확하게 복원된다.
- **SC-002**: 한글, 이모지, 특수문자가 혼합된 100자의 텍스트를 전송하면
  PC에서 디코더로 원문과 100% 일치하는 텍스트가 복원된다.
- **SC-003**: 5,000자 이상의 대용량 텍스트를 3회 연속 전송했을 때
  전송 실패(데이터 불일치 또는 중단)가 0건이다.
- **SC-004**: 최초 페어링부터 첫 텍스트 전송 완료까지 2분 이내에 달성
  가능하다 (신규 사용자 기준).
- **SC-005**: BLE 연결 끊김 후 키보드가 정상 타이핑 상태로 복귀하는 데
  1초 이내여야 한다.
- **SC-006**: 전송 중 30초 타임아웃 및 ABORT 명령 후 키보드에 잔존하는
  눌린 키(stuck key)가 0개여야 한다.
