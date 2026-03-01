<!--
=== 동기화 영향 보고서 ===
- 버전 변경: 0.0.0 → 1.0.0
- 수정된 원칙: (신규 문서 — 기존 원칙 없음)
- 추가된 섹션:
  - 핵심 원칙 7개 (최소 변경, 펌웨어-앱 역할 분리, USB 전용 제약,
    프로토콜 안전성, 보안 기본값, 단계별 검증, 단순성 우선)
  - 기술 제약 및 코딩 규칙
  - 개발 워크플로우
  - 거버넌스
- 삭제된 섹션: (없음)
- 템플릿 업데이트 상태:
  - .specify/templates/plan-template.md ⚠ 보류 (Constitution Check 섹션
    에서 본 헌법의 원칙을 게이트로 반영 필요)
  - .specify/templates/spec-template.md ✅ 변경 불필요
  - .specify/templates/tasks-template.md ✅ 변경 불필요
  - .specify/templates/commands/ — 파일 없음, 해당 없음
- 후속 TODO:
  - plan-template.md의 Constitution Check 섹션에 TextBridge 원칙
    게이트를 예시로 추가 검토
===
-->

# TextBridge 프로젝트 헌법

## 핵심 원칙

### I. 최소 변경 원칙 (Minimal ZMK Modification)

ZMK 펌웨어의 기존 코드를 최소한으로 수정한다. TextBridge의 모든 핵심
기능은 **단일 모듈** `textbridge.c`에 집중하며, ZMK 기존 파일 수정은
필수적인 통합 지점(integration hook)에만 한정한다.

- 기존 ZMK 파일(`ble.c`, `hid.c`, `endpoints.c`, `hog.c`,
  `behavior_bt.c` 등) 수정은 **반드시 정당성을 문서화**해야 한다.
- 새로운 통합 지점 추가 시, 기존 ZMK의 transport 디스패치 패턴
  (`24G → zmk_24g_pair()`)과 동일한 방식을 따라야 한다.
- `CMakeLists.txt` 변경은 `target_sources` 추가만 허용한다.
- **근거:** 키크론 B6 Pro의 ZMK 포크는 ESB 패치 등 커스텀 코드를 포함하고
  있으며, 변경 범위를 최소화해야 향후 업스트림 병합과 유지보수가 가능하다.

### II. 펌웨어-앱 역할 분리 (Firmware-App Separation)

펌웨어는 **언어를 모르는 HID 주입 엔진**이다. 모든 문자 해석, 키코드 변환,
한글 자모 분해는 앱(Flutter)에서 처리한다.

- 펌웨어는 `(keycode, modifier)` 쌍만 수신하여 press/release로 변환한다.
- 문자 집합(ASCII, 한글, 특수문자)에 대한 로직은 펌웨어에 포함하지 않는다.
- 한/영 전환키(`0x90`, `0xE7`) 삽입은 앱의 책임이다.
- OS별 차이(Windows/macOS) 처리는 앱에서 수행한다.
- **근거:** nRF52840의 제한된 플래시/RAM(1MB/256KB) 자원에서 11,172개
  한글 음절 변환 테이블을 펌웨어에 담는 것은 비효율적이며, 앱 업데이트가
  펌웨어 플래시보다 빠르고 안전하다.

### III. USB 전용 제약 (USB-Only Constraint)

TextBridge는 **USB 유선 모드에서만** 동작한다. BLE 모드와 2.4GHz 모드에서는
비활성화한다.

- nRF52840의 단일 라디오 제약을 준수한다.
- BLE 모드: ZMK HID 광고가 라디오를 사용 중이므로 미지원.
- 2.4GHz 모드: ESB 프리컴파일 바이너리가 라디오를 독점하므로 미지원.
- USB 모드 이탈 시 즉시 전송 중단, HID 클리어, BLE 종료를 수행한다.
- USB 모드 복귀 시 본딩된 기기 전용 BLE 광고를 자동 재시작한다.
- **근거:** 하드웨어 물리적 제약이며, 설계 초기에 확인된 불변 조건이다.

