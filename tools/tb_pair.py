#!/usr/bin/env python3
"""
TextBridge Pairing Mode Entry Tool

Sends VIA Raw HID command 0xFE to start TextBridge BLE advertising.
Equivalent to pressing Fn+1 on the keyboard.

Requires: pip install hidapi
"""

import sys
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

# TextBridge pairing command
CMD_TB_PAIR = 0xFE


def find_raw_hid_interface():
    """Find the Raw HID interface (usage page 0xFF60)"""
    for device in hid.enumerate(VENDOR_ID, PRODUCT_ID):
        if device['usage_page'] == RAW_USAGE_PAGE:
            return device['path']
    return None


def start_pairing():
    """Send TextBridge pairing command"""
    path = find_raw_hid_interface()

    if not path:
        print(f"Error: Keychron B6 Pro not found (VID:{VENDOR_ID:04x} PID:{PRODUCT_ID:04x})")
        print("\nAvailable devices:")
        for d in hid.enumerate():
            if d['vendor_id'] == VENDOR_ID:
                print(f"  - {d['product_string']} (usage_page: 0x{d['usage_page']:04x})")
        return False

    try:
        device = hid.device()
        device.open_path(path)
        print(f"Connected to: {device.get_product_string()}")

        # Build command: [report_id, command, ...padding...]
        data = [0x00] * (RAW_EPSIZE + 1)  # +1 for report ID
        data[0] = 0x00  # Report ID
        data[1] = CMD_TB_PAIR

        print("Sending TextBridge pairing command (0xFE)...")
        device.write(data)
        device.close()

        print("Success! TextBridge should be advertising as 'B6 TextBridge'.")
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    start_pairing()
