# Delay Optimization Test Plan

펌웨어의 모든 딜레이를 최적화하기 위한 테스트 계획.
앱에서 `CMD_SET_DELAY`로 6개 파라미터를 조정하며 최적값을 찾는다.

## 현재 구현 상태

### 설정 가능한 6개 딜레이 변수

| # | 변수 | 기본값 | 용도 | 펌웨어 위치 |
|---|------|--------|------|-------------|
| 1 | `tb_press_delay` | 5ms | 키 누름 유지 시간 (press → release) | textbridge.c:222 |
| 2 | `tb_release_delay` | 5ms | 키 뗌 후 다음 키까지 대기 | textbridge.c:236 |
| 3 | `tb_combo_delay` | 2ms | 모디파이어 ↔ 키 사이 대기 (2회 사용) | textbridge.c:218, 229 |
| 4 | `tb_toggle_press` | 20ms | 토글 키(Ctrl+Space) 누름 유지 시간 | textbridge.c:222 |
| 5 | `tb_toggle_delay` | 100ms | 토글 후 IME 전환 완료 대기 | textbridge.c:236 |
| 6 | `tb_warmup_delay` | 50ms | 세션 첫 청크만 USB 워밍업 | textbridge.c:198 |

### 딜레이 전달 경로

```
Flutter SettingsService (SharedPreferences에 저장)
  → TransmissionService.sendText() 시작 시 makeSetDelay() 호출
    → BLE write CMD_SET_DELAY [0x05, p, r, c, tp, td, w]
      → 펌웨어 tb_tx_write_cb() → 6개 변수 업데이트 → ACK
        → tb_inject_work_handler()에서 k_msleep()으로 사용
```

### 하드코딩 딜레이 (조정 불필요)

| 위치 | 값 | 용도 |
|------|----|------|
| textbridge.c:583 | 3000ms | BLE 초기화 지연 (부팅 후 `bt_enable` 호출 대기) |

### 숨은 지연: `send_report()`

`zmk_endpoints_send_report(0x07)` 자체에 USB 스택 블로킹 존재:
- USB Full Speed polling interval: ~1ms
- `usb_hid.c`의 `k_sem_take` 세마포어 대기 (최대 타임아웃까지)
- nRF USBD 전용 워크큐에서 `in_ready_cb` → `k_sem_give` 실행

이 시간은 `k_msleep` 외 추가 소요되는 암묵적 지연.

---

## 키 타입별 딜레이 구성

### 일반 키 (모디파이어 없음) — 2 report, 2 delay

```
keyboard_press(kc) → send_report → k_msleep(press_delay)
keyboard_release(kc) → send_report → k_msleep(release_delay)
```
총: `press_delay + release_delay` = **10ms/key** (기본값)

### 일반 키 (모디파이어 있음, Shift+A 등) — 4 report, 4 delay

```
register_mods(mod) → send_report → k_msleep(combo_delay)
keyboard_press(kc) → send_report → k_msleep(press_delay)
keyboard_release(kc) → send_report → k_msleep(combo_delay)
unregister_mods(mod) → send_report → k_msleep(release_delay)
```
총: `combo_delay×2 + press_delay + release_delay` = **14ms/key** (기본값)

### 토글 키 (Ctrl+Space, macOS) — 4 report, 4 delay

```
register_mods(Ctrl=0x01) → send_report → k_msleep(combo_delay)
keyboard_press(Space=0x2C) → send_report → k_msleep(toggle_press)
keyboard_release(Space) → send_report → k_msleep(combo_delay)
unregister_mods(Ctrl) → send_report → k_msleep(toggle_delay)
```
총: `combo_delay×2 + toggle_press + toggle_delay` = **124ms/toggle** (기본값)

### 토글 키 (LANG1=0x90, Windows) — 2 report, 2 delay

```
keyboard_press(0x90) → send_report → k_msleep(toggle_press)
keyboard_release(0x90) → send_report → k_msleep(toggle_delay)
```
총: `toggle_press + toggle_delay` = **120ms/toggle** (모디파이어 없음, combo_delay 안 씀)

### 워밍업 — 세션당 1회만 (첫 청크)

```
send_report(empty) → k_msleep(warmup_delay)
→ tb_needs_warmup = false (이후 청크는 스킵)
```
총: **50ms** (기본값), START 명령에서 `tb_needs_warmup = true`로 리셋

---

## 현재 코드 불일치 사항

### 1. Python 테스트 스크립트의 딜레이 오버라이드

테스트 스크립트들이 펌웨어 기본값과 다른 딜레이를 사용 중:

