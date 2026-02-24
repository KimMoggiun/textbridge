#!/usr/bin/env python3
"""
실제 환경 재현 재연결 타이밍 테스트

macOS BLE 연결을 명시적으로 끊은 후 재연결 시간을 측정.
폰에서 BLE 연결이 끊기고 재연결되는 실제 시나리오를 재현한다.

시나리오:
  1. BLE 모드에서 키보드 BLE에 연결
  2. macOS에서 명시적 disconnect (폰이 연결 끊기는 상황 재현)
  3. USB 모드 전환 (키보드 광고 중단)
  4. BLE 모드 전환 (키보드 재광고 시작)
  5. BLE 스캔 → 재연결 시간 측정

Usage:
    python3 test_reconnect_real.py [--cycles 5]
"""

import asyncio
import argparse
import sys
import time

try:
    from bleak import BleakScanner, BleakClient
except ImportError:
    print("Error: bleak not installed. Run: pip install bleak")
    sys.exit(1)

from tb_mode import send_command, CMD_STATUS, CMD_MODE_USB, CMD_MODE_BLE

TB_SVC_UUID = "12340000-1234-1234-1234-123456789abc"
TB_DEVICE_NAME = "TextBridge"
KB_DEVICE_NAME = "Keychron B6 Pro"

ZMK_ADV = {0: "NONE", 1: "DIR", 2: "CONN", 3: "RECONN", 4: "PAIR"}


def get_status():
    resp = send_command(CMD_STATUS, read_response=True)
    if resp and len(resp) > 6:
        return {
            "transport": resp[1],
            "tb_adv": resp[2], "tb_conn": resp[3], "tb_bonded": resp[4],
            "zmk_adv": resp[5], "zmk_conn": resp[6],
        }
    return None


def status_str(s):
    if not s:
        return "no response"
    return (f"t={s['transport']} tb_adv={s['tb_adv']} tb_conn={s['tb_conn']} "
            f"zmk_adv={ZMK_ADV.get(s['zmk_adv'],'?')} zmk_conn={s['zmk_conn']}")


async def ble_find_device(name_match, svc_uuid=None, timeout=12.0):
    """BLE 스캔으로 디바이스 찾기. BLEDevice 반환."""
    scanner = BleakScanner(service_uuids=[svc_uuid] if svc_uuid else None)
    await scanner.start()
    deadline = time.time() + timeout
    found = None
    while time.time() < deadline:
        for addr, (dev, adv) in scanner.discovered_devices_and_advertisement_data.items():
            name = dev.name or adv.local_name or ""
            uuids = [str(u).lower() for u in (adv.service_uuids or [])]
            if name_match in name or (svc_uuid and svc_uuid.lower() in uuids):
                found = dev
                break
        if found:
            break
        await asyncio.sleep(0.05)
    await scanner.stop()
    return found


async def ble_connect(dev, timeout=10.0):
    """BLEDevice에 연결. BleakClient 반환 (실패 시 None)."""
    client = BleakClient(dev, timeout=timeout)
    try:
        await client.connect()
        return client
    except Exception as e:
        print(f"    연결 실패: {e}")
        return None


async def test_reconnect_cycle(label, name_match, svc_uuid, pre_switch_fn, post_switch_fn):
    """
    1. post_switch_fn() 호출로 해당 모드 진입
    2. BLE 스캔 → 연결
    3. pre_switch_fn() 호출로 다른 모드 전환 (연결 유지 상태)
    4. macOS에서 명시적 disconnect
    5. 잠시 대기 (연결 완전히 끊김 확인)
    6. post_switch_fn() 호출로 다시 해당 모드 진입
    7. BLE 스캔 → 재연결 시간 측정

    Returns: (scan_time, connect_time, total_time) or None
    """
    # Step 1: 해당 모드 진입 + 연결
    post_switch_fn()
    await asyncio.sleep(1)

    dev = await ble_find_device(name_match, svc_uuid, timeout=10.0)
    if not dev:
        print(f"    [{label}] 디바이스 못 찾음 (초기 연결)")
        return None

    client = await ble_connect(dev)
    if not client:
        print(f"    [{label}] 초기 연결 실패")
        return None
    print(f"    [{label}] 초기 연결 완료: {dev.address}")

    # Step 2: 다른 모드로 전환
    pre_switch_fn()
    await asyncio.sleep(0.5)

    # Step 3: macOS에서 명시적 disconnect (폰이 끊기는 상황 재현)
    try:
        await client.disconnect()
    except Exception:
        pass  # 이미 끊어졌을 수 있음
    print(f"    [{label}] BLE 연결 끊음 (폰 시뮬레이션)")

    # Step 4: 잠시 대기 — 펌웨어가 disconnect 감지하도록
    await asyncio.sleep(1)

    s = get_status()
    print(f"    [{label}] 끊긴 후 상태: {status_str(s)}")

    # Step 5: 다시 해당 모드 진입 → 재광고 시작 → 스캔+연결 시간 측정
    t_start = time.time()
    post_switch_fn()

    # 스캔
    dev2 = await ble_find_device(name_match, svc_uuid, timeout=12.0)
    t_scan = time.time()
    scan_time = t_scan - t_start

    if not dev2:
        print(f"    [{label}] 재스캔 실패 ({scan_time:.1f}s)")
        return None

    # 연결
    client2 = await ble_connect(dev2)
    t_conn = time.time()
    connect_time = t_conn - t_scan
    total = t_conn - t_start

    if client2:
        await client2.disconnect()
        return scan_time, connect_time, total
    else:
        return scan_time, None, None


