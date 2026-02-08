# Tasks: TextBridge BLE-to-USB HID 텍스트 브릿지

**Input**: Design documents from `/specs/001-ble-hid-textbridge/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/ble-protocol.md, quickstart.md

**Tests**: BLE 없이 자동화 가능한 범위:
- **Dart unit test**: KeycodeService (ASCII/한글 변환), HangulService (음절 분해), 프로토콜 패킷 직렬화, SettingsService
- **Python E2E**: 펌웨어 프로토콜 검증 (`test_phase3_protocol.py`), 스트레스 테스트 (`test_stress.py`)
- **수동 검증 (실제 폰)**: BLE 스캔/연결, MTU 협상, 앱→키보드 E2E

Mock 미사용. BLE 의존 로직은 실제 폰에서만 검증.

**Organization**: 태스크는 User Story 단위로 그룹화. 각 스토리를 독립적으로 구현/검증 가능.

**현재 상태**: Phase 1-3(펌웨어)과 Phase 4(Flutter 앱, ASCII 기본)가 이미 구현됨.
이 태스크 목록은 **미완성 기능 완성**에 집중함.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 실행 가능 (다른 파일, 의존성 없음)
- **[Story]**: 해당 User Story (예: US1, US2, US3)
- 모든 태스크에 정확한 파일 경로 포함

---

## Phase 1: Setup (공유 인프라)

**Purpose**: 신규 의존성 추가 및 프로젝트 구조 준비

- [x] T001 `shared_preferences` 의존성을 `flutter_app/textbridge_app/pubspec.yaml`에 추가하고 `flutter pub get` 실행
- [x] T002 [P] `flutter_app/textbridge_app/lib/models/connection_state.dart`에 `transmitting` 상태의 `label` 값이 정확한지 확인하고, 누락된 상태가 있으면 추가

---

## Phase 2: Foundational (선행 필수)

**Purpose**: 모든 User Story에서 공유하는 핵심 인프라. 이 페이즈 완료 전 US 작업 불가

**⚠️ CRITICAL**: US 작업은 이 페이즈 완료 후 시작

- [x] T003 `flutter_app/textbridge_app/lib/services/settings_service.dart` 신규 생성 — `SettingsService` (ChangeNotifier) 구현. `SharedPreferences`를 사용하여 `targetOS` (enum: windows/macOS, 기본값 windows), `typingSpeed` (enum: safe 10ms / normal 5ms / fast 1ms, 기본값 normal), `lastDeviceAddress` (String?) 영속화. `load()`, `setTargetOS()`, `setTypingSpeed()`, `setLastDeviceAddress()` 메서드 제공. data-model.md의 AppSettings 엔티티 참조
- [x] T004 `flutter_app/textbridge_app/lib/main.dart`에 `SettingsService`를 Provider로 등록. `ChangeNotifierProvider`로 추가하고 `create`에서 `load()` 호출
- [x] T005 [P] `flutter_app/textbridge_app/test/settings_service_test.dart` 신규 생성 — SettingsService 단위 테스트: targetOS 기본값(windows) 확인, 변경 후 값 반영, typingSpeed 기본값(normal) 확인, 변경 후 값 반영, lastDeviceAddress 저장/조회. `SharedPreferences.setMockInitialValues({})` 사용

**Checkpoint**: 설정 영속화 인프라 준비 완료. 단위 테스트 통과

---

## Phase 3: User Story 1 - 영문/ASCII 텍스트 전송 (Priority: P1) 🎯 MVP

**Goal**: 폰에서 영문 소스 코드를 전송하면 PC에 정확히 타이핑됨. 기존 구현 완성.

**Independent Test**: 앱에서 `print("hello world")`를 입력하고 전송 → PC에 동일 문자열 출력

**현재 상태**: ASCII 전송 기본 동작 완료. 설정 반영(속도), 진행률 표시 강화, 에러 표시 개선 필요.

### Tests for User Story 1

- [x] T006 [P] [US1] `flutter_app/textbridge_app/test/keycode_service_test.dart` 신규 생성 — ASCII 변환 단위 테스트: 소문자(`a`→0x04), 대문자(`A`→0x04+Shift), 숫자(`0-9`), 특수문자(`!@#$%` 등 Shift 조합), 변환 불가 문자 skippedCount 검증, `chunkKeycodes()` MTU 기반 분할 검증 (MTU 23→청크 2개, MTU 64→청크 1개 등)
- [x] T007 [P] [US1] `flutter_app/textbridge_app/test/protocol_test.dart` 신규 생성 — 프로토콜 패킷 직렬화 단위 테스트: `makeStart()` 바이트 구조 (CMD=0x01, totalKeycodes, totalChunks), `makeDone()`/`makeAbort()` 패킷, `KeycodeChunk` 직렬화 (seq, keycode count, payload), contracts/ble-protocol.md의 바이트 레이아웃과 일치 검증