### IV. 프로토콜 안전성 (Protocol Safety)

ACK 기반 흐름 제어를 통해 데이터 무결성을 보장하며, 어떠한 상황에서도
키보드가 비정상 상태에 빠지지 않도록 한다.

- 한 번에 미확인 청크는 **최대 1개**. ACK 수신 후 다음 청크를 전송한다.
- 시퀀스 번호(0-255 순환)로 중복 청크를 감지하고 이중 입력을 방지한다.
- BLE 연결 끊김 시 `BT_CONN_DISCONNECTED` 콜백에서 즉시 상태를 초기화한다.
- 전송 중 30초 무응답 시 자동 타임아웃으로 전송을 중단한다.
- `TB_CMD_ABORT` 수신 시 즉시 HID 리포트를 클리어하고 대기 상태로 복귀한다.
- 전송 중 일반 키보드 타이핑은 차단한다 (입력 오염 방지).
- **근거:** 폐쇄망 PC에 잘못된 키 입력이 주입되면 복구가 어려우며,
  프로그래밍 소스 코드의 정확성이 핵심 요구사항이다.

### V. 보안 기본값 (Security by Default)

BLE 통신은 본딩 기반 암호화를 기본으로 하며, 물리적 접근 없이는 페어링할
수 없도록 한다.

- `CONFIG_BT_FILTER_ACCEPT_LIST=y`: 본딩된 기기만 연결을 허용한다.
- 최초 페어링은 물리적 키 조작(Fn+1, 3초 이상 홀드)을 요구한다.
- GATT Write 권한은 `BT_GATT_PERM_WRITE_ENCRYPT` 이상을 사용한다.
- TextBridge BLE 광고에 HID UUID를 포함하지 않는다 (키보드 자동 인식 방지).
- TextBridge는 ZMK BLE 프로필(ID 1-3)과 분리된 `BT_ID_DEFAULT`(0)를
  사용한다.
- VIA Raw HID 명령은 USB 물리적 접근이 전제이므로 별도 인증을 적용하지
  않는다.
- **근거:** 폐쇄망 환경의 보안 정책을 위반하지 않으면서, 승인되지 않은
  기기의 텍스트 주입을 차단해야 한다.

### VI. 단계별 검증 (Phase-Gated Validation)

5단계 개발 계획의 각 Phase 성공 기준을 **모두 통과한 후** 다음 Phase로
진행한다. 성공 기준이 불명확한 상태에서 다음 단계로 넘어가지 않는다.

- Phase 1: USB 모드에서 HID 키 주입이 PC에서 인식되는지 확인.
- Phase 2: BLE GATT 서비스 등록, 폰 연결, 페어링 동작 확인.
- Phase 3: 프로토콜 파싱, ACK 흐름 제어, HID 주입 파이프라인 확인.
- Phase 4: Flutter 앱 BLE 연결, ASCII 키코드 변환, 전송 UI 확인.
- Phase 5: 한글 처리, 프로덕션 안정성, 대용량 텍스트 전송 확인.
- 각 Phase의 테스트는 자동화 도구(`tools/` 스크립트)로 수행한다.
- **근거:** 임베디드 시스템은 디버깅 비용이 높으며, 단계별 검증 없이
  진행하면 문제의 원인 특정이 불가능해진다.

### VII. 단순성 우선 (Simplicity First)

