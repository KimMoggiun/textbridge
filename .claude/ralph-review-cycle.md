# TextBridge 전방위 리뷰-수정 사이클

## 상태 파일
`/Users/evan/project/textbridge/.ralph-cycle-state.md`를 읽어서 현재 사이클과 단계를 확인하라.
파일이 없으면 cycle=1, phase=REVIEW로 시작하라.

## 사이클 구조

각 사이클은 4단계로 구성된다:

### Phase 1: REVIEW (전방위 검토)
서브에이전트 5개를 병렬로 띄워 전체 프로젝트를 검토한다:
1. **Firmware** (textbridge.c, ble.c, launcher.c, CMakeLists, usb_hid.c)
2. **Flutter Services & Models** (services/, models/, protocol.dart)
3. **Flutter UI** (screens/, main.dart)
4. **Tests** (Dart tests + Python tools)
5. **Specs & Docs** (specs/, CLAUDE.md files, MEMORY.md)

각 에이전트는 CRITICAL/HIGH/MEDIUM/LOW로 분류된 finding 목록을 반환한다.

검토 완료 후:
- 결과를 `.ralph-cycle-state.md`에 기록
- phase를 PLAN으로 변경

### Phase 2: PLAN (수정 계획)
REVIEW 결과에서 CRITICAL과 HIGH 이슈만 추출하여 수정 계획을 작성한다.

규칙:
- 이전 사이클에서 이미 수정 완료된 항목은 제외 (상태 파일의 completed_fixes 참조)
- 한 사이클에서 최대 5개 이슈만 수정 (품질 > 수량)
- 각 수정 항목에 대해: 파일, 변경 내용, 검증 방법을 명시
- firmware 변경은 빌드 검증 포함
- Flutter 변경은 `flutter test` 검증 포함
- Docs 변경은 코드와 일치 여부 검증 포함

계획 완료 후:
- 계획을 `.ralph-cycle-state.md`에 기록
- phase를 FIX으로 변경

### Phase 3: FIX (수정 실행)
PLAN에서 정한 수정 항목을 하나씩 실행한다.

규칙:
- 항목 하나 수정할 때마다 즉시 관련 테스트 실행
- 테스트 실패 시 수정을 되돌리고 다음 항목으로 이동 (실패 기록)
- 모든 수정은 최소 변경 원칙 (over-engineering 금지)
- 수정 완료된 항목은 completed_fixes에 추가

수정 완료 후:
- 결과를 `.ralph-cycle-state.md`에 기록
- phase를 TEST로 변경

### Phase 4: TEST (전체 검증)
전체 테스트 스위트를 실행하여 수정이 기존 기능을 깨뜨리지 않았는지 확인한다.

실행할 테스트:
1. `cd flutter_app/textbridge_app && flutter test` (Dart 단위 테스트 전체)
2. Firmware 빌드: `source ~/.zmk_env/bin/activate && export ZEPHYR_SDK_INSTALL_DIR=~/.zephyr-sdk-0.16.3 && cd zmk_keychron/app && west build --pristine -b keychron -- -DSHIELD=keychron_b6_us`
3. Python 도구 문법 검사: `python3 -m py_compile tools/test_phase3_protocol.py` 등

규칙:
- 모든 테스트 통과 → phase를 REVIEW로, cycle + 1
- 테스트 실패 → 실패한 테스트 수정 시도 → 재실행
- 2번 시도 후에도 실패 → 해당 수정 되돌리고 다음 사이클로

검증 완료 후:
- 결과를 `.ralph-cycle-state.md`에 기록
- phase를 REVIEW로 변경, cycle + 1

## 종료 조건

다음 중 하나를 만족하면 종료:

1. **REVIEW에서 CRITICAL/HIGH 이슈가 0개** → 프로젝트 건강함
2. **3연속 사이클에서 새로운 수정 사항이 0개** → 수렴 완료
3. **cycle > 10** → 안전 장치

종료 시 반드시 출력:
```
<promise>REVIEW CYCLE COMPLETE</promise>
```

## 상태 파일 형식

```markdown
# Ralph Cycle State

## Current
- cycle: 1
- phase: REVIEW
- timestamp: 2026-02-24T00:00:00

## Cycle 1
### REVIEW findings
(검토 결과 요약)

### PLAN
(수정 계획)

### FIX results
(수정 결과)

### TEST results
(테스트 결과)

## Completed Fixes (전체 사이클 누적)
- [x] FW C-01: tb_conn 경쟁조건 mutex 추가
- [x] App C-01: responseQueue.clear() 추가
...
```

## 중요 원칙

1. **매 반복 시작 시 반드시 상태 파일을 읽어라** — 이전 작업을 중복하지 마라
2. **한 반복에서 한 phase만 수행하라** — REVIEW 하나, PLAN 하나, FIX 하나, TEST 하나
3. **수정은 보수적으로** — 확실한 것만 고치고, 애매한 건 다음 사이클로
4. **테스트가 왕** — 테스트 실패하면 무조건 되돌려라
5. **상태 파일을 항상 업데이트하라** — 다음 반복의 나 자신을 위해