### Implementation for User Story 1

- [x] T008 [US1] `flutter_app/textbridge_app/lib/services/transmission_service.dart` 수정 — 생성자에 `SettingsService` 의존성 추가. `sendText()` 내 ACK 타임아웃을 하드코딩 5초에서 500ms(FR-025 명세)로 변경. 재전송 간 대기시간을 1초에서 100ms로 변경
- [x] T009 [US1] `flutter_app/textbridge_app/lib/services/keycode_service.dart` 수정 — `textToKeycodes()` 반환값과 함께 변환 불가 문자 수를 리턴하도록 변경 (FR-020). 함수 시그니처: `({List<KeycodePair> keycodes, int skippedCount}) textToKeycodes(String text)` 형태의 record 반환
- [x] T010 [US1] `flutter_app/textbridge_app/lib/screens/home_screen.dart` 수정 — 전송 전 변환 불가 문자 수를 표시 (FR-020). 빈 텍스트 전송 시 "전송할 텍스트가 없습니다" 스낵바 표시. 전송 진행률에 예상 소요 시간 표시 (FR-019, `SettingsService.typingSpeed` 기반 계산)
- [x] T011 [US1] `flutter_app/textbridge_app/lib/screens/home_screen.dart` 수정 — 전송 실패 시 실패 위치(마지막 성공 청크/키코드)를 표시하여 사용자가 수동 편집할 수 있도록 지원 (Edge Case: 이어보내기 미지원, 실패 위치 표시)

**Checkpoint**: 영문 ASCII 전송이 설정된 속도와 500ms ACK 타임아웃으로 완전히 동작. 단위 테스트 통과

---

## Phase 4: User Story 2 - BLE 페어링 및 연결 관리 (Priority: P2)

**Goal**: 물리적 키 조작으로 페어링, 자동 재연결, 연결 상태 실시간 표시

**Independent Test**: Fn+1 3초 홀드 → 앱 스캔에 "B6 TextBridge" 표시 → 탭 → "연결됨"

**현재 상태**: 기본 스캔/연결/끊김 감지 구현됨. 자동 재연결, 마지막 기기 저장 미구현.

**검증 방법**: BLE 의존 — 실제 폰에서 수동 검증. 자동화 테스트 없음.

### Implementation for User Story 2

- [x] T012 [US2] `flutter_app/textbridge_app/lib/services/ble_service.dart` 수정 — 연결 성공 시 `SettingsService.setLastDeviceAddress()`로 기기 주소 저장. 앱 시작 시 `lastDeviceAddress`가 있으면 자동 연결 시도 추가
- [x] T013 [US2] `flutter_app/textbridge_app/lib/screens/home_screen.dart` 수정 — BLE 연결 끊김 시 진행 중인 전송이 있었다면 "연결 끊김으로 전송 중단" 알림 표시 (Acceptance Scenario 4). 연결 상태 badge에 신호 강도(RSSI) 표시 고려
- [x] T014 [US2] `flutter_app/textbridge_app/lib/screens/home_screen.dart` 수정 — `_ScanSheet` 내에서 이미 본딩된 기기가 목록 상단에 표시되도록 정렬. BLE 권한 거부 시 설정 화면으로 이동하는 버튼 추가 (Edge Case: 권한 거부)

**Checkpoint**: 페어링, 자동 재연결, 연결 상태 표시 완전 동작. 실제 폰+키보드로 수동 검증

---

## Phase 5: User Story 3 - 한글 텍스트 전송 (Priority: P3)

**Goal**: 한글 음절을 자모로 분해 → 두벌식 키코드 변환 → 한영 전환키 자동 삽입

**Independent Test**: `// 안녕하세요 테스트` 전송 → PC에 동일한 한글+영문 혼합 텍스트 출력

### Tests for User Story 3

