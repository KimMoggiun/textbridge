# BLE 광고 동기화 수정 — 계획 검토 사이클

코드를 수정하지 마라. 계획 파일만 수정하라.

---
## 상태 파일

`/Users/evan/project/textbridge/.ralph-plan-state.md`를 읽어라.
없으면 생성하라:

```markdown
# Plan Review State

## Config
- plan_file: /Users/evan/.claude/plans/reflective-crafting-engelbart.md
- source_files:
  - zmk_keychron/app/src/ble.c
  - zmk_keychron/app/src/textbridge.c
  - zmk_keychron/app/src/endpoints.c

## Current
- iteration: 1
- phase: REVIEW

## Fixes Under Review
- [ ] Fix C: zmk_ble_notify_adv_stopped() 추가 (ble.c:448 부근)
- [ ] Fix B: tb_start_advertising 방어적 stop (textbridge.c:495 부근)
- [ ] Fix A: disconnected() connected 플래그 이동 (ble.c:1008-1013)
- [ ] Fix D: update_advertising NONE→start 방어 (ble.c:540, 552)

## Scenarios Under Review
- [ ] S1: BLE→USB→BLE 키입력 재연결
- [ ] S2: TB페어링→전송→BLE복귀 재연결
- [ ] S3: 5회 반복 누적 상태 오염 없음
- [ ] S4: TB광고중 BLE전환 ZMK광고 시작

## Issues Found
(없으면 비워둘 것)
```

---
## 사이클 구조

### Phase 1: REVIEW (코드 대조 검증)

계획 파일의 모든 주장을 실제 코드와 대조한다.

**각 Fix에 대해 검증할 것:**

1. **라인 번호**: 계획이 참조하는 line 번호가 실제 코드와 일치하는가?
   → Read 도구로 해당 파일의 해당 줄을 읽어서 확인
2. **삽입 위치**: 코드가 들어갈 위치의 전후 맥락이 맞는가?
3. **변수/함수 접근**: 참조하는 변수(advertising_status, adv_timeout_work 등)가 해당 스코프에서 접근 가능한가?
4. **부작용**: 수정이 영향 미치는 다른 코드 경로를 모두 추적했는가?
   → Grep으로 해당 변수/함수의 모든 참조를 검색
5. **컴파일 가능성**: 제안된 코드가 문법적으로 올바른가?

**각 시나리오(S1~S4)에 대해 검증할 것:**

수정된 코드 기준으로 실행 경로를 line-by-line 추적:
- 각 함수 호출이 동기인지 비동기인지 확인
- 각 분기의 조건이 해당 시나리오에서 true/false인지 확인
- 최종 상태 변수 값이 올바른지 확인

발견한 문제를 분류:
- **CRITICAL**: 수정이 다른 기능을 깨뜨림, 컴파일 불가, 실행 경로 오류
- **HIGH**: 라인 번호 불일치, 누락된 경로, 부작용 미분석
- **MEDIUM**: 주석 오타, 스타일, 개선 가능한 부분 (수정 대상 아님)

결과를 상태 파일에 기록. 시나리오 체크박스 갱신.

- CRITICAL/HIGH 이슈 있음 → phase를 DRAFT로 변경
- 이슈 없음 → 종료

### Phase 2: DRAFT (계획 수정)

REVIEW에서 발견된 CRITICAL/HIGH 이슈만 수정한다.

규칙:
- 계획 파일(plan_file)을 Edit 도구로 직접 수정
- 수정 이유를 상태 파일에 기록
- 코드 파일은 절대 수정하지 마라
- MEDIUM 이슈는 기록만 하고 넘어가라

완료 후: phase를 REVIEW로 변경, iteration + 1

---
## 시나리오 추적 가이드

### S1: BLE→USB→BLE 키입력 재연결
```
1. BLE: connected() → profiles[].connected = 1
2. USB 전환: disconnect_current_endpoint() → zmk_ble_endpoint_disconnect()
   → bt_conn_disconnect() (비동기) + k_work_reschedule(&adv_timeout_work, 20ms)
3. current_instance = USB (line 405)
4. disconnected() 비동기 콜백:
   → identity 0 가드: 통과 (ZMK profile)
   → Fix A: profiles[].connected = 0 (USB 가드 앞)
   → USB 가드: return
5. BLE 복귀: zmk_ble_init() → advertising_start() → zmk_ble_prof_select()
   → k_work_submit(&update_advertising_work) (비동기)
6. 워크큐: update_advertising() → RECONN 광고 (3초 타임아웃)
7. 타임아웃 후 키 입력: zmk_ble_listener
   → !profiles[].connected → true (Fix A 덕분) → advertising_start()
8. 재광고 → 폰 재연결
```

### S2: TB페어링→전송→BLE복귀
```
1. USB: zmk_textbridge_pair_start() → tb_start_advertising()
2. Fix B: bt_le_adv_stop() + zmk_ble_notify_adv_stopped()
3. TB 광고 → 폰 연결 → 전송 완료
4. BLE 전환: zmk_ble_init() → k_work_submit (비동기)
5. ZMK_EVENT_RAISE → tb_endpoint_listener (동기):
   → tb_stop_advertising() (no-op, 이미 false)
   → bt_conn_disconnect(tb_conn)
6. 워크큐: update_advertising() → ZMK 광고 시작
7. 키 입력 → zmk_ble_listener → 재광고
```

### S3: 5회 반복 상태 검증
```
매 사이클 종료 시 확인:
- profiles[].connected = 0 (Fix A)
- tb_advertising = false
- tb_conn = NULL
- advertising_status = 정확한 값
- adv_timeout_work = 취소됨 또는 정상
```

### S4: TB 광고 중 BLE 전환
```
1. USB: TB 광고 활성 (tb_advertising=true)
2. BLE 전환: zmk_ble_init() → k_work_submit (비동기)
3. ZMK_EVENT_RAISE → tb_endpoint_listener (동기):
   → tb_stop_advertising() → bt_le_adv_stop() → TB 광고 중지
4. 워크큐: update_advertising():
   → NONE→DIR/CONN
   → Fix D: bt_le_adv_stop() (no-op, 이미 중지)
   → checked_dir_adv()/checked_open_adv() → 성공
```

---
## 종료 조건

다음 중 하나 만족 시 종료:

1. **REVIEW에서 CRITICAL/HIGH 이슈 0개** + **S1~S4 모두 체크됨** → 계획 완성
2. **2연속 반복에서 동일 이슈만 반복** → 수렴 불가
3. **iteration > 5** → 안전 장치

종료 시 출력:
```
<promise>PLAN REVIEW COMPLETE</promise>
```

---
## 변경 금지

- 코드 파일 수정 금지
- tb_endpoint_listener 변경 제안 금지 (타이밍 분석 완료됨)
- tb_stop_advertising() 함수 변경 제안 금지
- ble.h 헤더 변경 제안 금지
