# 펌웨어 개선 태스크

**대상**: `zmk_keychron/app/src/textbridge.c`, `zmk_keychron/app/src/usb_hid.c`
**기준**: 2026-02-10 코드 리뷰 결과

---

## 즉시 수정 (이번 세션)

### FW-001: 일반 modifier atomic 2-report + 토글 combo_delay 분리

**심각도**: 높음 — Shift 단독 리포트 제거 + 속도 2배 + 토글 안정성
**파일**: `textbridge.c`

**현재 문제**:
- `combo_delay`가 Shift+A와 Ctrl+Space에 동일하게 적용됨 (line 218, 229)
- Shift+A는 combo_delay 불필요 (atomic이면 됨)
- Ctrl+Space는 macOS IME 인식에 충분한 딜레이 필요
- Shift만 담긴 리포트가 전송됨 → macOS CJK 토글 오인식 위험 (HF-002)

**수정**:
```
is_toggle=false, mod≠0 → atomic 2-report (mod+key 동시, combo_delay 미사용)
is_toggle=true,  mod≠0 → 4-report (combo_delay 사용, Ctrl+Space용)
is_toggle=true,  mod=0 → 2-report (LANG1, modifier 없음)
```

combo_delay는 atomic 적용 후 토글 조합에서만 사용되므로 별도 파라미터 추가 불필요.

### FW-002: DONE 시 HID 클린업

**파일**: `textbridge.c` line 340-349

DONE 핸들러에서 `tb_cleanup_transmission()` 호출로 통일. 잔여 modifier/key 상태 제거.

### FW-003: bt_gatt_notify 반환값 로깅

**파일**: `textbridge.c` line 133

`bt_gatt_notify()` 반환값 로깅. 연결 끊김 시 silent failure 방지.

### FW-004: 전용 워크큐 스택 2048B

**파일**: `textbridge.c` line 184

1024B → 2048B. SRAM 여유 66%, 스택 오버플로 안전 마진.

### FW-005: SET_DELAY 상태 검증

**파일**: `textbridge.c` line 364

`tb_transmitting == true`이면 NACK 응답. 주입 중 딜레이 변경 방지.

### FW-006: tb_injecting volatile 선언

**파일**: `textbridge.c` line 73

BLE 콜백 스레드와 inject 워크큐 스레드에서 접근. `volatile` 없으면 컴파일러 최적화로 재읽기 생략 가능.

---

## 보류 (검증 비용 높음 또는 영향 낮음)

| 항목 | 사유 |
|------|------|
| ABORT inject work 취소 | `k_work_cancel_sync`가 BLE 콜백 블로킹. 현재 플래그 방식 합리적. 최악 1키 추가. |
| usb_hid.c sem fall-through | ZMK 포크 이슈. TextBridge 범위 밖. MEMORY에 기록됨. |
| BLE Connection Interval | 효과 크지만 ZMK 상호작용 검증 비용 높음. |
| 연속 세션 warmup 스킵 | 세션당 50ms 1회. 체감 없음. |
| ~~자동 광고 재시작~~ | **완료** (2026-02-24). connectable adv + accept list 필터, ADV_RECONN_TIME_OUT 10초. |
| NVS 딜레이 영속화 | SET_DELAY ACK 1회(~15ms) 절약. 플래시 마모 대비 가치 없음. |
| 펌웨어 버전 쿼리 | 앱/펌웨어 1:1 페어. 나중에. |
| 토글키 하드코딩 | 토글키 2종류뿐. 복잡도 대비 이득 없음. |
| 매직넘버 0x07 | 코드 스타일. 기능 변경 아님. |
