# Quickstart: TextBridge 빌드, 플래시, 테스트

## 사전 요구사항

- macOS (개발 환경)
- Keychron B6 Pro 키보드 (nRF52840)
- USB-C 케이블
- iOS 또는 Android 폰 (BLE 지원)
- Zephyr SDK 0.16.3 (`~/.zephyr-sdk-0.16.3`)
- Python 3.10+ (`bleak`, `hidapi`, `pynput`)
- Flutter 3.10.8+ (앱 빌드 시)

## 1. 펌웨어 빌드

```bash
# 가상환경 활성화 + SDK 설정
source ~/.zmk_env/bin/activate
export ZEPHYR_SDK_INSTALL_DIR=~/.zephyr-sdk-0.16.3

# 빌드 (zmk_keychron/app 디렉토리에서)
cd ~/project/textbridge/zmk_keychron/app
west build --pristine -b keychron -- -DSHIELD=keychron_b6_us

# 결과: build/zephyr/zmk.uf2
```

## 2. 펌웨어 플래시

```bash
# 방법 A: Python 스크립트로 DFU 진입
python3 ~/project/textbridge/tools/enter_dfu.py
sleep 3
cp build/zephyr/zmk.uf2 /Volumes/NRF52BOOT/

# 방법 B: 수동 DFU 진입
# 키보드에서 ESC + USB 연결 동시 → NRF52BOOT 볼륨 마운트
cp build/zephyr/zmk.uf2 /Volumes/NRF52BOOT/
```

## 3. 시리얼 모니터링

```bash
screen /dev/tty.usbmodem* 115200

# 예상 로그:
# [00:00:03] <inf> textbridge: TextBridge Phase 3 initialized
# [00:00:06] <inf> textbridge: BLE stack ready
```

## 4. BLE 페어링 테스트

```bash
# VIA 명령으로 페어링 모드 시작
python3 ~/project/textbridge/tools/tb_pair.py

# 또는 키보드에서 Fn+1 (3초 이상 홀드)
```

## 5. 프로토콜 테스트

```bash
cd ~/project/textbridge

# 전체 테스트 스위트
python3 tools/test_phase3_protocol.py --test all

# 개별 테스트
python3 tools/test_phase3_protocol.py --test hello      # "hello world"
python3 tools/test_phase3_protocol.py --test special     # 특수문자
python3 tools/test_phase3_protocol.py --test abort       # ABORT 명령

# 커스텀 텍스트
python3 tools/test_phase3_protocol.py --text "print('hi')"

# 옵션
#   --no-pair    VIA 자동화 건너뜀 (수동 Fn+1)
#   --no-verify  HID 입력 검증 건너뜀
#   --scan-only  BLE 장치 검색만
```

## 6. 한글 테스트 (Phase 5)

```bash
cd ~/project/textbridge

# 프로토콜 테스트에 한글 케이스 추가됨
python3 tools/test_phase3_protocol.py --test hangul          # 순수 한글
python3 tools/test_phase3_protocol.py --test hangul_mixed    # 한영 혼합
python3 tools/test_phase3_protocol.py --test hangul_complex  # 쌍자음/겹받침

# 전용 한글 E2E 테스트
python3 tools/test_phase5_hangul.py --test all
python3 tools/test_phase5_hangul.py --test pure      # 순수 한글
python3 tools/test_phase5_hangul.py --test mixed     # 한영 혼합
python3 tools/test_phase5_hangul.py --test complex   # 쌍자음/복합모음/겹받침
```

## 7. 스트레스 테스트

```bash
cd ~/project/textbridge

# 5,000자 단일 전송
python3 tools/test_stress.py --test single --chars 5000

# 5회 반복 전송
python3 tools/test_stress.py --test repeat --chars 5000 --runs 5

# 속도 측정 (100~5000자)
python3 tools/test_stress.py --test speed

# 전체
python3 tools/test_stress.py --test all
```

## 8. Dart 단위 테스트

