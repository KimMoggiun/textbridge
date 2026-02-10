#!/usr/bin/env python3
"""macOS 키보드 이벤트 로거 — HID 디버깅용
별도 터미널에서 실행: python3 hid_logger.py
Accessibility 권한 필요 (System Settings > Privacy > Accessibility)
"""
import time
from Quartz import (
    CGEventTapCreate, CGEventTapEnable,
    CFMachPortCreateRunLoopSource, CFRunLoopAddSource,
    CFRunLoopGetCurrent, CFRunLoopRun,
    kCGSessionEventTap, kCGHeadInsertEventTap, kCGEventTapOptionListenOnly,
    kCGEventKeyDown, kCGEventKeyUp, kCGEventFlagsChanged,
    kCFRunLoopCommonModes,
    CGEventGetIntegerValueField, CGEventGetFlags,
    CGEventKeyboardGetUnicodeString,
    kCGKeyboardEventKeycode,
    kCGEventFlagMaskShift, kCGEventFlagMaskControl,
    kCGEventFlagMaskAlternate, kCGEventFlagMaskCommand,
)

t0 = time.time()

def callback(proxy, etype, event, refcon):
    ts = time.time() - t0
    keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
    flags = CGEventGetFlags(event)

    shift = "S" if flags & kCGEventFlagMaskShift else "."
    ctrl  = "C" if flags & kCGEventFlagMaskControl else "."
    alt   = "A" if flags & kCGEventFlagMaskAlternate else "."
    cmd   = "M" if flags & kCGEventFlagMaskCommand else "."

    if etype == kCGEventKeyDown:
        label = "DOWN"
    elif etype == kCGEventKeyUp:
        label = "UP  "
    elif etype == kCGEventFlagsChanged:
        label = "FLAG"
    else:
        label = f"?{etype}"

    # Unicode 문자 추출
    length, chars = CGEventKeyboardGetUnicodeString(event, 10, None, None)
    char_str = chars if chars else ""

    print(f"{ts:8.3f}  {label}  vk={keycode:3d}  mod={shift}{ctrl}{alt}{cmd}  '{char_str}'")
    return event

mask = (1 << kCGEventKeyDown) | (1 << kCGEventKeyUp) | (1 << kCGEventFlagsChanged)
tap = CGEventTapCreate(
    kCGSessionEventTap, kCGHeadInsertEventTap,
    kCGEventTapOptionListenOnly, mask, callback, None
)

if tap is None:
    print("이벤트 탭 생성 실패.")
    print("System Settings > Privacy & Security > Accessibility 에서")
    print("Terminal.app (또는 iTerm) 권한을 추가하세요.")
    exit(1)

source = CFMachPortCreateRunLoopSource(None, tap, 0)
CFRunLoopAddSource(CFRunLoopGetCurrent(), source, kCFRunLoopCommonModes)
CGEventTapEnable(tap, True)

print("키보드 이벤트 로깅 시작... (Ctrl+C 종료)")
print(f"{'시간':>8}  타입  {'vk':>5}  mod       char")
print("-" * 50)

try:
    CFRunLoopRun()
except KeyboardInterrupt:
    print("\n종료.")
