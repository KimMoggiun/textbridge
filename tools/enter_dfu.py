#!/usr/bin/env python3
"""
Keychron B6 Pro DFU Mode Entry Tool

Sends HID command to enter bootloader/DFU mode.
Requires: pip install hidapi
"""

import sys
try:
    import hid
except ImportError:
    print("Error: hidapi not installed")
    print("Run: pip install hidapi")
    sys.exit(1)

from hid_util import find_raw_hid_interface, VENDOR_ID, PRODUCT_ID, RAW_USAGE_PAGE, RAW_EPSIZE

# VIA Command
ID_BOOTLOADER_JUMP = 0x0B

def enter_dfu():
    """Send bootloader jump command"""
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
        data[1] = ID_BOOTLOADER_JUMP  # Command

        print("Sending bootloader jump command...")
        device.write(data)
        device.close()

        print("Success! Keyboard should be in DFU mode now.")
        print("Look for NRF52BOOT volume.")
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    enter_dfu()