- [x] T015 [P] [US3] `flutter_app/textbridge_app/test/hangul_service_test.dart` 신규 생성 — 한글 분해 단위 테스트: 기본 음절(`가`, `나`, `안`), 쌍자음(`까`, `따`), 복합모음(`왕`, `웨`), 겹받침(`값`, `앉`, `왂`), 전체 분해 결과가 research.md의 참조 데이터와 일치하는지 검증
- [x] T016 [P] [US3] `flutter_app/textbridge_app/test/keycode_service_test.dart` 확장 — 한글+영문 혼합 텍스트 변환 테스트 추가: `Hello 안녕 World 세계` → 한영 전환키 삽입 위치와 키코드 시퀀스 검증. Windows/macOS 각각의 전환키(0x90 vs 0xE7) 검증

### Implementation for User Story 3

- [x] T017 [US3] `flutter_app/textbridge_app/lib/services/hangul_service.dart` 신규 생성 — `HangulService` 클래스 구현. research.md 기반으로: (1) `decomposeHangul(int codepoint)` → 초성/중성/종성 인덱스 반환 (수학 공식: `code = cp - 0xAC00; cho = code/588; jung = (code%588)/28; jong = code%28`), (2) `isHangulSyllable(int codepoint)` → 0xAC00~0xD7A3 범위 검사, (3) 초성/중성/종성 → 두벌식 키코드 매핑 테이블 (research.md Section 3 참조), (4) 복합모음 확장 (7종, research.md Section 4), (5) 겹받침 확장 (11종, research.md Section 5), (6) 쌍자음 Shift modifier 처리 (ㄲ=R+Shift, ㄸ=E+Shift 등), (7) `syllableToKeycodes(int codepoint)` → `List<KeycodePair>` 반환
- [x] T018 [US3] `flutter_app/textbridge_app/lib/services/keycode_service.dart` 수정 — `textToKeycodes()`를 확장하여 한글 음절 감지 시 `HangulService.syllableToKeycodes()` 호출. 한영 전환키 자동 삽입 로직 추가 (FR-014, FR-015): 텍스트를 영문/한글 구간으로 세그먼트화하고, 구간 전환 시 `SettingsService.targetOS`에 따라 한영키(Windows: 0x90, macOS: 0xE7) 삽입. 연속 동일 언어 구간 병합으로 전환 횟수 최소화
- [x] T019 [US3] `flutter_app/textbridge_app/lib/screens/home_screen.dart` 수정 — 한글 포함 텍스트의 문자 수 카운트를 정확하게 표시 (한글 음절은 1문자이지만 여러 키코드로 변환됨을 반영). `_CharCount` 위젯에 "XX 키코드로 변환됨" 정보 추가

**Checkpoint**: 한글+영문 혼합 텍스트가 PC에서 정확히 재현됨. 한영 전환 자동 처리. 단위 테스트 통과

---

## Phase 6: User Story 4 - 전송 설정 및 OS 선택 (Priority: P4)

**Goal**: 대상 OS, 타이핑 속도 설정 → 앱 재시작 후 유지

**Independent Test**: 설정에서 OS=Windows, 속도=빠름 → 앱 종료 → 재시작 → 설정 유지 확인

### Implementation for User Story 4

- [x] T020 [US4] `flutter_app/textbridge_app/lib/screens/settings_screen.dart` 수정 — "대상 OS" 섹션 추가: SegmentedButton으로 Windows/macOS 선택 (FR-016). "타이핑 속도" 섹션 추가: SegmentedButton으로 안전(10ms)/보통(5ms)/최대(1ms) 선택 (FR-017). `SettingsService` Consumer로 양방향 바인딩. 현재 설정이 전송에 미치는 영향 설명 텍스트 추가
- [x] T021 [US4] `flutter_app/textbridge_app/lib/services/transmission_service.dart` 수정 — HID 주입 타이밍에 `SettingsService.typingSpeed` 반영. 현재 하드코딩된 `TB_HID_DELAY_MS`(5ms)를 설정값으로 대체. 주의: 타이밍은 펌웨어 측이므로, 앱에서는 chunk 전송 간격에 반영하거나 펌웨어에 속도 정보를 START 패킷에 포함하는 방안 검토. (현재 펌웨어는 5ms 고정이므로 앱에서 chunk 크기를 조절하여 간접 제어)

**Checkpoint**: OS와 속도 설정이 전송에 반영되고, 앱 재시작 후 유지

---

## Phase 7: User Story 5 - 전송 안정성 및 오류 복구 (Priority: P5)

**Goal**: 5,000자 전송 100% 정확, 타임아웃 자동 복구, 연결 끊김 시 안전 복귀

