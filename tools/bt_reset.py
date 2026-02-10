#!/usr/bin/env python3
"""macOS Bluetooth 캐시 초기화 (blueutil 사용)

GATT 캐시 문제로 BLE 알림이 실패할 때 사용.
펌웨어 리플래시 후 권장.

사용법:
    python3 bt_reset.py
"""

import subprocess
import sys
import time


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FAIL: {' '.join(cmd)}")
        print(result.stderr.strip())
        sys.exit(1)
    return result.stdout.strip()


def bt_toggle():
    print("Bluetooth OFF...", end=" ", flush=True)
    run(["blueutil", "--power", "0"])
    time.sleep(3)
    print("ON...", end=" ", flush=True)
    run(["blueutil", "--power", "1"])
    time.sleep(5)
    print("ok")


if __name__ == "__main__":
    bt_toggle()
