#!/usr/bin/env python3
"""
Shared HID utility for TextBridge tools.

Provides common constants and functions for finding the Keychron B6 Pro
Raw HID interface.

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


def find_raw_hid_interface():
    """Find the Raw HID interface (usage page 0xFF60)"""
    for device in hid.enumerate(VENDOR_ID, PRODUCT_ID):
        if device['usage_page'] == RAW_USAGE_PAGE:
            return device['path']
    return None