**Independent Test**: 5,000자 소스 코드 전송 → PC 수신 텍스트와 원본 100% 일치

### Implementation for User Story 5

- [x] T022 [US5] `zmk_keychron/app/src/textbridge.c` 수정 — 30초 세션 타임아웃 구현 (FR-021). `k_work_delayable`로 타이머 추가: START 수신 시 시작, 각 KEYCODE 수신 시 리셋, DONE/ABORT 시 취소. 타임아웃 만료 시 `tb_cleanup_transmission()` 호출 후 IDLE 복귀
- [x] T023 [US5] `zmk_keychron/app/src/textbridge.c` 수정 — 전송 중 사용자 직접 키보드 입력 차단 (FR-024). `tb_transmitting == true`일 때 키 이벤트를 무시하는 훅 추가. ZMK의 키 이벤트 체인에서 인터셉트하는 방법 조사 필요 (`zmk_listener` 또는 `zmk_event_manager` 활용)
- [x] T024 [P] [US5] `zmk_keychron/app/src/textbridge.c` 수정 — USB 모드 전환 감지 (FR-023). `zmk_endpoint_changed` 이벤트 리스너 등록: USB→BLE/2.4GHz 전환 시 `tb_stop_advertising()`, `tb_cleanup_transmission()`, BLE 연결 종료 실행. 펌웨어 CLAUDE.md 참조하여 이벤트 구독 방법 확인
- [x] T025 [P] [US5] `tools/test_stress.py` 신규 생성 — 대용량 전송 스트레스 테스트 스크립트. (1) 5,000자 영문 소스 코드 전송 후 PC 수신 텍스트와 비교 (SC-003), (2) 5회 연속 전송 실행, (3) 전송 속도 측정 (chars/sec), (4) `pynput`으로 PC 입력 캡처하여 원본과 diff 비교. 기존 `tools/test_phase3_protocol.py`의 BLE 연결 로직 재사용

**Checkpoint**: 대용량 전송 안정성, 타임아웃 복구, 모드 전환 안전성 검증 완료

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 여러 User Story에 걸친 개선사항

- [x] T026 [P] `flutter_app/textbridge_app/lib/screens/home_screen.dart` 수정 — 전송 완료/실패 시 소리 또는 진동 피드백 추가. 전체 UX 검토 및 한글/영문 혼합 텍스트에 대한 미리보기 기능 검토
- [x] T027 [P] `tools/test_phase3_protocol.py` 수정 — 한글 테스트 케이스 추가 (`--test hangul`): `안녕하세요`, `Hello 안녕 World`, `까닭없이 왂뷁` 등. 기존 프로토콜 테스트와 통합
- [x] T028 [P] `tools/test_phase5_hangul.py` 신규 생성 — 한글 전송 E2E 테스트. (1) 순수 한글 텍스트, (2) 한영 혼합, (3) 쌍자음/복합모음/겹받침 포함 텍스트, (4) PC에서 `pynput`으로 캡처한 결과와 원본 비교
- [x] T029 quickstart.md 검증 — 모든 빌드/플래시/테스트 단계를 실행하여 문서 정확성 확인. 한글 테스트 케이스 추가된 내용 반영하여 `specs/001-ble-hid-textbridge/quickstart.md` 업데이트

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 의존성 없음 — 즉시 시작
- **Foundational (Phase 2)**: Phase 1 완료 필요 — **모든 US 차단**
- **US1 (Phase 3)**: Phase 2 완료 필요 — 다른 US와 독립
- **US2 (Phase 4)**: Phase 2 완료 필요 — US1과 독립 (병렬 가능)
- **US3 (Phase 5)**: Phase 2 완료 필요 — US1과 독립 (병렬 가능)
- **US4 (Phase 6)**: Phase 2 완료 필요 — US3 이후 권장 (한영키가 OS 설정에 의존)
- **US5 (Phase 7)**: Phase 2 완료 필요 — US1 이후 권장 (전송 안정성은 기본 전송에 의존)
- **Polish (Phase 8)**: US3, US5 완료 필요

### User Story Dependencies

- **US1 (P1)**: Phase 2 완료 후 즉시 시작 가능 — 다른 US 의존 없음
- **US2 (P2)**: Phase 2 완료 후 즉시 시작 가능 — US1과 병렬 가능
- **US3 (P3)**: Phase 2 완료 후 시작 가능 — US1/US2와 병렬 가능. `keycode_service.dart` 수정이 US1의 T009와 충돌할 수 있으므로 US1 완료 후 권장
- **US4 (P4)**: Phase 2 완료 후 시작 가능 — `SettingsService`를 사용하므로 Phase 2 필수. US3의 한영키가 OS 설정에 의존하므로 US3과 동시 또는 이후 권장
- **US5 (P5)**: Phase 2 완료 후 시작 가능 — 펌웨어 태스크(T022-T024)는 독립 실행 가능