| 파일 | 위치 | 사용값 | 기본값과 차이 |
|------|------|--------|--------------|
| `test_phase3_protocol.py:645` | `main()` | combo=20 | 기본 2 → **10배** |
| `test_phase5_hangul.py:94` | 그룹 시작 | press=5, rel=5, combo=20 | combo 10배 |
| `test_phase5_hangul.py:98` | 매 텍스트 전 | press=15, rel=15, combo=30 | **전부 다름** |

**문제**: `test_phase5_hangul.py`는 매 텍스트 전에 `set_delay(press=15, rel=15, combo=30)`으로 오버라이드하므로, line 94의 설정은 첫 텍스트에만 적용되고 이후에는 항상 15/15/30/20/100/50으로 실행됨.

### 2. ACK 타임아웃 계산 불정확

`transmission_service.dart:141-143`:
```dart
final ackTimeoutMs = warmupMs +
    chunk.pairs.length * (pressMs + releaseMs + 2 * comboMs) + 500;
```

**문제**: 모든 키를 `press + release + 2*combo`로 계산하지만, 토글 키는 별도 청크(1개)로 분리되므로 `toggle_press + toggle_delay + 2*combo`가 되어야 함. 다만 토글 청크는 pairs.length=1이라 timeout이 매우 짧게 계산됨. 현재 buffer 500ms가 커버하고 있지만 toggle_delay를 255ms까지 올리면 부족할 수 있음.

### 3. ETA 계산 근사치

`home_screen.dart:186`:
```dart
final etaMs = remaining * (settings.pressDelay + settings.releaseDelay);
```

**문제**: 모디파이어 키(combo_delay×2 추가)와 토글 키(toggle_press+toggle_delay)를 고려하지 않음. 실제보다 빠른 ETA를 보여줌. UI 표시용이므로 치명적이지 않지만 부정확.

### 4. settings_screen.dart 워밍업 설명

`settings_screen.dart:99`: `'USB host sync before each chunk'`

**실제**: 워밍업은 세션 첫 청크만. `tb_needs_warmup` 플래그로 제어.

### 5. ble-protocol.md 워밍업 설명

`ble-protocol.md:82`: `warmup_delay (1~255 ms) — 청크 시작 전 USB 호스트 동기화 대기`

**실제**: "세션 첫 청크 시작 전" USB 호스트 동기화 대기. 모든 청크가 아님.

---

## 테스트 프로파일

### 기준 속도 (현재 기본값)

| 시나리오 | ms/key | keys/sec | send_report 횟수 |
|----------|--------|----------|-----------------|
| 영문 소문자 (mod 없음) | 10 | 100 | 2 |
| 영문 대문자 (Shift) | 14 | 71 | 4 |
| 한글 자모 (mod 없음) | 10 | 100 | 2 |
| 한글 쌍자음 (Shift) | 14 | 71 | 4 |
| 한영 전환 (macOS) | 124 | — | 4 |
| 한영 전환 (Windows) | 120 | — | 2 |

### Profile A: 기본값 (baseline)

| press | release | combo | toggle_press | toggle_delay | warmup |
|-------|---------|-------|--------------|--------------|--------|
| 5 | 5 | 2 | 20 | 100 | 50 |

### Profile B: 보수적 최적화

| press | release | combo | toggle_press | toggle_delay | warmup |
|-------|---------|-------|--------------|--------------|--------|
| 3 | 3 | 1 | 15 | 80 | 40 |

### Profile C: 공격적 최적화

| press | release | combo | toggle_press | toggle_delay | warmup |
|-------|---------|-------|--------------|--------------|--------|
| 2 | 2 | 1 | 10 | 60 | 30 |

### Profile D: 극한 테스트

| press | release | combo | toggle_press | toggle_delay | warmup |
|-------|---------|-------|--------------|--------------|--------|
| 1 | 1 | 1 | 5 | 40 | 20 |

### 예상 속도 비교

| Profile | 일반 키 (ms) | Shift 키 (ms) | 토글 macOS (ms) | 영문 소문자 keys/sec |
|---------|-------------|---------------|----------------|---------------------|
| A (기본) | 10 | 14 | 124 | 100 |
| B | 6 | 8 | 97 | 167 |
| C | 4 | 6 | 73 | 250 |
| D | 2 | 4 | 47 | 500 |

> 참고: 위 계산은 `k_msleep`만 포함. 실제는 `send_report()` USB 지연이 추가되어 이론값보다 느림.

---

## 테스트 절차

