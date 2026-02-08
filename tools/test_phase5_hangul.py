#!/usr/bin/env python3
"""
TextBridge Phase 5: 한글 전송 E2E 테스트
- 순수 한글, 한영 혼합, 쌍자음/복합모음/겹받침 테스트
- pynput으로 PC 캡처 결과와 원본 비교
- test_phase3_protocol.py의 BLE/프로토콜 로직 재사용

사용법:
    python3 test_phase5_hangul.py --test pure        # 순수 한글
    python3 test_phase5_hangul.py --test mixed       # 한영 혼합
    python3 test_phase5_hangul.py --test complex     # 쌍자음/겹받침
    python3 test_phase5_hangul.py --test all         # 전체
    python3 test_phase5_hangul.py --no-verify        # pynput 검증 스킵
"""

import asyncio
import argparse
import sys
import time

try:
    from bleak import BleakClient
except ImportError:
    print("bleak 필요: pip3 install bleak")
    sys.exit(1)

from test_phase3_protocol import (
    TB_RX_UUID,
    TextBridgeClient, HIDVerifier, scan, via_start_pairing,
    hangul_to_keycodes, make_start, make_keycode, make_done,
    RESP_READY, RESP_ACK, RESP_DONE,
)


async def send_keycodes(tb: TextBridgeClient, keycodes: list, chunk_size: int = 8) -> bool:
    """Send pre-computed keycodes via protocol."""
    chunks = []
    for i in range(0, len(keycodes), chunk_size):
        chunks.append(keycodes[i:i + chunk_size])

    await tb.write(make_start(0, len(chunks)), "START")
    resp = await tb.wait_response(RESP_READY)
    if not resp or resp[0] != RESP_READY:
        print("  [FAIL] READY 미수신")
        return False

    for i, chunk in enumerate(chunks):
        seq = (i + 1) % 256
        await tb.write(make_keycode(seq, chunk), f"KEYCODE seq={seq} count={len(chunk)}")
        resp = await tb.wait_response(RESP_ACK, timeout=10.0)
        if not resp or resp[0] != RESP_ACK:
            print(f"  [FAIL] ACK 미수신 (chunk {i+1}/{len(chunks)})")
            return False

    done_seq = (len(chunks) + 1) % 256
    await tb.write(make_done(done_seq), "DONE")
    await tb.wait_response(RESP_DONE)
    return True


# ============ Test cases ============

TEST_CASES = {
    "pure": {
        "name": "순수 한글",
        "texts": [
            "안녕하세요",
            "대한민국",
            "프로그래밍",
        ],
    },
    "mixed": {
        "name": "한영 혼합",
        "texts": [
            "Hello 안녕 World",
            "print('안녕하세요')",
            "// 주석입니다 comment",
            "변수명 = variable_name",
        ],
    },
    "complex": {
        "name": "쌍자음/복합모음/겹받침",
        "texts": [
            "까닭없이",
            "왕관",
            "값싼",
            "읽다",
            "앉다",
        ],
    },
}


async def run_test_group(
    address: str,
    group_name: str,
    verifier: HIDVerifier = None,
) -> bool:
    """Run a group of Korean text tests."""
    group = TEST_CASES[group_name]
    print(f"\n{'='*50}")
    print(f"테스트 그룹: {group['name']}")
    print(f"{'='*50}")

    results = []

    async with BleakClient(address) as client:
        tb = TextBridgeClient(client, verifier=verifier)
        await tb.connect()

        for text in group["texts"]:
            print(f"\n--- '{text}' ---")
            keycodes = hangul_to_keycodes(text)
            print(f"  키코드: {len(keycodes)}개")

            if verifier:
                verifier.clear()

            ok = await send_keycodes(tb, keycodes)
            if not ok:
                results.append((text, False))
                continue

            if verifier:
                # Wait for HID injection
                wait_time = len(keycodes) * 0.02 + 2.0
                await asyncio.sleep(wait_time)
                captured = verifier.get_captured()
                if captured == text:
                    print(f"  [PASS] 캡처 일치: '{captured}'")
                    results.append((text, True))
                else:
                    print(f"  [FAIL] 불일치")
                    print(f"    기대: '{text}'")
                    print(f"    캡처: '{captured}'")
                    results.append((text, False))
            else:
                print(f"  [OK] 프로토콜 전송 완료 (HID 검증 스킵)")
                results.append((text, True))

            await asyncio.sleep(1.0)

    # Summary
    passed = sum(1 for _, ok in results if ok)
    print(f"\n  {group['name']}: {passed}/{len(results)} 통과")
    return passed == len(results)


async def main():
    parser = argparse.ArgumentParser(description="TextBridge 한글 E2E 테스트")
    parser.add_argument("--test", type=str, default="all",
                        help="테스트: pure, mixed, complex, all")
    parser.add_argument("--address", type=str, default=None)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--no-pair", action="store_true")
    parser.add_argument("--no-verify", action="store_true")
    args = parser.parse_args()

    if not args.no_pair:
        print("\n[STEP 1] VIA 명령으로 TextBridge 광고 시작")
        if not via_start_pairing():
            print("[WARN] VIA 페어링 실패. 수동으로 Fn+1을 누르세요.")
        else:
            await asyncio.sleep(2.0)

    verifier = None
    if not args.no_verify:
        verifier = HIDVerifier()
        if not verifier.start():
            print("[WARN] pynput 초기화 실패.")
            verifier = None

    try:
        address = args.address
        if not address:
            print("\n[STEP 2] BLE 스캔")
            devices = await scan(args.timeout)
            if not devices:
                return
            address = devices[0].address

        groups = (
            list(TEST_CASES.keys()) if args.test == "all"
            else [t.strip() for t in args.test.split(",")]
        )

        results = {}
        for group_name in groups:
            if group_name not in TEST_CASES:
                print(f"[SKIP] 알 수 없는 그룹: {group_name}")
                continue
            ok = await run_test_group(address, group_name, verifier)
            results[group_name] = ok
            await asyncio.sleep(2.0)

        print(f"\n{'='*50}")
        print("한글 E2E 테스트 결과:")
        for name, ok in results.items():
            print(f"  [{'PASS' if ok else 'FAIL'}] {TEST_CASES[name]['name']}")
        print(f"{'='*50}")

    finally:
        if verifier:
            verifier.stop()


if __name__ == "__main__":
    asyncio.run(main())