```bash
cd ~/project/textbridge/flutter_app/textbridge_app

# 전체 테스트
flutter test

# 개별 테스트
flutter test test/keycode_service_test.dart    # ASCII/한글 키코드 변환
flutter test test/hangul_service_test.dart     # 한글 분해/두벌식 매핑
flutter test test/settings_service_test.dart   # 설정 영속화
```

## 9. Flutter 앱 빌드

```bash
cd ~/project/textbridge/flutter_app/textbridge_app
flutter pub get
flutter run   # iOS: 실제 기기 필요 (BLE는 시뮬레이터 미지원)
```

## 10. 검증 체크리스트

| # | 항목 | 명령/방법 | 기대 결과 |
|---|------|-----------|-----------|
| 1 | 빌드 성공 | `west build` | FLASH 25%, SRAM 33% |
| 2 | 시리얼 로그 | `screen` | "BLE stack ready" |
| 3 | BLE 스캔 | `--scan-only` | "B6 TextBridge" 발견 |
| 4 | 단일 키 | `--test single_a` | PC에 'a' 출력 |
| 5 | 문자열 전송 | `--test hello` | "hello world" 정확 출력 |
| 6 | 중지 동작 | `--test abort` | 전송 중단, 키보드 정상 |
| 7 | 앱 연결 | Flutter 앱 실행 | "연결됨" 표시 |
| 8 | 한글 전송 | `--test hangul` | PC에 '안녕하세요' 출력 |
| 9 | 한영 혼합 | `--test hangul_mixed` | 한/영 정확 출력 |
| 10 | 스트레스 | `test_stress.py --test single` | 5,000자 정확 전송 |
| 11 | Dart 테스트 | `flutter test` | 60+ 테스트 통과 |

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| "BLE stack ready" 미출력 | BLE 초기화 실패 | DFU 재플래시 |
| 스캔에 장치 미표시 | USB 모드 아님 | USB 케이블 연결 확인, Fn+1 홀드 |
| 스캔에서 "B6 TextBridge" 대신 "Keychron B6 Pro" 표시 | macOS BLE 이름 캐시 | 정상 동작. UUID로 매칭됨. 이름이 달라도 TextBridge 서비스 사용 가능 |
| START 후 READY 미수신 | `tb_conn` NULL (BLE identity 필터링) | 펌웨어 hotfix 적용 확인: GATT write callback에서 `tb_conn` 자동 설정 |
| ACK 타임아웃 반복 | BLE 신호 약함 | 키보드-폰 거리 줄이기 |
| HID 출력 없음 | PC에 포커스 없음 | 텍스트 편집기 활성화 확인 |
| pynput 권한 오류 | macOS 접근성 미허용 | 시스템 설정 → 개인정보 → 접근성 |
| UF2 복사 시 xattr 에러 | FAT 파일시스템에 확장 속성 미지원 | 무시 가능. 펌웨어는 정상 플래시됨 |
| 시리얼 포트 (`/dev/tty.usbmodem*`) 없음 | USB 로깅 비활성화 | `keychron_defconfig`에서 `CONFIG_ZMK_USB_LOGGING=y` 활성화 후 재빌드 (디버깅 시에만) |

## 알려진 이슈 및 해결

### BLE Identity 필터링 문제 (2026-02-08 수정)

**증상**: BLE 연결은 성공하지만 (MTU=65), START 명령 후 READY 응답 없음.

**원인**: `tb_connected()` 콜백이 `info.id != BT_ID_DEFAULT`로 필터링하여 `tb_conn`이 NULL 상태.
Zephyr에서 GATT 서비스는 identity와 무관하게 전역 등록되므로, 클라이언트가 다른 identity로 연결해도
GATT write/notify는 동작하지만, `tb_conn`이 설정되지 않아 `tb_send_response()`가 무응답.

**수정**: `tb_tx_write_cb()`에서 `tb_conn`이 NULL이면 write callback의 `conn` 파라미터를 채용.

```c
/* tb_tx_write_cb() 시작 부분 */
if (!tb_conn && conn) {
    LOG_INF("TB: adopting conn from write callback");
    tb_conn = bt_conn_ref(conn);
}
```
