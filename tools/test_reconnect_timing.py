#!/usr/bin/env python3
"""
TextBridge/Keyboard 모드 전환 재연결 타이밍 테스트

USB 모드에서 TextBridge, BLE 모드에서 키보드 BLE의
광고 시작 시간 + BLE 스캔 발견 시간 + 연결 시간을 5회 반복 측정.

사전 조건: TextBridge + Keyboard BLE 둘 다 macOS와 본딩 완료.

Usage:
    python3 test_reconnect_timing.py [--cycles 5]
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

# TextBridge
TB_SVC_UUID = "12340000-1234-1234-1234-123456789abc"
TB_DEVICE_NAME = "TextBridge"
KB_DEVICE_NAME = "Keychron B6 Pro"


def get_status():
    resp = send_command(CMD_STATUS, read_response=True)
    if resp and len(resp) > 6:
        return {
            "transport": resp[1],
            "tb_adv": resp[2],
            "tb_conn": resp[3],
            "tb_bonded": resp[4],
            "zmk_adv": resp[5],
            "zmk_conn": resp[6],
        }
    return None


def switch_usb():
    send_command(CMD_MODE_USB, read_response=False)


def switch_ble():
    send_command(CMD_MODE_BLE, read_response=False)


async def poll_until(key, expected, timeout=10.0, poll_ms=50):
    """VIA 폴링으로 상태 대기. 도달 시간 반환."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = get_status()
        if s and s[key] == expected:
            return time.time() - t0
        await asyncio.sleep(poll_ms / 1000)
    return None


async def ble_scan_and_connect(name_match, svc_uuid=None, scan_timeout=10.0):
    """BLE 스캔 → 연결. (scan_time, connect_time, total_time) 반환."""
    t_start = time.time()

    found_dev = None
    scanner = BleakScanner(service_uuids=[svc_uuid] if svc_uuid else None)
    await scanner.start()
    deadline = t_start + scan_timeout
    while time.time() < deadline:
        for addr, (dev, adv) in scanner.discovered_devices_and_advertisement_data.items():
            dev_name = dev.name or adv.local_name or ""
            svc_uuids = [str(u).lower() for u in (adv.service_uuids or [])]
            if name_match in dev_name or (svc_uuid and svc_uuid.lower() in svc_uuids):
                found_dev = dev
                break
        if found_dev:
            break
        await asyncio.sleep(0.05)
    await scanner.stop()

    if not found_dev:
        return None, None, None

    t_scan = time.time()
    scan_time = t_scan - t_start

    client = BleakClient(found_dev, timeout=10.0)
    try:
        await client.connect()
        t_conn = time.time()
        connect_time = t_conn - t_scan
        total = t_conn - t_start
        await client.disconnect()
        return scan_time, connect_time, total
    except Exception as e:
        return scan_time, None, None