### Within Each User Story

- 테스트(있으면) → 모델 → 서비스 → UI 순서
- 서비스 변경 전 의존 서비스 확인
- US 완료 후 다음 우선순위로 이동

### Parallel Opportunities

- T001, T002: Setup 태스크 병렬 실행 가능
- T006, T007: US1 테스트 병렬 실행 가능
- T015, T016: US3 테스트 병렬 실행 가능
- T022, T023, T024: US5 펌웨어 태스크 중 T024는 T022/T023과 병렬 가능
- T026, T027, T028: Polish 태스크 모두 병렬 가능
- US1과 US2: Phase 2 완료 후 병렬 실행 가능

---

## Test Strategy Summary

### 자동화 테스트 (BLE 불필요)

| 태스크 | 유형 | 대상 |
|--------|------|------|
| T005 | Dart unit | SettingsService 영속화 |
| T006 | Dart unit | KeycodeService ASCII 변환 |
| T007 | Dart unit | 프로토콜 패킷 직렬화 |
| T015 | Dart unit | HangulService 음절 분해 |
| T016 | Dart unit | 한글+영문 혼합 키코드 변환 |
| T025 | Python E2E | 펌웨어 대용량 스트레스 테스트 |
| T027 | Python E2E | 펌웨어 한글 프로토콜 테스트 |
| T028 | Python E2E | 펌웨어 한글 HID 주입 E2E |

### 수동 검증 (실제 폰 필요)

| 태스크 | 대상 |
|--------|------|
| T012 | 자동 재연결 |
| T013 | 연결 끊김 알림 |
| T014 | 스캔 목록 정렬, 권한 처리 |
| US1 E2E | 앱→키보드→PC 전체 흐름 |
| US3 E2E | 한글 앱→키보드→PC 전체 흐름 |

---

## Parallel Example: User Story 3

