# Implementation Plan: TextBridge BLE-to-USB HID 텍스트 브릿지

**Branch**: `001-ble-hid-textbridge` | **Date**: 2026-02-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-ble-hid-textbridge/spec.md`

## Summary

폐쇄망 회사 PC에 휴대폰에서 프로그래밍 소스 코드를 전송하는 BLE-to-USB HID
브릿지 시스템. Keychron B6 Pro 키보드(nRF52840/ZMK)를 중간 매체로 사용하여,
폰(Flutter) → BLE GATT → 키보드 펌웨어 → USB HID → PC 경로로 텍스트를
전달한다.

현재 Phase 1-3(펌웨어)과 Phase 4(Flutter 앱, ASCII) 기본 구현이 완료되어
있으며, 이 계획은 미완성 기능(한글 지원, 설정 영속화, 안정성 강화, USB 모드
감지 등)을 완성하여 전체 명세(Phase 1-5)를 달성하는 것을 목표로 한다.

## Technical Context

**Language/Version**: C (Zephyr RTOS 3.x / nRF52840), Dart 3.10.8+ (Flutter 3.10.8+), Python 3.10+ (테스트 도구)
**Primary Dependencies**: Zephyr BLE stack, ZMK firmware (Keychron fork), flutter_blue_plus 1.32.0, provider 6.1.0, permission_handler 11.0.0
**Storage**: Zephyr Settings subsystem (BLE 본딩), SharedPreferences (Flutter 앱 설정)
**Testing**: Python 스크립트 (bleak, hidapi, pynput) — 자동화 통합 테스트, Flutter widget/unit tests
**Target Platform**: nRF52840 (ARM Cortex-M4), iOS 15+ / Android 12+, macOS/Windows (대상 PC)
**Project Type**: Embedded firmware + Mobile app (2-component 시스템)
**Performance Goals**: 150+ chars/sec (5ms 간격), 400+ chars/sec (1ms 간격)
**Constraints**: nRF52840 단일 라디오 (USB 모드 전용), FLASH 25%/SRAM 33% 사용률, BLE MTU 23~244바이트
**Scale/Scope**: 1:1 연결 (폰 1대 : 키보드 1대), 최대 5,000자 단일 전송, 한글 11,172 음절 지원

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | 원칙 | 상태 | 검증 |
|---|------|------|------|
| I | 최소 변경 원칙 | PASS | 펌웨어 변경은 `textbridge.c`에 집중. `ble.c`(2곳), `launcher.c`(1곳), `CMakeLists.txt`(1줄)만 수정. 추가 ZMK 파일 변경 없음 |
| II | 펌웨어-앱 역할 분리 | PASS | 한글 자모 분해, 키코드 변환, OS별 한영키 삽입 모두 Flutter 앱에서 처리. 펌웨어는 (keycode, modifier) 쌍만 수신 |
| III | USB 전용 제약 | PASS | USB 모드 전용 동작. FR-023에서 모드 전환 시 비활성화 명시. `zmk_endpoint_changed` 이벤트 구독으로 구현 |
| IV | 프로토콜 안전성 | PASS | ACK 기반 흐름 제어(FR-007), 중복 감지(FR-008), 30초 타임아웃(FR-021), ABORT(FR-010) 모두 명세됨 |
| V | 보안 기본값 | PASS | Filter Accept List(FR-003), 물리적 페어링(FR-002), BLE Identity 분리(FR-004) 명세됨 |
| VI | 단계별 검증 | PASS | 기존 Phase 1-3 통과. 본 계획은 미완성 기능 완성 후 Phase 4-5 검증을 포함 |
| VII | 단순성 우선 | PASS | 이어보내기 미지원(YAGNI), 단일 모듈 유지, Provider 최소 상태 관리 |

**GATE RESULT: ALL PASS** — Phase 0 진행 가능.

## Project Structure

### Documentation (this feature)

```text
specs/001-ble-hid-textbridge/
├── plan.md              # 이 파일
├── spec.md              # 기능 명세
├── research.md          # Phase 0: 한글 분해 알고리즘, 두벌식 매핑 조사
├── data-model.md        # Phase 1: 엔티티 모델, 상태 전이
├── quickstart.md        # Phase 1: 빌드/플래시/테스트 가이드
├── contracts/           # Phase 1: BLE GATT 프로토콜 명세
│   └── ble-protocol.md
├── checklists/
│   └── requirements.md  # 품질 체크리스트
└── tasks.md             # Phase 2: 태스크 목록 (/speckit.tasks)
```

### Source Code (repository root)

```text
zmk_keychron/app/
├── src/
│   ├── textbridge.c       ← TextBridge 핵심 모듈 (기존 + 확장)
│   ├── ble.c              ← BLE 통합 훅 (기존 수정, 추가 변경 없음)
│   └── launcher/
│       └── launcher.c     ← VIA 훅 (기존 수정, 추가 변경 없음)
├── CMakeLists.txt         ← 빌드 설정 (변경 없음)
└── boards/                ← 보드/키맵 (변경 없음)

flutter_app/textbridge_app/
├── lib/
│   ├── main.dart
│   ├── models/
│   │   ├── protocol.dart         ← 프로토콜 상수/구조체 (기존)
│   │   └── connection_state.dart ← BLE 상태 enum (기존)
│   ├── services/
│   │   ├── ble_service.dart          ← BLE 연결 관리 (기존)
│   │   ├── keycode_service.dart      ← ASCII 변환 (기존 + 한글 확장)
│   │   ├── hangul_service.dart       ← [신규] 한글 자모 분해 + 두벌식 변환
│   │   ├── transmission_service.dart ← 전송 프로토콜 (기존 + 설정 반영)
│   │   └── settings_service.dart     ← [신규] 설정 영속화
│   └── screens/
│       ├── home_screen.dart     ← 메인 UI (기존 + 한글 표시 강화)
│       ├── scan_screen.dart     ← BLE 스캔 UI (기존)
│       └── settings_screen.dart ← 설정 UI (기존 + OS/속도 선택)
├── test/
│   ├── hangul_service_test.dart     ← [신규] 한글 분해 단위 테스트
│   └── keycode_service_test.dart    ← ASCII 변환 테스트 (기존 + 확장)
└── pubspec.yaml                     ← 의존성 (shared_preferences 추가)

tools/
├── test_phase3_protocol.py    ← 프로토콜 테스트 (기존 + 한글 케이스 추가)
├── test_phase5_hangul.py      ← [신규] 한글 전송 E2E 테스트
├── test_stress.py             ← [신규] 대용량 전송 스트레스 테스트
└── ...                        ← 기존 도구 (변경 없음)
```

**Structure Decision**: 기존 2-component 구조(펌웨어 + Flutter 앱) 유지.
펌웨어는 `textbridge.c` 단일 모듈 확장, 앱은 `hangul_service.dart`와
`settings_service.dart` 2개 파일 신규 추가. 헌법 I(최소 변경)과
VII(단순성) 준수.

## Complexity Tracking

> 위반 사항 없음. 모든 원칙 PASS.