async def run_test(cycles=5):
    print("=" * 60)
    print("실제 환경 재현 재연결 타이밍 테스트")
    print("=" * 60)

    s = get_status()
    if not s:
        print("ERROR: VIA 통신 불가")
        return
    print(f"현재: {status_str(s)}")

    def to_usb():
        send_command(CMD_MODE_USB, read_response=False)

    def to_ble():
        send_command(CMD_MODE_BLE, read_response=False)

    kb_results = []
    tb_results = []

    for cycle in range(1, cycles + 1):
        print(f"\n{'─' * 60}")
        print(f"[Cycle {cycle}/{cycles}]")

        # Keyboard BLE: BLE 모드에서 연결 → USB로 전환 → disconnect → BLE 복귀 → 재연결
        print(f"\n  Keyboard BLE 재연결:")
        result = await test_reconnect_cycle(
            "KB", KB_DEVICE_NAME, None,
            pre_switch_fn=to_usb,
            post_switch_fn=to_ble,
        )
        if result:
            scan_t, conn_t, total_t = result
            if total_t is not None:
                print(f"    [KB] 스캔: {scan_t:.2f}s, 연결: {conn_t:.2f}s, 전체: {total_t:.2f}s")
                kb_results.append(total_t)
            else:
                print(f"    [KB] 발견({scan_t:.2f}s) 연결 실패")
                kb_results.append(None)
        else:
            kb_results.append(None)

        await asyncio.sleep(2)

        # TextBridge: USB 모드에서 연결 → BLE로 전환 → disconnect → USB 복귀 → 재연결
        print(f"\n  TextBridge 재연결:")
        result = await test_reconnect_cycle(
            "TB", TB_DEVICE_NAME, TB_SVC_UUID,
            pre_switch_fn=to_ble,
            post_switch_fn=to_usb,
        )
        if result:
            scan_t, conn_t, total_t = result
            if total_t is not None:
                print(f"    [TB] 스캔: {scan_t:.2f}s, 연결: {conn_t:.2f}s, 전체: {total_t:.2f}s")
                tb_results.append(total_t)
            else:
                print(f"    [TB] 발견({scan_t:.2f}s) 연결 실패")
                tb_results.append(None)
        else:
            tb_results.append(None)

        await asyncio.sleep(2)

    # USB로 복귀
    to_usb()

    # 결과 요약
    print(f"\n{'=' * 60}")
    print("결과 요약")
    print(f"{'=' * 60}")

    for label, results in [("Keyboard BLE", kb_results), ("TextBridge", tb_results)]:
        print(f"\n  {label}:")
        valid = [t for t in results if t is not None]
        for i, t in enumerate(results, 1):
            print(f"    Cycle {i}: {f'{t:.2f}s' if t is not None else 'FAIL'}")
        if valid:
            print(f"    평균: {sum(valid)/len(valid):.2f}s  "
                  f"최소: {min(valid):.2f}s  최대: {max(valid):.2f}s")
        else:
            print(f"    전부 실패")

    print(f"\n{'=' * 60}")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=5)
    args = parser.parse_args()
    await run_test(cycles=args.cycles)


if __name__ == "__main__":
    asyncio.run(main())