```bash
# US3 테스트를 먼저 병렬로 작성:
Task: "T015 - hangul_service_test.dart 신규 생성"
Task: "T016 - keycode_service_test.dart 한글 확장"

# 테스트 실패 확인 후, 서비스 구현:
Task: "T017 - hangul_service.dart 신규 생성"
Task: "T018 - keycode_service.dart 한글 확장"

# 서비스 완료 후 UI:
Task: "T019 - home_screen.dart 한글 표시"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup 완료
2. Phase 2: Foundational 완료 (SettingsService)
3. Phase 3: User Story 1 완료 (ASCII 전송 완성)
4. **STOP and VALIDATE**: 500ms ACK 타임아웃, 변환 불가 문자 표시, 진행률 확인
5. Dart unit test (T006, T007) + 기존 `test_phase3_protocol.py`로 E2E 검증

### Incremental Delivery

1. Setup + Foundational → 설정 인프라 준비
2. US1 → ASCII 전송 완성 → Dart unit test + Python E2E 검증 (**MVP!**)
3. US2 → 자동 재연결 추가 → 실제 폰 수동 검증
4. US3 → 한글 지원 → Dart unit test + Python E2E 검증
5. US4 → OS/속도 설정 → 다양한 환경 대응
6. US5 → 안정성 강화 → Python 스트레스 테스트
7. Polish → 테스트 도구, UX 개선

### 권장 실행 순서 (단일 개발자)

Phase 1 → Phase 2 → Phase 3 (US1) → Phase 4 (US2) → Phase 5 (US3) → Phase 6 (US4) → Phase 7 (US5) → Phase 8

---

## Hotfix Log

### HF-001: BLE Identity 필터링 버그 수정 (2026-02-08)

**파일**: `zmk_keychron/app/src/textbridge.c`

**증상**: 프로토콜 테스트 10/10 실패. BLE 연결 성공(MTU=65), GATT 서비스 발견 성공, 하지만 START → READY 응답 없음.

**근본 원인**: `tb_connected()` 콜백이 `info.id != BT_ID_DEFAULT`로 필터링. Zephyr GATT 서비스는 identity-agnostic이므로 클라이언트가 identity 0이 아닌 경로로 연결해도 GATT write는 동작하지만, `tb_conn`이 NULL 상태여서 `tb_send_response()`가 무응답.

**수정**: `tb_tx_write_cb()`에서 `tb_conn`이 NULL이면 write callback의 `conn` 파라미터를 채용:
```c
if (!tb_conn && conn) {
    tb_conn = bt_conn_ref(conn);
}
```

**검증**: 수정 후 프로토콜 테스트 10/10 통과.

### HF-002: macOS 한글 HID 주입 수정 (2026-02-08)

**파일**: `zmk_keychron/app/src/textbridge.c`, `tools/test_phase3_protocol.py`

**증상**: macOS에서 한영 혼합 텍스트("Hello 안녕 World 세계") 전송 시 "Hello dㅏㄴ녕 World 섹P" 출력. 두 가지 문제:
1. macOS가 단독 Shift HID 리포트를 CJK→English 전환으로 해석
2. Ctrl+Space를 별도 리포트로 전송 시 입력기 전환 불안정

**수정**:
1. **Atomic modifier+key**: modifier와 key를 같은 HID 리포트에 포함 (register_mods + keyboard_press + send_report)
2. **Toggle delay 100ms**: Ctrl+Space 이후 macOS 입력기 전환 대기 (`TB_TOGGLE_DELAY_MS`)
3. **Ctrl+Space 감지**: `kc == 0x2C && mod == 0x01` 조건 추가

**Python 테스트 도구 수정**:
- `--os mac` 옵션 추가, `TOGGLE_MAC = (0x2C, 0x01)` (Ctrl+Space)
- `text_to_keycodes()` 한글 지원 (`hangul_to_keycodes()` 위임)

**검증**: "자모 닭 까닭없이 값", "Hello 안녕 World 세계" 모두 macOS 터미널에서 정확히 출력.

---

## Verification Results (2026-02-08)

### 펌웨어 빌드
- FLASH: 216,756 B / 844 KB (25.08%)
- SRAM: 87,688 B / 256 KB (33.45%)

### BLE 프로토콜 테스트 (10/10 통과)

```
[PASS] single_a          단일 키 'a'
[PASS] shift_A            대문자 'A' (Shift)
[PASS] hello              "hello world" (11키, 2청크)
[PASS] multi_chunk        "abcdefghijklmnop" (16키, 2청크)
[PASS] duplicate          중복 seq 감지 (ACK 응답, HID 미주입)
[PASS] abort              ABORT 명령으로 전송 중단
[PASS] special            "Hello, World! 123" (특수문자+숫자)
[PASS] hangul             '안녕하세요' (순수 한글, 14키)
[PASS] hangul_mixed       'Hello 안녕 World 세계' (한영 혼합, 27키)
[PASS] hangul_complex     '까닭없이' (쌍자음/겹받침, 14키)
```

### Dart 단위 테스트 (60+ 통과)
- `keycode_service_test.dart`: ASCII/한글 키코드 변환, 혼합 텍스트, emoji 처리
- `hangul_service_test.dart`: 한글 음절 분해, 두벌식 매핑, 쌍자음/복합모음/겹받침
- `settings_service_test.dart`: 설정 영속화 (TargetOS, TypingSpeed)

### 실제 HID 출력 검증 — macOS (2026-02-08)

| 텍스트 | 결과 | 비고 |
|--------|------|------|
| `자모 닭 까닭없이 값` | PASS | 쌍자음, 겹받침 정확 |
| `Hello 안녕 World 세계` | PASS | 한영 전환 4회, Ctrl+Space |

### 스트레스 테스트 (2026-02-08)

| 테스트 | 결과 | 비고 |
|--------|------|------|
| 5000자 단일 전송 | PASS | 67 chars/sec |
| 5000자 연속 3회 | 2/3 PASS | 3회차 chunk 195/625에서 ACK timeout |

---

## Notes

- [P] = 다른 파일, 의존성 없음 → 병렬 가능
- [Story] = 해당 User Story 매핑 (추적성)
- 각 US는 독립적으로 완료/검증 가능
- 체크포인트에서 정지하여 스토리 독립 검증
- 펌웨어 변경(T022-T024)은 빌드+플래시 필요 → quickstart.md 참조
- 커밋: 태스크 또는 논리적 그룹 단위
- BLE 관련 기능은 실제 폰에서만 수동 검증 (동글/에뮬레이터 불필요)
- T014의 `scan_screen.dart`는 실제로 `home_screen.dart` 내 `_ScanSheet`에 위치
