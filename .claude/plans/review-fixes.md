# TextBridge 검토 수정 계획

## 수정 대상 (우선순위순)

### CRITICAL

#### C2: setTransmitting(false) 상태 경쟁
**파일**: `flutter_app/textbridge_app/lib/services/ble_service.dart`
**수정**: setState()에서 transmitting→connected 전환 시 현재 상태가 reconnecting/disconnected면 무시

```dart
void setTransmitting(bool transmitting) {
  if (transmitting) {
    setState(TbConnectionState.transmitting);
  } else {
    // Only go back to connected if still in transmitting state
    // (disconnect handler may have already changed state)
    if (_state == TbConnectionState.transmitting) {
      setState(TbConnectionState.connected);
    }
  }
}
```

#### C3: TextBridge 재연결 광고 5초 → 10초
**파일**: `zmk_keychron/app/src/textbridge.c:561`
**수정**: `TB_RECONN_ADV_TIMEOUT_MS` 5000 → 10000

### HIGH

#### H1: autoConnect 10분 타임아웃 → 30초
**파일**: `flutter_app/textbridge_app/lib/services/ble_service.dart:147`
**수정**: `Duration(minutes: 10)` → `Duration(seconds: 30)`

#### H2: iOS MTU 조기 읽기
**파일**: `flutter_app/textbridge_app/lib/services/ble_service.dart:163-165`
**수정**: discoverServices 후 잠시 대기 또는 mtuNow 값이 23이면 재시도

```dart
if (!Platform.isAndroid) {
  // iOS: MTU negotiation may still be in progress after discoverServices.
  // Wait briefly and re-read if still at default.
  _mtu = device.mtuNow;
  if (_mtu <= 23) {
    await Future.delayed(const Duration(milliseconds: 500));
    _mtu = device.mtuNow;
  }
}
```

#### H3: _startAutoDetect 타이머 누적 방지
**파일**: `flutter_app/textbridge_app/lib/services/ble_service.dart:220`
**수정**: 이미 `_autoDetectTimer?.cancel()` 하고 있음. 추가로 진행 중인 async 작업 체크 필요.

```dart
bool _autoDetecting = false;

void _startAutoDetect() {
  _autoDetectTimer?.cancel();
  _autoDetecting = false;
  var retries = 0;
  _autoDetectTimer = Timer.periodic(const Duration(seconds: 2), (_) async {
    if (_autoDetecting) return;  // Skip if previous iteration still running
    _autoDetecting = true;
    try {
      retries++;
      if (_state != TbConnectionState.unregistered || retries > 5) {
        _autoDetectTimer?.cancel();
        _autoDetectTimer = null;
        return;
      }
      // ... existing logic ...
    } finally {
      _autoDetecting = false;
    }
  });
}
```

### MEDIUM

#### M4: Settings load() 클램핑
**파일**: `flutter_app/textbridge_app/lib/services/settings_service.dart`
**수정**: load()에서도 clamp 적용

#### M5: update_advertising() default 케이스
**파일**: `zmk_keychron/app/src/ble.c:547-578`
**수정**: switch문에 `default: break;` 추가

## 검증 방법

1. **Flutter 테스트**: `cd flutter_app/textbridge_app && flutter test`
2. **펌웨어 빌드**: `source ~/.zmk_env/bin/activate && export ZEPHYR_SDK_INSTALL_DIR=~/.zephyr-sdk-0.16.3 && cd zmk_keychron/app && west build --pristine -b keychron -- -DSHIELD=keychron_b6_us`
3. **코드 리뷰**: 각 수정이 기존 동작을 깨뜨리지 않는지 확인

## 완료 기준

- [ ] C2 수정 + 리뷰
- [ ] C3 수정 + 리뷰
- [ ] H1 수정 + 리뷰
- [ ] H2 수정 + 리뷰
- [ ] H3 수정 + 리뷰
- [ ] M4 수정 + 리뷰
- [ ] M5 수정 + 리뷰
- [ ] Flutter 테스트 통과
- [ ] 펌웨어 빌드 성공
