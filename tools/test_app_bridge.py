#!/usr/bin/env python3
"""
TextBridge 앱-펌웨어 브릿지 테스트

Flutter 앱이 생성한 키코드/프로토콜 바이트를 그대로 읽어서
실제 BLE로 키보드 펌웨어에 전송하고 HID 출력을 검증한다.

파이프라인: Dart(textToKeycodes) → JSON → Python(BLE) → Firmware → HID → PC

사전 준비:
    cd flutter_app/textbridge_app && flutter test test/export_keycodes_test.dart

사용법:
    python3 test_app_bridge.py --test all
    python3 test_app_bridge.py --test hangul_mixed_win
    python3 test_app_bridge.py --test ascii_hello,hangul_pure_win
    python3 test_app_bridge.py --list
    python3 test_app_bridge.py --compare hangul_mixed_win   # Dart vs Python 비교만
"""

import asyncio
import argparse
import json
import os
import sys

try:
    from bleak import BleakScanner, BleakClient
except ImportError:
    print("bleak 필요: pip3 install bleak")
    sys.exit(1)

# test_phase3_protocol에서 공통 인프라 재사용
from test_phase3_protocol import (
    TB_SVC_UUID, TB_TX_UUID, TB_RX_UUID,
    RESP_ACK, RESP_NACK, RESP_READY, RESP_DONE, RESP_ERROR, RESP_NAMES,
    CMD_KEYCODE, CMD_START, CMD_DONE,
    TextBridgeClient,
    via_start_pairing, scan,
    hangul_to_keycodes, make_keycode, make_start, make_done,
    TOGGLE_WIN, TOGGLE_MAC, _toggle_key,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(SCRIPT_DIR, "dart_keycodes.json")


def load_dart_keycodes() -> dict:
    """dart_keycodes.json 로드"""
    if not os.path.exists(JSON_PATH):
        print(f"[ERROR] {JSON_PATH} 파일 없음.")
        print("  먼저 Dart 익스포트를 실행하세요:")
        print("  cd flutter_app/textbridge_app && flutter test test/export_keycodes_test.dart")
        sys.exit(1)

    with open(JSON_PATH) as f:
        return json.load(f)


def compare_keycodes(case_name: str, dart_data: dict) -> bool:
    """Dart 앱 키코드와 Python 키코드를 비교"""
    text = dart_data["text"]
    os_name = dart_data["os"]
    dart_keycodes = [tuple(kp) for kp in dart_data["keycodes"]]

    # Python 쪽 키코드 생성
    import test_phase3_protocol as proto
    saved_toggle = proto._toggle_key
    if os_name == "macOS":
        proto._toggle_key = TOGGLE_MAC
    else:
        proto._toggle_key = TOGGLE_WIN

    py_keycodes = hangul_to_keycodes(text)
    proto._toggle_key = saved_toggle

    # 비교
    match = dart_keycodes == py_keycodes
    if match:
        print(f"  [MATCH] {case_name}: Dart={len(dart_keycodes)}개 == Python={len(py_keycodes)}개")
    else:
        print(f"  [DIFF] {case_name}: Dart={len(dart_keycodes)}개, Python={len(py_keycodes)}개")
        # 차이점 상세 출력
        max_len = max(len(dart_keycodes), len(py_keycodes))
        for i in range(max_len):
            d = dart_keycodes[i] if i < len(dart_keycodes) else None
            p = py_keycodes[i] if i < len(py_keycodes) else None
            if d != p:
                d_str = f"(0x{d[0]:02x},0x{d[1]:02x})" if d else "---"
                p_str = f"(0x{p[0]:02x},0x{p[1]:02x})" if p else "---"
                print(f"    [{i}] Dart={d_str}  Python={p_str}")
    return match


async def send_dart_keycodes(tb: TextBridgeClient, case_name: str, dart_data: dict) -> bool:
    """Dart 앱이 생성한 프로토콜 패킷을 그대로 BLE로 전송"""
    text = dart_data["text"]
    os_name = dart_data["os"]
    packets = dart_data["packets"]
    keycodes = dart_data["keycodes"]

    print(f"\n=== Bridge Test: {case_name} ===")
    print(f"  텍스트: '{text}' (OS={os_name})")
    print(f"  키코드: {len(keycodes)}개, 패킷: {len(packets)}개")

    # 프로토콜 패킷을 순서대로 전송
    for pkt_info in packets:
        pkt_type = pkt_info["type"]
        raw_bytes = bytes(pkt_info["bytes"])

        if pkt_type == "START":
            await tb.write(raw_bytes, f"START (Dart)")
            resp = await tb.wait_response(RESP_READY)
            if not resp or resp[0] != RESP_READY:
                print(f"  [FAIL] READY 미수신")
                return False

        elif pkt_type == "KEYCODE":
            seq = pkt_info["seq"]
            count = pkt_info["count"]
            await tb.write(raw_bytes, f"KEYCODE seq={seq} count={count} (Dart)")
            resp = await tb.wait_response(RESP_ACK, timeout=10.0)
            if not resp:
                print(f"  [FAIL] ACK 미수신 (seq={seq})")
                return False
            if resp[0] == RESP_NACK:
                print(f"  [RETRY] NACK, 1초 후 재전송")
                await asyncio.sleep(1.0)
                await tb.write(raw_bytes, f"KEYCODE retry seq={seq} (Dart)")
                resp = await tb.wait_response(RESP_ACK, timeout=10.0)
                if not resp or resp[0] != RESP_ACK:
                    print(f"  [FAIL] 재전송 후에도 ACK 미수신")
                    return False
            elif resp[0] == RESP_ERROR:
                print(f"  [FAIL] ERROR 수신")
                return False

        elif pkt_type == "DONE":
            await tb.write(raw_bytes, f"DONE (Dart)")
            resp = await tb.wait_response(RESP_DONE)
            if not resp or resp[0] != RESP_DONE:
                print(f"  [WARN] DONE 응답 미수신")

    return True


async def run_bridge_tests(address: str, case_names: list[str], dart_data: dict):
    """브릿지 테스트 실행"""
    print(f"\n[CONN] {address} 연결 중...")

    async with BleakClient(address) as client:
        tb = TextBridgeClient(client)
        await tb.connect()

        results = {}
        for name in case_names:
            if name not in dart_data:
                print(f"\n[SKIP] '{name}' — dart_keycodes.json에 없음")
                continue
            try:
                ok = await send_dart_keycodes(tb, name, dart_data[name])
                results[name] = ok
                status = "PASS" if ok else "FAIL"
                print(f"\n  [{status}] {name}")
                await asyncio.sleep(0.5)
            except Exception as e:
                results[name] = False
                print(f"\n  [ERROR] {name}: {e}")

        # 결과 요약
        print("\n" + "=" * 50)
        print("브릿지 테스트 결과 (Dart 앱 → BLE → 펌웨어):")
        for name, ok in results.items():
            status = "PASS" if ok else "FAIL"
            text = dart_data[name]["text"]
            print(f"  [{status}] {name}: '{text}'")
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        print(f"\n  {passed}/{total} 통과")
        print("=" * 50)


async def main():
    parser = argparse.ArgumentParser(
        description="TextBridge 앱-펌웨어 브릿지 테스트 (Dart 키코드 → BLE → 펌웨어)")
    parser.add_argument("--list", action="store_true",
                        help="사용 가능한 테스트 케이스 목록")
    parser.add_argument("--compare", type=str, default=None,
                        help="Dart vs Python 키코드 비교 (BLE 전송 없이). 'all' 또는 케이스명")
    parser.add_argument("--test", type=str, default=None,
                        help="BLE 전송 테스트. 'all' 또는 콤마 구분 케이스명")
    args = parser.parse_args()
    dart_data = load_dart_keycodes()

    # --list: 테스트 케이스 목록
    if args.list:
        print(f"\nDart 키코드 테스트 케이스 ({JSON_PATH}):\n")
        for name, data in dart_data.items():
            text = data["text"]
            os_name = data["os"]
            kc = data["keycode_count"]
            chunks = data["chunk_count"]
            print(f"  {name:25s} OS={os_name:7s} 키코드={kc:3d} 청크={chunks:2d}  '{text}'")
        return

    # --compare: Dart vs Python 키코드 비교 (오프라인, BLE 불필요)
    if args.compare:
        case_names = list(dart_data.keys()) if args.compare == "all" else \
                     [n.strip() for n in args.compare.split(",")]

        print(f"\n[COMPARE] Dart vs Python 키코드 비교 ({len(case_names)}개)")
        print("=" * 50)
        all_match = True
        for name in case_names:
            if name not in dart_data:
                print(f"  [SKIP] '{name}' 없음")
                continue
            if not compare_keycodes(name, dart_data[name]):
                all_match = False

        print("=" * 50)
        if all_match:
            print(f"  모두 일치 ({len(case_names)}개)")
        else:
            print(f"  [WARN] 불일치 발견 — Dart 앱과 Python 구현이 다름")
        return

    # --test: BLE 전송 테스트
    if args.test:
        if args.test == "all":
            # macOS에서 실행: Windows+한글 케이스는 제외 (LANG1 토글이 macOS에서 안 됨)
            def _has_korean(text):
                return any(0xAC00 <= ord(c) <= 0xD7A3 for c in text)
            case_names = [n for n, d in dart_data.items()
                          if d["os"] == "macOS" or not _has_korean(d["text"])]
        else:
            case_names = [n.strip() for n in args.test.split(",")]

        # 먼저 Dart vs Python 비교 수행
        print(f"\n[STEP 0] Dart vs Python 키코드 비교")
        for name in case_names:
            if name in dart_data:
                compare_keycodes(name, dart_data[name])

        # macOS 고정
        import test_phase3_protocol as proto
        proto._toggle_key = TOGGLE_MAC

        # VIA 페어링
        print("\n[STEP 1] VIA 명령으로 TextBridge 광고 시작")
        if not via_start_pairing():
            print("[WARN] VIA 페어링 실패. 수동으로 Fn+1을 누르세요.")
        else:
            print("[PAIR] 광고 시작 대기 (2초)...")
            await asyncio.sleep(2.0)

        # BLE 스캔
        print("\n[STEP 2] BLE 스캔")
        devices = await scan(10)
        if not devices:
            return
        address = devices[0].address

        # 테스트 실행
        await run_bridge_tests(address, case_names, dart_data)
        return

    # 인자 없으면 도움말
    parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
