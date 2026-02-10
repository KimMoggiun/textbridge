# Delay Optimization Test Plan

펌웨어의 모든 딜레이를 최적화하기 위한 테스트 계획.
앱에서 `CMD_SET_DELAY`로 6개 파라미터를 조정하며 최적값을 찾는다.

## 펌웨어 딜레이 맵

### 설정 가능한 6개 변수

| # | 변수 | 기본값 | 용도 | 위치 |
|---|------|--------|------|------|
| 1 | `tb_press_delay` | 5ms | 키 누름 유지 시간 (press → release) | line 222 |
| 2 | `tb_release_delay` | 5ms | 키 뗌 후 다음 키까지 대기 | line 236 |
| 3 | `tb_combo_delay` | 2ms | 모디파이어 ↔ 키 사이 대기 | line 218, 229 |
| 4 | `tb_toggle_press` | 20ms | 토글 키(Ctrl+Space) 누름 유지 | line 222 |
| 5 | `tb_toggle_delay` | 100ms | 토글 후 IME 전환 완료 대기 | line 236 |
| 6 | `tb_warmup_delay` | 50ms | 세션 첫 청크 USB 워밍업 | line 198 |

### 키 타입별 딜레이 구성

**일반 키 (모디파이어 없음)** — 2 report, 2 delay
```
press → send_report → press_delay
release → send_report → release_delay
```
→ press_delay + release_delay = **10ms/key** (기본값)

**일반 키 (모디파이어 있음, Shift+A 등)** — 4 report, 4 delay
```
register_mods → send_report → combo_delay
press → send_report → press_delay
release → send_report → combo_delay
unregister_mods → send_report → release_delay
```
→ combo_delay×2 + press_delay + release_delay = **14ms/key** (기본값)

**토글 키 (Ctrl+Space)** — 4 report, 4 delay
```
register_mods(Ctrl) → send_report → combo_delay
press(Space) → send_report → toggle_press
release(Space) → send_report → combo_delay
unregister_mods(Ctrl) → send_report → toggle_delay
```
→ combo_delay×2 + toggle_press + toggle_delay = **124ms/toggle** (기본값)

### 하드코딩 (조정 불필요)

| 위치 | 값 | 용도 |
|------|----|------|
| line 583 | 3000ms | BLE 초기화 지연 (부팅 후) |

### 숨은 지연: `send_report()`

`zmk_endpoints_send_report()` 자체에 USB 스택 블로킹 존재:
- USB Full Speed polling: ~1ms
- `usb_hid.c` 세마포어 대기

이 시간은 `k_msleep` 외 추가 소요되는 시간임.

---

## 테스트 매트릭스

### 기준 속도 (현재 기본값)

| 시나리오 | ms/key | keys/sec |
|----------|--------|----------|
| 영문 소문자 | 10 | 100 |
| 영문 대문자 (Shift) | 14 | 71 |
| 한글 자모 | 10 | 100 |
| 한글 쌍자음 (Shift) | 14 | 71 |
| 한영 전환 | 124 | — |

### 테스트할 프로파일

각 프로파일로 Phase5 전체 테스트 실행하여 정확도 확인.

#### Profile A: 기본값 (baseline)
| press | release | combo | toggle_press | toggle_delay | warmup |
|-------|---------|-------|--------------|--------------|--------|
| 5 | 5 | 2 | 20 | 100 | 50 |

#### Profile B: 보수적 최적화
| press | release | combo | toggle_press | toggle_delay | warmup |
|-------|---------|-------|--------------|--------------|--------|
| 3 | 3 | 1 | 15 | 80 | 40 |

#### Profile C: 공격적 최적화
| press | release | combo | toggle_press | toggle_delay | warmup |
|-------|---------|-------|--------------|--------------|--------|
| 2 | 2 | 1 | 10 | 60 | 30 |

#### Profile D: 극한 테스트
| press | release | combo | toggle_press | toggle_delay | warmup |
|-------|---------|-------|--------------|--------------|--------|
| 1 | 1 | 1 | 5 | 40 | 20 |

### 예상 속도 비교

| Profile | 일반 키 (ms) | Shift 키 (ms) | 토글 (ms) | 영문 keys/sec |
|---------|-------------|---------------|-----------|--------------|
| A (기본) | 10 | 14 | 124 | 100 |
| B | 6 | 8 | 97 | 167 |
| C | 4 | 6 | 73 | 250 |
| D | 2 | 4 | 47 | 500 |

> 참고: 위 계산은 `k_msleep`만 포함. 실제는 `send_report()` USB 지연이 추가됨.

---

## 테스트 절차

### 1단계: 영문 전용 (토글 없음)
각 프로파일로 테스트. 토글 영향 없이 press/release/combo만 검증.

**텍스트**: `"The quick brown fox jumps over the lazy dog"`
- [ ] Profile A — 정확도 확인
- [ ] Profile B — 정확도 확인
- [ ] Profile C — 정확도 확인
- [ ] Profile D — 정확도 확인 (깨지는 지점 확인)

### 2단계: 한글 전용 (토글 1회)
한영 전환 후 한글만 입력. toggle_delay 최소값 확인.

**텍스트**: `"안녕하세요 대한민국 프로그래밍"`
- [ ] Profile A — 정확도 확인
- [ ] Profile B — 정확도 확인
- [ ] Profile C — 정확도 확인
- [ ] Profile D — 정확도 확인

### 3단계: 혼합 (토글 다회)
영한 반복 전환. toggle_delay가 충분한지 확인.

**텍스트**: `"Hello 안녕 World 세계"`
- [ ] Profile A — 정확도 확인
- [ ] Profile B — 정확도 확인
- [ ] Profile C — 정확도 확인
- [ ] Profile D — 정확도 확인

### 4단계: 쌍자음/복합 (Shift+키)
combo_delay + press_delay 최소값 확인.

**텍스트**: `"까닭없이 값싼 읽다 앉다"`
- [ ] Profile A — 정확도 확인
- [ ] Profile B — 정확도 확인
- [ ] Profile C — 정확도 확인
- [ ] Profile D — 정확도 확인

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

## 결과 기록

| 단계 | Profile | 결과 | 비고 |
|------|---------|------|------|
| 1-영문 | A | | |
| 1-영문 | B | | |
| 1-영문 | C | | |
| 1-영문 | D | | |
| 2-한글 | A | | |
| 2-한글 | B | | |
| 2-한글 | C | | |
| 2-한글 | D | | |
| 3-혼합 | A | | |
| 3-혼합 | B | | |
| 3-혼합 | C | | |
| 3-혼합 | D | | |
| 4-쌍자음 | A | | |
| 4-쌍자음 | B | | |
| 4-쌍자음 | C | | |
| 4-쌍자음 | D | | |
| 5-스트레스 | 최적 | | |