테스트 도구: `test_phase3_protocol.py --text "..."` (VIA 페어링 → BLE 스캔 → SET_DELAY → 전송 → Enter)

**사전 준비**: Python 스크립트의 `set_delay()` 호출을 테스트 프로파일 값으로 수정하거나, 앱 UI에서 변경 후 앱으로 전송.

### 1단계: 영문 전용 (토글 없음)

press/release/combo만 검증. 토글 변수 무관.

**텍스트**: `"The quick brown fox jumps over the lazy dog"`
- 44자, 대문자 1개(Shift), 공백 8개, 소문자 35개
- 총 키코드: 44개 (Shift+T 1개 + 나머지 43개)
- [ ] Profile A — PASS / FAIL
- [ ] Profile B — PASS / FAIL
- [ ] Profile C — PASS / FAIL
- [ ] Profile D — PASS / FAIL (깨지는 지점 확인)

### 2단계: 한글 전용 (토글 1회 + trailing toggle 1회)

toggle_delay 최소값 확인. 토글은 시작 1회 + 끝 1회 = 2회.

**텍스트**: `"안녕하세요"`
- 키코드: toggle + 안(3)+녕(3)+하(2)+세(2)+요(2) + trailing toggle = 14개
- [ ] Profile A — PASS / FAIL
- [ ] Profile B — PASS / FAIL
- [ ] Profile C — PASS / FAIL
- [ ] Profile D — PASS / FAIL

### 3단계: 혼합 (토글 다회)

영한 반복 전환. toggle_delay가 충분한지 확인.

**텍스트**: `"Hello 안녕 World 세계"`
- 토글 4회 (영→한, 한→영, 영→한, 한→영)
- [ ] Profile A — PASS / FAIL
- [ ] Profile B — PASS / FAIL
- [ ] Profile C — PASS / FAIL
- [ ] Profile D — PASS / FAIL

### 4단계: 쌍자음/복합모음/겹받침 (Shift+키)

combo_delay + press_delay 최소값 확인. 쌍자음은 Shift 모디파이어 필요.

**텍스트**: `"까닭없이 값싼 읽다 앉다"`
- 쌍자음: 까(ㄲ=Shift+R), 쌍시옷 등
- 겹받침: 값(ㅄ=Q,T), 읽(ㄺ=F,R), 앉(ㄵ=S,W)
- [ ] Profile A — PASS / FAIL
- [ ] Profile B — PASS / FAIL
- [ ] Profile C — PASS / FAIL
- [ ] Profile D — PASS / FAIL

### 5단계: 스트레스 (5000자)

최적 프로파일로 대량 전송 안정성 확인.

- [ ] 최적 프로파일 × 5000자 × 1회
- [ ] 최적 프로파일 × 5000자 × 3회 연속

---

## 판정 기준

- **PASS**: HID 출력이 원본 텍스트와 100% 일치
- **FAIL**: 누락, 중복, 오입력 발생

깨지는 프로파일의 한 단계 위를 최적값으로 채택.

---

## 테스트 전 수정 필요 사항

### 필수 수정

1. **test_phase5_hangul.py:94,98** — 테스트 프로파일 값으로 통일하거나, 프로파일 파라미터를 CLI 인자로 받도록 수정
2. **test_phase3_protocol.py:645** — `combo_delay=20`을 프로파일 값으로 변경하거나 CLI 인자화

### 권장 수정

3. **settings_screen.dart:99** — 워밍업 설명을 `'USB host sync before first chunk'`으로 수정
4. **ble-protocol.md:82** — `세션 첫 청크 시작 전 USB 호스트 동기화 대기`로 수정
5. **transmission_service.dart:141-143** — 토글 청크 ACK 타임아웃에 `toggle_press + toggle_delay` 반영

---

## 결과 기록

| 단계 | Profile | 결과 | 속도 체감 | 비고 |
|------|---------|------|----------|------|
| 1-영문 | A | | | |
| 1-영문 | B | | | |
| 1-영문 | C | | | |
| 1-영문 | D | | | |
| 2-한글 | A | | | |
| 2-한글 | B | | | |
| 2-한글 | C | | | |
| 2-한글 | D | | | |
| 3-혼합 | A | | | |
| 3-혼합 | B | | | |
| 3-혼합 | C | | | |
| 3-혼합 | D | | | |
| 4-쌍자음 | A | | | |
| 4-쌍자음 | B | | | |
| 4-쌍자음 | C | | | |
| 4-쌍자음 | D | | | |
| 5-스트레스 | 최적 | | | |
