#!/usr/bin/env python3
"""
TextBridge Mode Switch Tool

VIA Raw HID commands for transport mode switching and status query.

Commands:
    python3 tb_mode.py usb      # Switch to USB mode
    python3 tb_mode.py ble      # Switch to BLE mode
    python3 tb_mode.py status   # Query current state
    python3 tb_mode.py pair     # Start TextBridge pairing (alias for tb_pair.py)

Requires: pip install hidapi
"""

import sys
import time

try:
    import hid
except ImportError:
    print("Error: hidapi not installed")
    print("Run: pip install hidapi")
    sys.exit(1)

# Keychron B6 Pro
VENDOR_ID = 0x3434
PRODUCT_ID = 0x0761
RAW_USAGE_PAGE = 0xFF60
RAW_EPSIZE = 32

# VIA commands
CMD_TB_PAIR = 0xFE
CMD_MODE_USB = 0xFC
CMD_MODE_BLE = 0xFB
CMD_STATUS = 0xFA

TRANSPORT_NAMES = {0: "USB", 1: "BLE", 2: "2.4G", 3: "NONE"}


def find_raw_hid_interface():
    """Find the Raw HID interface (usage page 0xFF60)"""
    for device in hid.enumerate(VENDOR_ID, PRODUCT_ID):
        if device['usage_page'] == RAW_USAGE_PAGE:
            return device['path']
    return None


def send_command(cmd, read_response=False):
    """Send a VIA command and optionally read response"""
    path = find_raw_hid_interface()

    if not path:
        print(f"Error: Keychron B6 Pro not found (VID:{VENDOR_ID:04x} PID:{PRODUCT_ID:04x})")
        return None

    device = hid.device()
    device.open_path(path)

    # Build command: [report_id, command, ...padding...]
    data = [0x00] * (RAW_EPSIZE + 1)  # +1 for report ID
    data[0] = 0x00  # Report ID
    data[1] = cmd

    device.write(data)

    response = None
    if read_response:
        device.set_nonblocking(0)
        try:
            response = device.read(RAW_EPSIZE, timeout_ms=1000)
        except OSError:
            pass  # read can fail after mode switch

    device.close()
    return response


def cmd_usb():
    """Switch to USB mode"""
    print("Switching to USB mode...")
    resp = send_command(CMD_MODE_USB, read_response=True)
    if resp:
        transport = resp[1] if len(resp) > 1 else -1
        name = TRANSPORT_NAMES.get(transport, f"unknown({transport})")
        print(f"  transport = {name} ({transport})")
        return transport == 0
    # Response may fail after mode switch — verify with status
    print("  (no direct response, verifying via status...)")
    time.sleep(0.5)
    s = cmd_status()
    return s is not None and s["transport"] == 0


def cmd_ble():
    """Switch to BLE mode"""
    print("Switching to BLE mode...")
    resp = send_command(CMD_MODE_BLE, read_response=True)
    if resp:
        transport = resp[1] if len(resp) > 1 else -1
        name = TRANSPORT_NAMES.get(transport, f"unknown({transport})")
        print(f"  transport = {name} ({transport})")
        return transport == 1
    # Response may fail after mode switch — verify with status
    print("  (no direct response, verifying via status...)")
    time.sleep(0.5)
    s = cmd_status()
    return s is not None and s["transport"] == 1


def cmd_status():
    """Query TextBridge state"""
    print("Querying TextBridge status...")
    resp = send_command(CMD_STATUS, read_response=True)
    if resp:
        transport = resp[1] if len(resp) > 1 else -1
        advertising = resp[2] if len(resp) > 2 else -1
        connected = resp[3] if len(resp) > 3 else -1
        bonded = resp[4] if len(resp) > 4 else -1

        t_name = TRANSPORT_NAMES.get(transport, f"unknown({transport})")
        print(f"  transport   = {t_name} ({transport})")
        print(f"  advertising = {bool(advertising)} ({advertising})")
        print(f"  connected   = {bool(connected)} ({connected})")
        print(f"  bonded      = {bool(bonded)} ({bonded})")
        return {
            "transport": transport,
            "advertising": advertising,
            "connected": connected,
            "bonded": bonded,
        }
    print("  (no response)")
    return None


def cmd_pair():
    """Start TextBridge pairing"""
    print("Starting TextBridge pairing...")
    send_command(CMD_TB_PAIR, read_response=False)
    print("  TextBridge should be advertising as 'TextBridge'")
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 tb_mode.py <command>")
        print()
        print("Commands:")
        print("  usb      Switch to USB mode")
        print("  ble      Switch to BLE mode")
        print("  status   Query current state")
        print("  pair     Start TextBridge BLE pairing")
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "usb":
        success = cmd_usb()
    elif cmd == "ble":
        success = cmd_ble()
    elif cmd == "status":
        result = cmd_status()
        success = result is not None
    elif cmd == "pair":
        success = cmd_pair()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
