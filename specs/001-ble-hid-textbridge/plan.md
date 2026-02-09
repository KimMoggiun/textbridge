# Implementation Plan: TextBridge BLE-to-USB HID 텍스트 브릿지

**Branch**: `001-ble-hid-textbridge` | **Date**: 2026-02-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-ble-hid-textbridge/spec.md`

## Summary

폐쇄망 PC에 휴대폰에서 프로그래밍 소스 코드를 전송하는 시스템.
Keychron B6 Pro 키보드(nRF52840)를 BLE-to-USB HID 브릿지로 활용하여,
Flutter 앱에서 텍스트를 (keycode, modifier) 쌍으로 변환한 뒤 BLE GATT를
통해 키보드에 전송하면, 키보드가 USB HID 키 입력으로 PC에 주입한다.
한글은 자모 분해 + 두벌식 키코드 변환으로 처리하며,
한/영 전환키(Windows: LANG1, macOS: Ctrl+Space)를 자동 삽입한다.

## Technical Context

**Language/Version**: C (Zephyr RTOS 3.x / nRF52840), Dart 3.10.8+ (Flutter), Python 3.10+ (테스트)
**Primary Dependencies**: Zephyr BLE stack, ZMK firmware (Keychron fork), flutter_blue_plus 1.32.0, provider 6.1.0, permission_handler 11.0.0
**Storage**: SharedPreferences (앱 설정), Zephyr NVS (BLE 본딩)
**Testing**: `flutter test` (Dart 단위), `python3 tools/test_phase3_protocol.py` (BLE E2E), `python3 tools/test_stress.py` (스트레스)
**Target Platform**: 펌웨어=nRF52840 (ARM Cortex-M4), 앱=iOS/Android, PC=Windows/macOS (HID 수신)
**Project Type**: Embedded + Mobile (펌웨어 + Flutter 앱)
**Performance Goals**: 1,000자 영문 10초 이내 (5ms 간격), 67 chars/sec (실측)
**Constraints**: FLASH 844KB (25% 사용), SRAM 256KB (33% 사용), BLE 단일 라디오, USB 모드 전용
**Scale/Scope**: 단일 사용자, 1:1 폰-키보드 연결, 최대 5,000자/회 전송

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 원칙 | 상태 | 근거 |
|------|------|------|
| I. 최소 변경 | PASS | TextBridge 전체 기능이 `textbridge.c` 단일 파일에 집중. ZMK 기존 파일 수정은 `ble.c` (페어링 훅 수 줄), `CMakeLists.txt` (1줄) 에만 한정 |
| II. 펌웨어-앱 역할 분리 | PASS | 펌웨어는 (keycode, modifier) 쌍만 수신하여 HID press/release 실행. 한글 분해, 키코드 변환, 한/영 전환키 삽입 모두 Flutter 앱에서 처리 |
| III. USB 전용 제약 | PASS | USB 모드에서만 BLE 광고/연결. BLE/2.4GHz 모드 전환 시 즉시 비활성화 |
| IV. 프로토콜 안전성 | PASS | ACK 기반 흐름 제어, 시퀀스 번호 중복 감지, 30초 세션 타임아웃, 전송 중 키보드 입력 차단 |
| V. 보안 기본값 | PASS | Filter Accept List, 물리적 키 페어링, GATT 암호화 Write, BT_ID_DEFAULT 분리 |
| VI. 단계별 검증 | PASS | Phase 1~5 각 단계 성공 기준 충족 후 진행. 자동화 테스트 스크립트 구비 |
| VII. 단순성 우선 | PASS | 단일 모듈, Provider 최소 상태 관리, 추상화 계층 없음 |

**게이트 결과: ALL PASS** — 위반 사항 없음.

## Project Structure

### Documentation (this feature)

```text
specs/001-ble-hid-textbridge/
├── plan.md              # 이 파일
├── spec.md              # 기능 명세
├── research.md          # 한글 분해 + 두벌식 매핑 기술 레퍼런스
├── data-model.md        # 엔티티 정의 (KeycodePair, Chunk, Session 등)
├── quickstart.md        # 빌드/플래시/테스트 가이드
├── contracts/
│   └── ble-protocol.md  # BLE GATT 프로토콜 명세
├── checklists/
│   └── requirements.md  # 요구사항 체크리스트
└── tasks.md             # 작업 목록 (T001~T029 + HF-001, HF-002)
```

### Source Code (repository root)

```text
zmk_keychron/app/
├── src/
│   ├── textbridge.c          # TextBridge 핵심 모듈 (GATT, 프로토콜, HID 주입)
│   ├── ble.c                 # BLE 관리 (페어링 훅 최소 수정)
│   └── CMakeLists.txt        # 빌드 설정 (textbridge.c 추가 1줄)
├── include/zmk/
│   └── textbridge.h          # TextBridge 공개 API (zmk_textbridge_pair_start 등)
└── boards/shields/keychron/
    └── b6/us/keychron_b6_us.conf  # Kconfig (BLE 설정)

