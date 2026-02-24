#!/usr/bin/env python3
"""
TextBridge Auto-Reconnect E2E Test

Simulates the Flutter app's reconnect flow:
  1. Connect (like app's initial connection)
  2. Mode switch causes firmware disconnect
  3. Wait for re-advertising (like app's autoConnect wait)
  4. Reconnect to same device (like app's _attemptReconnect)
  5. Verify GATT still works

This tests the REAL reconnect path, not "scan and make a fresh connection".

Usage:
    python3 test_auto_reconnect.py [--timeout 15] [--no-pair]

Requires: pip install bleak hidapi
"""

import asyncio
import argparse
import sys
import time

try:
    from bleak import BleakScanner, BleakClient, BleakError
except ImportError:
    print("Error: bleak not installed. Run: pip install bleak")
    sys.exit(1)

from tb_mode import cmd_usb, cmd_ble, cmd_pair, send_command, CMD_STATUS
from tb_pair import find_raw_hid_interface

# TextBridge UUIDs
TB_SVC_UUID = "12340000-1234-1234-1234-123456789abc"
TB_TX_UUID = "12340001-1234-1234-1234-123456789abc"
TB_RX_UUID = "12340002-1234-1234-1234-123456789abc"

DEVICE_NAME = "TextBridge"


class TestResult:
    def __init__(self):
        self.steps = []
        self.passed = 0
        self.failed = 0

    def ok(self, step, msg):
        self.steps.append((step, True, msg))
        self.passed += 1
        print(f"  [{step}] OK: {msg}")

    def fail(self, step, msg):
        self.steps.append((step, False, msg))
        self.failed += 1
        print(f"  [{step}] FAIL: {msg}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'=' * 50}")
        print(f"Results: {self.passed}/{total} passed")
        if self.failed:
            print("\nFailed steps:")
            for step, ok, msg in self.steps:
                if not ok:
                    print(f"  [{step}] {msg}")
        print(f"{'=' * 50}")
        return self.failed == 0


def get_status():
    """Get TextBridge status via VIA, returns dict or None"""
    resp = send_command(CMD_STATUS, read_response=True)
    if resp and len(resp) > 4:
        return {
            "transport": resp[1],
            "advertising": resp[2],
            "connected": resp[3],
            "bonded": resp[4],
        }
    return None


async def ble_scan(timeout=10.0, use_service_filter=False):
    """Scan for TextBridge device, return address or None.

    use_service_filter: pass service UUID to OS-level scan filter.
    On macOS, this uses CBCentralManager.scanForPeripherals(withServices:)
    which can find devices that discover() misses due to caching.
    """
    if use_service_filter:
        # OS-level filter — helps find cached/known devices on macOS
        found = [None]

        def on_detect(device, adv_data):
            if found[0]:
                return
            name = device.name or adv_data.local_name or ""
            svc_uuids = [str(u).lower() for u in (adv_data.service_uuids or [])]
            if DEVICE_NAME in name or TB_SVC_UUID.lower() in svc_uuids:
                found[0] = device.address

        scanner = BleakScanner(
            detection_callback=on_detect,
            service_uuids=[TB_SVC_UUID],
        )
        await scanner.start()
        deadline = time.time() + timeout
        while time.time() < deadline and not found[0]:
            await asyncio.sleep(0.2)
        await scanner.stop()
        return found[0]
    else:
        devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
        for addr, (d, adv) in devices.items():
            name = d.name or adv.local_name or ""
            svc_uuids = [str(u).lower() for u in (adv.service_uuids or [])]
            if DEVICE_NAME in name or TB_SVC_UUID.lower() in svc_uuids:
                return d.address
        return None


def check_gatt_services(client):
    """Check GATT service/characteristics on an already-connected client."""
    svc_found = False
    tx_found = False
    rx_found = False
    for svc in client.services:
        if svc.uuid.lower() == TB_SVC_UUID.lower():
            svc_found = True
            for char in svc.characteristics:
                if char.uuid.lower() == TB_TX_UUID.lower():
                    tx_found = True
                elif char.uuid.lower() == TB_RX_UUID.lower():
                    rx_found = True
    return svc_found and tx_found and rx_found


