#!/usr/bin/env python3
"""
TextBridge Phase 2 BLE GATT 테스트
- "B6 TextBridge" 스캔
- 연결 → GATT 서비스/특성 확인
- RX Notify 활성화
- TX에 테스트 데이터 Write
- 연결 해제

사용법:
    pip install bleak hidapi
    python test_phase2_ble.py [--scan-only] [--timeout 10] [--no-pair]
"""

import asyncio
import argparse
import sys

try:
    from bleak import BleakScanner, BleakClient
except ImportError:
    print("bleak 패키지가 필요합니다: pip install bleak")
    sys.exit(1)

from tb_pair import start_pairing as via_start_pairing

# TextBridge UUIDs
TB_SVC_UUID = "12340000-1234-1234-1234-123456789abc"
TB_TX_UUID  = "12340001-1234-1234-1234-123456789abc"  # Write (phone → keyboard)
TB_RX_UUID  = "12340002-1234-1234-1234-123456789abc"  # Notify (keyboard → phone)

DEVICE_NAME = "B6 TextBridge"


async def scan(timeout: float) -> list:
    """BLE 스캔하여 TextBridge 디바이스 찾기"""
    print(f"[SCAN] {timeout}초간 BLE 스캔 중...")
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)

    found = []
    for addr, (d, adv) in devices.items():
        name = d.name or adv.local_name or ""
        svc_uuids = [str(u).lower() for u in (adv.service_uuids or [])]
        if DEVICE_NAME in name or TB_SVC_UUID.lower() in svc_uuids:
            found.append(d)
            print(f"  [OK] {name} ({d.address}) RSSI={adv.rssi}")
        else:
            if name:
                print(f"  [ ] {name} ({d.address}) RSSI={adv.rssi}")

    if not found:
        print(f"\n[FAIL] '{DEVICE_NAME}' 디바이스를 찾지 못했습니다.")
        print("확인사항:")
        print("  1. 키보드가 USB로 연결되어 있는가?")
        print("  2. Fn+1 키를 눌렀는가? (TextBridge 광고 시작)")
        print("  3. 시리얼 로그에 'TextBridge pairing mode' 메시지가 있는가?")
    else:
        print(f"\n[OK] TextBridge 디바이스 {len(found)}개 발견")

    return found


def notification_handler(sender, data: bytearray):
    """RX Notify 수신 콜백"""
    print(f"  [NOTIFY] {len(data)} bytes: {data.hex()}")


async def test_gatt(address: str):
    """GATT 서비스 연결 및 테스트"""
    print(f"\n[CONN] {address}에 연결 중...")

    async with BleakClient(address) as client:
        print(f"  [OK] 연결됨 (MTU={client.mtu_size})")

        # 1. 서비스 탐색
        print("\n[GATT] 서비스 탐색...")
        svc_found = False
        tx_found = False
        rx_found = False

        for svc in client.services:
            if svc.uuid.lower() == TB_SVC_UUID.lower():
                svc_found = True
                print(f"  [OK] TextBridge 서비스: {svc.uuid}")
                for char in svc.characteristics:
                    props = ",".join(char.properties)
                    print(f"    특성: {char.uuid} [{props}]")
                    if char.uuid.lower() == TB_TX_UUID.lower():
                        tx_found = True
                        print(f"    [OK] TX (Write Without Response)")
                    elif char.uuid.lower() == TB_RX_UUID.lower():
                        rx_found = True
                        print(f"    [OK] RX (Notify)")
                    for desc in char.descriptors:
                        print(f"      디스크립터: {desc.uuid}")

        if not svc_found:
            print(f"  [FAIL] TextBridge 서비스({TB_SVC_UUID})를 찾지 못함")
            print("\n  발견된 서비스 목록:")
            for svc in client.services:
                print(f"    {svc.uuid}: {svc.description}")
            return False

        if not tx_found or not rx_found:
            print(f"  [FAIL] 특성 누락 - TX:{tx_found}, RX:{rx_found}")
            return False

        # 2. RX Notify 활성화
        print("\n[NOTIFY] RX Notify 활성화 중...")
        try:
            await client.start_notify(TB_RX_UUID, notification_handler)
            print("  [OK] Notify 활성화됨")
        except Exception as e:
            print(f"  [WARN] Notify 활성화 실패: {e}")

        # 3. TX Write 테스트
        test_data = [
            bytes([0x01, 0x02, 0x03, 0x04]),       # 간단한 바이트
            b"Hello TextBridge",                     # 문자열
            bytes(range(20)),                        # 20바이트 시퀀스
        ]

        print("\n[WRITE] TX Write 테스트...")
        for i, data in enumerate(test_data):
            try:
                await client.write_gatt_char(TB_TX_UUID, data, response=False)
                print(f"  [OK] Write #{i+1}: {len(data)}바이트 → {data.hex()}")
                await asyncio.sleep(0.5)  # 키보드 로그 확인할 시간
            except Exception as e:
                print(f"  [FAIL] Write #{i+1}: {e}")

        # 4. Notify 수신 대기 (키보드가 응답을 보내면)
        print("\n[WAIT] 2초간 Notify 응답 대기...")
        await asyncio.sleep(2)

        # 5. Notify 중지
        try:
            await client.stop_notify(TB_RX_UUID)
        except Exception:
            pass

        print("\n[DONE] 테스트 완료")
        return True


async def main():
    parser = argparse.ArgumentParser(description="TextBridge Phase 2 BLE 테스트")
    parser.add_argument("--scan-only", action="store_true",
                        help="스캔만 수행 (연결 안 함)")
    parser.add_argument("--timeout", type=float, default=10,
                        help="스캔 타임아웃 (초, 기본: 10)")
    parser.add_argument("--address", type=str, default=None,
                        help="직접 MAC 주소 지정 (스캔 건너뛰기)")
    parser.add_argument("--no-pair", action="store_true",
                        help="VIA 자동 페어링 스킵 (수동 Fn+1)")
    args = parser.parse_args()

    if not args.no_pair and not args.scan_only:
        print("\n[STEP 0] VIA 명령으로 TextBridge 광고 시작")
        if not via_start_pairing():
            print("[WARN] VIA 페어링 실패. 수동으로 Fn+1을 누르세요.")
        else:
            print("[PAIR] 광고 시작 대기 (2초)...")
            await asyncio.sleep(2.0)

    if args.address:
        await test_gatt(args.address)
        return

    devices = await scan(args.timeout)

    if args.scan_only or not devices:
        return

    # 첫 번째 디바이스에 연결
    target = devices[0]
    print(f"\n대상: {target.name} ({target.address})")
    success = await test_gatt(target.address)

    if success:
        print("\n=== Phase 2 테스트 성공 ===")
        print("시리얼 로그에서 확인할 내용:")
        print('  - "TextBridge connected: <주소>"')
        print('  - "RX notify enabled"')
        print('  - "RX: N bytes" + hexdump (Write 데이터)')
        print('  - "TextBridge disconnected: <주소>"')
    else:
        print("\n=== Phase 2 테스트 실패 ===")


if __name__ == "__main__":
    asyncio.run(main())