flutter_app/textbridge_app/
├── lib/
│   ├── main.dart             # 앱 진입점
│   ├── models/
│   │   ├── protocol.dart     # 프로토콜 정의
│   │   └── connection_state.dart
│   ├── screens/
│   │   ├── home_screen.dart  # 메인 UI (텍스트 입력 + 전송)
│   │   ├── scan_screen.dart  # BLE 스캔 화면
│   │   └── settings_screen.dart
│   └── services/
│       ├── ble_service.dart          # BLE GATT 통신
│       ├── keycode_service.dart      # ASCII + 한글 → HID 키코드 변환
│       ├── hangul_service.dart       # 한글 음절 분해 + 두벌식 매핑
│       ├── settings_service.dart     # 설정 영속화
│       └── transmission_service.dart # 청크 전송 + ACK 흐름 제어
└── test/
    ├── keycode_service_test.dart
    ├── hangul_service_test.dart
    └── settings_service_test.dart

tools/
├── enter_dfu.py              # DFU 부트로더 진입
├── tb_pair.py                # VIA 기반 페어링 유틸
├── test_phase2_ble.py        # BLE 연결 테스트
├── test_phase3_protocol.py   # 프로토콜 E2E 테스트 (10/10)
├── test_phase5_hangul.py     # 한글 E2E 테스트
└── test_stress.py            # 스트레스 테스트
```

**Structure Decision**: Embedded + Mobile 하이브리드 프로젝트.
펌웨어(`zmk_keychron/`)와 앱(`flutter_app/`)이 독립 빌드 체인을 가지며,
`tools/`에 Python 기반 E2E 테스트가 위치. 표준 웹/모바일 템플릿과 다르게
하드웨어 의존 구조를 반영한다.

## Implementation Phases

### Phase 1: HID 주입 기초 (완료)

- USB 모드에서 HID 키코드 직접 주입 검증
- `zmk_hid_keyboard_press/release` + `zmk_endpoints_send_report` 파이프라인
- PC에서 'a' 키 출력 확인

### Phase 2: BLE GATT 서비스 (완료)

- TextBridge GATT 서비스 등록 (커스텀 UUID)
- TX (Write Without Response) + RX (Notify) 특성
- BLE 광고, 연결, 페어링 (Fn+1 홀드)
- BT_ID_DEFAULT(0) 분리, Filter Accept List

### Phase 3: 프로토콜 + 흐름 제어 (완료)

- START/KEYCODE/DONE/ABORT 명령 파서
- ACK 기반 흐름 제어, 시퀀스 번호 중복 감지
- 30초 세션 타임아웃, 전송 중 키보드 입력 차단
- BLE 연결 끊김 시 HID 클리어 + 상태 초기화

### Phase 4: Flutter 앱 (완료)

- BLE 스캔/연결 (flutter_blue_plus)
- ASCII 키코드 변환 (KeycodeService)
- 청크 분할 + ACK 대기 + 재전송 (TransmissionService)
- 전송 진행률 UI, 설정 화면 (OS/속도)
- Provider 기반 상태 관리

### Phase 5: 한글 + 안정성 (완료)

- 한글 음절 분해 (HangulService): 초성/중성/종성
- 두벌식 키코드 매핑: 쌍자음(Shift), 복합모음, 겹받침 확장
- 한/영 전환키 자동 삽입 (Windows: 0x90, macOS: Ctrl+Space)
- **토글키 별도 청크 분리**: 토글키를 단독 청크(1개 키코드)로 전송하고 ACK 수신 후 다음 청크 전송. OS 입력기 전환 완료를 ACK 왕복으로 보장
- 연속 구간 병합으로 전환 횟수 최소화
- 5,000자 스트레스 테스트

### 미해결 잔존 이슈

| 이슈 | 영향 | 상태 |
|------|------|------|
| Flutter `keycode_service.dart` macOS 토글키가 아직 0xE7 (Right GUI) | 앱에서 macOS 대상 전송 시 한/영 전환 실패 | 수정 필요 |
| 토글키가 다른 키코드와 같은 청크에 포함되어 OS 전환 타이밍 불안정 | 순차 테스트 시 한영 전환 실패 | HF-003으로 수정 예정 |
| 스트레스 테스트 3회 연속 중 3번째 실패 (ACK 타임아웃 @ 청크 195) | 대용량 연속 전송 신뢰성 | 원인 조사 필요 |
| macOS BLE GATT 캐시 (CCC 상태) | 비정상 종료 후 재연결 시 무응답 | 수동 BT 토글 필요 |

## Complexity Tracking

> 위반 사항 없음 — 모든 헌법 원칙 준수.