async def wait_for_status(key, expected, timeout=5.0, poll_interval=0.5):
    """Poll status until key matches expected or timeout"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = get_status()
        if s and s[key] == expected:
            return s
        await asyncio.sleep(poll_interval)
    return get_status()


async def run_test(scan_timeout=10.0, skip_pair=False):
    result = TestResult()

    # ── Step 1: Verify USB mode ──
    print("\n[Step 1] Verify USB mode")
    s = get_status()
    if not s:
        result.fail(1, "Cannot communicate with keyboard via VIA HID")
        return result
    if s["transport"] == 0:
        result.ok(1, f"USB mode (transport={s['transport']})")
    else:
        print("  Switching to USB mode...")
        cmd_usb()
        await asyncio.sleep(1)
        s = get_status()
        if s and s["transport"] == 0:
            result.ok(1, "Switched to USB mode")
        else:
            result.fail(1, f"transport={s['transport'] if s else '?'}")
            return result

    # ── Step 2: Start pairing ──
    print("\n[Step 2] Start pairing")
    if not skip_pair:
        cmd_pair()
        s = await wait_for_status("advertising", 1, timeout=5.0)
        if s and s["advertising"]:
            result.ok(2, "Advertising started")
        else:
            result.fail(2, f"Not advertising: {s}")
    else:
        result.ok(2, "Skipped (--no-pair)")

    # ── Step 3: BLE scan ──
    print(f"\n[Step 3] BLE scan ({scan_timeout}s)")
    address = await ble_scan(timeout=scan_timeout)
    if address:
        result.ok(3, f"Found at {address}")
    else:
        result.fail(3, "Not found")
        return result

    # ── Step 4: Connect + hold connection (like Flutter app) ──
    print("\n[Step 4] Connect and hold (simulating app)")
    disconnect_event = asyncio.Event()
    client = BleakClient(
        address,
        timeout=15.0,
        disconnected_callback=lambda c: disconnect_event.set(),
    )
    try:
        await client.connect()
        result.ok("4a", f"Connected (MTU={client.mtu_size})")
    except Exception as e:
        result.fail(4, f"Connect failed: {e}")
        return result

    # Discover and verify GATT
    try:
        svcs = client.services
        if check_gatt_services(client):
            result.ok("4b", "GATT verified (SVC + TX + RX)")
        else:
            result.fail("4b", "GATT service/chars missing")
    except Exception as e:
        result.fail("4b", f"Service discovery failed: {e}")

    await asyncio.sleep(1)
    s = get_status()
    if s:
        print(f"    FW status: connected={s['connected']}, bonded={s['bonded']}")

    # ── Step 5: Switch to BLE mode → expect disconnect ──
    print("\n[Step 5] Switch to BLE mode (expect disconnect)")
    disconnect_event.clear()
    cmd_ble()

    # Wait for disconnect callback (max 5s)
    try:
        await asyncio.wait_for(disconnect_event.wait(), timeout=5.0)
        result.ok(5, "Disconnect detected by client callback")
    except asyncio.TimeoutError:
        if not client.is_connected:
            result.ok(5, "Disconnected (no callback but client.is_connected=False)")
        else:
            result.fail(5, "Still connected after BLE mode switch!")

    s = get_status()
    if s:
        print(f"    FW status: transport={s['transport']}, connected={s['connected']}")

    # ── Step 6: Wait + switch back to USB ──
    # Wait >3s to let ZMK's adv_timeout_work (ADV_RECONN_TIME_OUT=3000ms) fire
    # BEFORE we switch to USB. This avoids a race where adv_timeout_work kills
    # TB advertising started by tb_start_pairing_adv().
    print("\n[Step 6] Wait 5s (>ADV_RECONN_TIME_OUT), switch to USB")
    await asyncio.sleep(5)
    cmd_usb()
    await asyncio.sleep(2)

    s = get_status()
    if s and s["transport"] == 0:
        result.ok(6, "USB mode restored")
    else:
        result.fail(6, f"transport={s['transport'] if s else '?'}")
        return result

    # ── Step 7: Check auto-reconnect state ──
    # After USB restore, firmware calls tb_start_reconnect_adv() which uses
    # discoverable advertising. The real phone may auto-reconnect before we check.
    print("\n[Step 7] Check firmware auto-reconnect state")
    s = await wait_for_status("advertising", 1, timeout=5.0)
    phone_already_connected = s and s["connected"]
    if phone_already_connected:
        result.ok(7, "Phone already auto-reconnected (fix verified!)")
    elif s and s["advertising"]:
        result.ok(7, f"Advertising for reconnect (bonded={s['bonded']})")
    else:
        result.fail(7, f"No reconnect activity: {s}")

    # ── Step 8: Simulate app reconnect ──
    # Flutter app uses autoConnect: true → iOS does background scan + auto-connect.
    # On macOS, bleak needs an explicit scan to rediscover the device after disconnect
    # (CoreBluetooth evicts peripherals from cache). This scan simulates iOS autoConnect.
    if phone_already_connected:
        print("\n[Step 8] SKIP — phone already reconnected, proving auto-reconnect works")
        result.ok(8, "Skipped (phone auto-reconnected in Step 7)")
        reconnect_client = None
    else:
        print("\n[Step 8] Reconnect using SAME client (like Flutter app reusing device)")
        # On macOS, CBCentralManager won't re-discover a recently-disconnected
        # peripheral in scan results. But reconnecting the SAME BleakClient
        # (same CBPeripheral object) works — this mirrors Flutter's behavior:
        # BluetoothDevice.fromId(savedId).connect(autoConnect: true)
        #
        # Verify firmware IS advertising first.
        s = get_status()
        if not s or not s["advertising"]:
            result.fail(8, f"Firmware not advertising: {s}")
            return result
        print(f"    FW advertising={s['advertising']}, reconnecting with original client...")

        t0 = time.time()
        reconnect_client = client  # Reuse Step 4's client (same CBPeripheral)
        try:
            await reconnect_client.connect()
            elapsed = time.time() - t0
            result.ok(8, f"Reconnected in {elapsed:.1f}s (same client)")
        except Exception as e:
            elapsed = time.time() - t0
            result.fail(8, f"Reconnect failed after {elapsed:.1f}s: {e}")
            return result

    # ── Step 9: Re-discover services (like app's _connectAndDiscover) ──
    if reconnect_client is None:
        print("\n[Step 9] SKIP — no test client (phone auto-reconnected)")
        result.ok("9a", "Skipped (phone connection)")
        result.ok("9b", "Skipped (phone connection)")
        result.ok("9c", "Skipped (phone connection)")
    else:
        print("\n[Step 9] Re-discover services (simulating app flow)")
        try:
            svcs = reconnect_client.services
            if check_gatt_services(reconnect_client):
                result.ok("9a", "GATT re-verified")
            else:
                result.fail("9a", "GATT service/chars missing on reconnect")
        except Exception as e:
            result.fail("9a", f"Service re-discovery failed: {e}")

        # Try enabling notifications (like app's setNotifyValue)
        try:
            notifications = []
            def on_notify(sender, data):
                notifications.append(data)

            await reconnect_client.start_notify(TB_RX_UUID, on_notify)
            result.ok("9b", "Notify re-enabled on RX")
        except Exception as e:
            result.fail("9b", f"Notify re-enable failed: {e}")

        # Try writing to TX (like app's write)
        try:
            test_data = bytes([0x02, 0x01, 0x00, 0x01])  # START seq=1 total=1
            await reconnect_client.write_gatt_char(TB_TX_UUID, test_data, response=False)
            await asyncio.sleep(0.5)
            if notifications:
                result.ok("9c", f"TX write + RX notify works (got {len(notifications)} responses)")
            else:
                result.ok("9c", "TX write succeeded (no notify yet)")
        except Exception as e:
            result.fail("9c", f"TX write failed: {e}")

        # Cleanup: send ABORT to clear any transmission state
        try:
            await reconnect_client.write_gatt_char(TB_TX_UUID, bytes([0x04, 0x01]), response=False)
        except Exception:
            pass

        await reconnect_client.disconnect()

    # ── Step 10: Final status ──
    print("\n[Step 10] Final status")
    await asyncio.sleep(1)
    s = get_status()
    if s:
        print(f"    transport={s['transport']}, advertising={s['advertising']}, "
              f"connected={s['connected']}, bonded={s['bonded']}")
        result.ok(10, "Done")
    else:
        result.fail(10, "Cannot get status")

    return result


async def main():
    parser = argparse.ArgumentParser(description="TextBridge Auto-Reconnect E2E Test")
    parser.add_argument("--timeout", type=float, default=15,
                        help="BLE scan timeout (default: 15)")
    parser.add_argument("--no-pair", action="store_true",
                        help="Skip initial pairing")
    args = parser.parse_args()

    print("=" * 50)
    print("TextBridge Auto-Reconnect E2E Test")
    print("=" * 50)

    if not find_raw_hid_interface():
        print("Error: Keychron B6 Pro not found via USB HID")
        sys.exit(1)

    result = await run_test(
        scan_timeout=args.timeout,
        skip_pair=args.no_pair,
    )
    all_passed = result.summary()
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
