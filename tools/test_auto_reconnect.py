#!/usr/bin/env python3
"""TextBridge 자동 재연결 테스트

disconnect→reconnect 반복으로 자동 재광고 검증.
기존 test_phase3_protocol.py 인프라 재사용.

사용법:
    python3 test_auto_reconnect.py
    python3 test_auto_reconnect.py --repeats 10
"""

import asyncio
import argparse
import sys
import time

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print("bleak 필요: pip3 install bleak")
    sys.exit(1)

from test_phase3_protocol import (
    via_start_pairing, scan, TextBridgeClient,
    TB_SVC_UUID, DEVICE_NAME,
)

RECONNECT_WAIT = 2.5  # directed adv 1.28s + discoverable fallback margin


def via_soft_reset() -> bool:
    """VIA Raw HID로 0xFD 전송하여 MCU 소프트 리셋"""
    try:
        import hid
    except ImportError:
        print("[RESET] hidapi 미설치")
        return False

    VENDOR_ID = 0x3434
    PRODUCT_ID = 0x0761
    RAW_USAGE_PAGE = 0xFF60

    path = None
    for device in hid.enumerate(VENDOR_ID, PRODUCT_ID):
        if device['usage_page'] == RAW_USAGE_PAGE:
            path = device['path']
            break

    if not path:
        print("[RESET] 키보드 USB 미연결")
        return False

    try:
        device = hid.device()
        device.open_path(path)
        data = [0x00] * 33
        data[1] = 0xFD
        device.write(data)
        device.close()
        return True
    except Exception as e:
        print(f"[RESET] 실패: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="TextBridge 자동 재연결 테스트")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--skip-reset", action="store_true",
                        help="초기 소프트 리셋 건너뛰기")
    args = parser.parse_args()

    # Phase 0: 소프트 리셋 (BLE 상태 초기화)
    if not args.skip_reset:
        print("=== Phase 0: MCU soft reset ===")
        print("  Resetting...", end=" ", flush=True)
        if via_soft_reset():
            print("ok")
            print("  Waiting 8s for reboot + BLE init...")
            await asyncio.sleep(8)
        else:
            print("SKIP (keyboard not found via USB)")

    # Phase 1: 초기 페어링 + 텍스트 전송
    print("\n=== Phase 1: Initial pairing ===")
    print("  VIA pairing...", end=" ", flush=True)
    via_start_pairing()
    await asyncio.sleep(2.0)
    print("ok")

    print("  Scanning...", end=" ", flush=True)
    devices = await scan(10)
    if not devices:
        print("FAIL: TextBridge not found")
        return 1
    addr = devices[0].address
    print(addr)

    print("  Connecting + sending...", end=" ", flush=True)
    async with BleakClient(addr) as client:
        tb = TextBridgeClient(client)
        await tb.connect()
        ok = await tb.send_text("initial")
        print(f"{'PASS' if ok else 'FAIL'}")
        if not ok:
            return 1
    # context exit → disconnect → firmware auto-readvertise

    # Phase 2: Disconnect→Reconnect 반복
    print(f"\n=== Phase 2: Reconnect cycle ({args.repeats}x) ===")
    times = []

    for i in range(args.repeats):
        print(f"\n--- Round {i+1}/{args.repeats} ---")
        t0 = time.time()

        # 재광고 대기
        print(f"  Waiting {RECONNECT_WAIT}s for firmware re-advertise...")
        await asyncio.sleep(RECONNECT_WAIT)

        # 재스캔
        print("  Scanning...", end=" ", flush=True)
        devices = await scan(5)
        if not devices:
            print("FAIL: not found after disconnect")
            return 1
        print(f"found {devices[0].address}")

        # 재연결 + 전송
        print("  Connecting + sending...", end=" ", flush=True)
        try:
            async with BleakClient(devices[0].address) as client:
                tb = TextBridgeClient(client)
                await tb.connect()
                ok = await tb.send_text(f"reconnect{i+1}")
                elapsed = time.time() - t0
                times.append(elapsed)
                print(f"{'PASS' if ok else 'FAIL'} ({elapsed:.1f}s)")
                if not ok:
                    return 1
        except Exception as e:
            print(f"FAIL: {e}")
            return 1
        # context exit → disconnect → firmware auto-readvertise

    # 결과
    avg = sum(times) / len(times)
    print(f"\n=== ALL {args.repeats} RECONNECTS PASSED ===")
    print(f"  Avg cycle time: {avg:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
