#!/usr/bin/env python3
"""
TextBridge 한글 전송 테스트
- 순수 한글, 한영 혼합, 쌍자음/복합모음/겹받침 테스트
- 각 텍스트를 BLE로 전송 후 Enter 키코드 추가 (Claude Code 검증용)

사용법:
    python3 test_phase5_hangul.py --test pure        # 순수 한글
    python3 test_phase5_hangul.py --test mixed       # 한영 혼합
    python3 test_phase5_hangul.py --test complex     # 쌍자음/겹받침
    python3 test_phase5_hangul.py --test all         # 전체
"""

import asyncio
import argparse
import sys

try:
    from bleak import BleakClient
except ImportError:
    print("bleak 필요: pip3 install bleak")
    sys.exit(1)

from test_phase3_protocol import (
    TextBridgeClient, scan, via_start_pairing,
    TOGGLE_MAC,
)

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


async def main():
    parser = argparse.ArgumentParser(description="TextBridge 한글 전송 테스트")
    parser.add_argument("--test", type=str, default="all",
                        help="테스트: pure, mixed, complex, all")
    args = parser.parse_args()

    import test_phase3_protocol as proto
    proto._toggle_key = TOGGLE_MAC

    print("pairing...", end=" ", flush=True)
    via_start_pairing()
    await asyncio.sleep(2.0)
    print("ok")

    print("scanning...", end=" ", flush=True)
    devices = await scan(10)
    if not devices:
        print("not found")
        return
    print(devices[0].address)

    groups = (
        list(TEST_CASES.keys()) if args.test == "all"
        else [t.strip() for t in args.test.split(",")]
    )

    for group_name in groups:
        if group_name not in TEST_CASES:
            continue
        group = TEST_CASES[group_name]

        async with BleakClient(devices[0].address) as client:
            tb = TextBridgeClient(client)
            await tb.connect()
            await tb.set_delay(press_delay=5, release_delay=5, combo_delay=20, toggle_press=20, toggle_delay=100, warmup_delay=50)

            for text in group["texts"]:
                # 매 텍스트 전 딜레이 재설정 (값 유실 방지)
                await tb.set_delay(press_delay=15, release_delay=15, combo_delay=30, toggle_press=20, toggle_delay=100, warmup_delay=50)
                print(f"{text}...", end=" ", flush=True)
                ok = await tb.send_text(text, append_enter=True)
                print("ok" if ok else "FAIL")
                await asyncio.sleep(1.0)  # IME 상태 안정화 대기

        await asyncio.sleep(2.0)


if __name__ == "__main__":
    asyncio.run(main())