async def run_test(cycles=5):
    print("=" * 60)
    print("모드 전환 재연결 타이밍 테스트")
    print("=" * 60)

    s = get_status()
    if not s:
        print("ERROR: VIA 통신 불가")
        return

    ZMK_ADV = {0: "NONE", 1: "DIR", 2: "CONN", 3: "RECONN", 4: "PAIR"}
    print(f"현재: transport={s['transport']}, tb_bonded={s['tb_bonded']}, "
          f"zmk_adv={ZMK_ADV.get(s['zmk_adv'], '?')}")

    if not s["tb_bonded"]:
        print("ERROR: TextBridge 본딩 없음. 먼저 페어링 필요.")
        return

    tb_results = []
    kb_results = []

    for cycle in range(1, cycles + 1):
        print(f"\n{'─' * 60}")
        print(f"[Cycle {cycle}/{cycles}]")

        # ── USB 모드: TextBridge 재연결 ──
        # 먼저 BLE 모드로 갔다가 USB로 전환 (disconnect 유발)
        switch_ble()
        await asyncio.sleep(2)  # BLE 모드에서 TB disconnect 대기
        print(f"\n  [USB → TextBridge]")
        switch_usb()
        await asyncio.sleep(0.5)

        # VIA 폴링: tb_conn=1 또는 tb_adv=1 대기
        t0 = time.time()
        adv_time = None
        conn_time_via = None
        deadline = t0 + 10.0
        while time.time() < deadline:
            s = get_status()
            if s:
                if s["tb_conn"] and conn_time_via is None:
                    conn_time_via = time.time() - t0
                    break
                if s["tb_adv"] and adv_time is None:
                    adv_time = time.time() - t0
            await asyncio.sleep(0.05)

        if conn_time_via is not None:
            print(f"    자동 연결: {conn_time_via:.2f}s (VIA 폴링)")
            tb_results.append(conn_time_via)
        elif adv_time is not None:
            print(f"    광고 시작: {adv_time:.2f}s, BLE 스캔+연결 시도...")
            scan_t, conn_t, total_t = await ble_scan_and_connect(
                TB_DEVICE_NAME, TB_SVC_UUID, scan_timeout=8.0
            )
            if total_t is not None:
                total = adv_time + total_t
                print(f"    스캔: {scan_t:.2f}s, 연결: {conn_t:.2f}s, 전체: {total:.2f}s")
                tb_results.append(total)
            elif scan_t is not None:
                print(f"    발견({scan_t:.2f}s) 연결 실패")
                tb_results.append(None)
            else:
                print(f"    스캔 실패")
                tb_results.append(None)
        else:
            print(f"    타임아웃 (10s)")
            tb_results.append(None)

        await asyncio.sleep(1)

        # ── BLE 모드: Keyboard 재연결 ──
        # USB 모드에서 KB BLE disconnect 상태 후 BLE 전환
        switch_usb()
        await asyncio.sleep(2)  # USB 모드에서 KB disconnect 대기
        print(f"\n  [BLE → Keyboard]")
        switch_ble()
        await asyncio.sleep(0.5)

        # VIA 폴링: zmk_adv 또는 zmk_conn 대기
        t0 = time.time()
        adv_time = None
        conn_time_via = None
        deadline = t0 + 10.0
        while time.time() < deadline:
            s = get_status()
            if s:
                if s["zmk_conn"] and conn_time_via is None:
                    conn_time_via = time.time() - t0
                    break
                if s["zmk_adv"] and adv_time is None:
                    adv_time = time.time() - t0
            await asyncio.sleep(0.05)

        if conn_time_via is not None:
            print(f"    자동 연결: {conn_time_via:.2f}s (VIA 폴링)")
            kb_results.append(conn_time_via)
        elif adv_time is not None:
            zmk_adv_name = ZMK_ADV.get(s["zmk_adv"] if s else 0, "?")
            print(f"    광고 시작: {adv_time:.2f}s ({zmk_adv_name}), BLE 스캔+연결 시도...")
            scan_t, conn_t, total_t = await ble_scan_and_connect(
                KB_DEVICE_NAME, svc_uuid=None, scan_timeout=8.0
            )
            if total_t is not None:
                total = adv_time + total_t
                print(f"    스캔: {scan_t:.2f}s, 연결: {conn_t:.2f}s, 전체: {total:.2f}s")
                kb_results.append(total)
            elif scan_t is not None:
                print(f"    발견({scan_t:.2f}s) 연결 실패")
                kb_results.append(None)
            else:
                print(f"    스캔 실패 (whitelist 필터)")
                kb_results.append(None)
        else:
            print(f"    타임아웃 (10s)")
            kb_results.append(None)

        await asyncio.sleep(1)

    # USB로 복귀
    switch_usb()

    # ── 결과 요약 ──
    print(f"\n{'=' * 60}")
    print("결과 요약")
    print(f"{'=' * 60}")

    for label, results in [("TextBridge (USB)", tb_results), ("Keyboard (BLE)", kb_results)]:
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