가장 단순하고 안전한 방식을 선택한다. YAGNI(You Ain't Gonna Need It)
원칙을 적용하며, 가설적 미래 요구사항을 위한 설계를 하지 않는다.

- 추상화 계층, 제네릭 인터페이스, 팩토리 패턴 등 과도한 설계를 금지한다.
- 펌웨어: 단일 파일(`textbridge.c`) 단일 모듈 구조를 유지한다.
- 앱: Provider 패턴의 최소 상태 관리를 유지한다.
- 기능 추가 시 기존 코드의 복잡도가 불필요하게 증가하지 않는지 검토한다.
- 3줄의 유사 코드가 하나의 섣부른 추상화보다 낫다.
- **근거:** 이 프로젝트의 핵심은 텍스트 전송이라는 명확한 단일 목적이며,
  확장성보다 정확한 동작과 유지보수 용이성이 우선이다.

## 기술 제약 및 코딩 규칙

### 하드웨어 제약

| 항목 | 값 | 비고 |
|------|-----|------|
| MCU | nRF52840 (ARM Cortex-M4) | 단일 라디오 |
| 플래시 | 1MB | 펌웨어 빌드 FLASH 25% 사용 |
| RAM | 256KB | SRAM 33% 사용 |
| BLE MTU | 기본 23바이트 / 협상 후 최대 244바이트 | 청크 크기 결정 |
| USB 폴링 | 1000Hz (1ms) | HID 주입 최소 간격 |
| BLE 광고 | 단일 인스턴스만 가능 | USB 모드에서만 TextBridge 광고 |

### 펌웨어 코딩 규칙 (C / Zephyr)

- **코드 스타일:** `.clang-format` 준수 (LLVM 기반, 4칸 들여쓰기,
  100자 줄 제한)
- **네이밍:** TextBridge 모듈 접두사 `tb_` 사용
  - 상수: `TB_CMD_KEYCODE`, `TB_MAX_KEYCODES`
  - 정적 전역: `tb_conn`, `tb_notify_enabled`
  - 함수: `tb_tx_write_cb()`, `tb_on_receive()`
  - 공개 API: `zmk_textbridge_` 접두사 (예: `zmk_textbridge_pair_start()`)
- **로깅:** `LOG_MODULE_REGISTER(textbridge, CONFIG_ZMK_LOG_LEVEL)` 사용
  - 정보: `LOG_INF`, 경고: `LOG_WRN`, 오류: `LOG_ERR`
  - 로그 메시지는 `TB ` 접두사로 시작 (예: `"TB KEYCODE seq=%d count=%d"`)
- **초기화:** `SYS_INIT(textbridge_init, APPLICATION, 91)` — `endpoints.c`
  (우선순위 90) 이후
- **GATT:** `BT_GATT_SERVICE_DEFINE` 정적 등록 매크로 사용
- **동시성:** ZMK 시스템 work queue (`k_work`, `k_work_delayable`) 사용.
  별도 스레드를 생성하지 않는다.
- **HID 주입 순서:**
  1. `zmk_hid_register_mods()` (modifier가 있는 경우)
  2. `zmk_hid_keyboard_press()` → `zmk_endpoints_send_report(0x07)`
  3. `k_msleep(delay)` → `zmk_hid_keyboard_release()`
  4. `zmk_endpoints_send_report(0x07)` → modifier 해제
- **include 순서:** `SortIncludes: false` — 수동 관리, Zephyr 헤더 먼저,
  ZMK 헤더 다음
- **정적 분석:** 컴파일러 경고를 오류로 처리 (Zephyr 기본 설정)

### Flutter 앱 코딩 규칙 (Dart)

- **린터:** `package:flutter_lints/flutter.yaml` 기반
- **상태 관리:** Provider 패턴 (`ChangeNotifier`, `ChangeNotifierProxy`)
- **디자인:** Material 3 (`useMaterial3: true`)
- **네이밍:**
  - 서비스: `BleService`, `KeycodeService`, `TransmissionService`
  - 모델: `ConnectionState`, `KeycodePair`
  - 화면: `HomeScreen`, `ScanScreen`, `SettingsScreen`
- **의존성 최소화:** 핵심 BLE(`flutter_blue_plus`), 상태(`provider`),
  권한(`permission_handler`)만 사용
- **SDK:** Dart `^3.10.8`, Flutter 3.10.8+

### Python 테스트 도구 규칙

- **용도:** 자동화 테스트 및 유틸리티 전용 (프로덕션 코드 아님)
- **핵심 라이브러리:** `bleak` (BLE), `hidapi` (USB HID), `pynput` (입력 검증)
- **위치:** `tools/` 디렉토리
- **실행:** `python3 tools/<script>.py [options]`

## 개발 워크플로우

### 빌드 및 플래시 절차

```
1. 환경 활성화:  source ~/.zmk_env/bin/activate
2. SDK 설정:     export ZEPHYR_SDK_INSTALL_DIR=~/.zephyr-sdk-0.16.3
3. 빌드:         west build -b keychron -- -DSHIELD=keychron_b6_us
4. DFU 진입:     python3 tools/enter_dfu.py (또는 ESC+U 동시 누르기)
5. 플래시:       cp build/zephyr/zmk.uf2 /Volumes/NRF52BOOT/
6. 모니터링:     screen /dev/tty.usbmodem* 115200
```

### 커밋 관례

- 펌웨어 변경: `firmware: <설명>` 또는 Phase 기반 `Phase N: <설명>`
- 앱 변경: `app: <설명>`
- 문서 변경: `docs: <설명>`
- 도구 변경: `tools: <설명>`
- 커밋 메시지는 영어 또는 한국어 가능 (혼용 가능)

### 프로젝트 디렉토리 구조

```
textbridge/
├── docs/plans/              ← 설계 문서 및 개발 계획
├── tools/                   ← Python 테스트 및 유틸리티 스크립트
├── flutter_app/             ← Flutter 모바일 앱
│   └── textbridge_app/
│       ├── lib/             ← Dart 소스 (main, models, services, screens)
│       ├── pubspec.yaml     ← 의존성 정의
│       └── analysis_options.yaml
├── zmk_keychron/            ← ZMK 펌웨어 전체 소스
│   ├── app/
│   │   ├── src/textbridge.c ← TextBridge 핵심 모듈 (신규)
│   │   ├── src/ble.c        ← BLE 관리 (최소 수정)
│   │   ├── CMakeLists.txt   ← 빌드 설정 (1줄 추가)
│   │   └── boards/          ← 보드/키맵 정의 (변경 없음)
│   ├── zephyr/              ← Zephyr RTOS (.gitignore)
│   └── modules/             ← Zephyr 모듈 (.gitignore)
├── .specify/                ← speckit 설정 및 메모리
├── README.md
└── .gitignore
```

## 거버넌스

### 헌법의 지위

이 헌법은 TextBridge 프로젝트의 **최상위 설계 원칙** 문서이다.
모든 코드 변경, 설계 결정, 리뷰는 이 문서의 원칙을 준수해야 한다.
원칙과 충돌하는 코드 변경은 헌법 개정을 먼저 수행한 후 진행한다.

### 개정 절차

1. 개정 사유와 영향 범위를 문서화한다.
2. 기존 원칙과의 충돌 여부를 검토한다.
3. 버전을 시맨틱 버저닝에 따라 갱신한다:
   - MAJOR: 원칙의 삭제 또는 근본적 재정의
   - MINOR: 새로운 원칙 또는 섹션 추가
   - PATCH: 문구 명확화, 오타 수정, 비의미적 변경
4. `LAST_AMENDED_DATE`를 갱신한다.

### 준수 검증

- 모든 코드 리뷰에서 헌법 원칙 준수를 확인한다.
- `plan-template.md`의 Constitution Check 섹션에서 구현 계획이 원칙과
  부합하는지 게이트 검증을 수행한다.
- 복잡도 증가가 필요한 경우, Complexity Tracking 테이블에 정당성을
  기록한다.

### 참조 문서

- 설계 문서: `docs/plans/2026-02-06-textbridge-design.md`
- 개발 계획: `docs/plans/textbridge-5phase-plan.md`
- 개발 가이드: 각 디렉토리의 `CLAUDE.md`

**Version**: 1.0.0 | **Ratified**: 2026-02-08 | **Last Amended**: 2026-02-08
