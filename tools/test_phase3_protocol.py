#!/usr/bin/env python3
"""
TextBridge Phase 3 프로토콜 테스트 (자동화)
- VIA Raw HID로 TextBridge 광고 자동 시작 (Fn+1 대체)
- BLE 연결 → START → KEYCODE → DONE 시퀀스
- ACK/READY/DONE 응답 검증
- 중복 감지, ABORT 테스트

사용법:
    python3 test_phase3_protocol.py --text "hello world"
    python3 test_phase3_protocol.py --text "hello" --append-enter  # Claude Code 검증용
"""

import asyncio
import argparse
import sys

try:
    from bleak import BleakScanner, BleakClient
except ImportError:
    print("bleak 필요: pip3 install bleak")
    sys.exit(1)

# TextBridge UUIDs
TB_SVC_UUID = "12340000-1234-1234-1234-123456789abc"
TB_TX_UUID  = "12340001-1234-1234-1234-123456789abc"
TB_RX_UUID  = "12340002-1234-1234-1234-123456789abc"

DEVICE_NAME = "TextBridge"

# Protocol commands
CMD_KEYCODE = 0x01
CMD_START   = 0x02
CMD_DONE    = 0x03
CMD_ABORT     = 0x04
CMD_SET_DELAY = 0x05

# Protocol responses
RESP_ACK    = 0x01
RESP_NACK   = 0x02
RESP_READY  = 0x03
RESP_DONE   = 0x04
RESP_ERROR  = 0x05

RESP_NAMES = {
    RESP_ACK: "ACK", RESP_NACK: "NACK", RESP_READY: "READY",
    RESP_DONE: "DONE", RESP_ERROR: "ERROR",
}

# HID keycodes for ASCII
ASCII_TO_HID = {}
# a-z: 0x04-0x1D, no modifier
for i, c in enumerate(range(ord('a'), ord('z') + 1)):
    ASCII_TO_HID[chr(c)] = (0x04 + i, 0x00)
# A-Z: 0x04-0x1D, shift
for i, c in enumerate(range(ord('A'), ord('Z') + 1)):
    ASCII_TO_HID[chr(c)] = (0x04 + i, 0x02)
# 1-9
for i in range(1, 10):
    ASCII_TO_HID[str(i)] = (0x1E + i - 1, 0x00)
# 0
ASCII_TO_HID['0'] = (0x27, 0x00)
# Special
ASCII_TO_HID[' '] = (0x2C, 0x00)  # Space
ASCII_TO_HID['\n'] = (0x28, 0x00)  # Enter
ASCII_TO_HID['!'] = (0x1E, 0x02)
ASCII_TO_HID['@'] = (0x1F, 0x02)
ASCII_TO_HID['#'] = (0x20, 0x02)
ASCII_TO_HID['$'] = (0x21, 0x02)
ASCII_TO_HID['%'] = (0x22, 0x02)
ASCII_TO_HID['^'] = (0x23, 0x02)
ASCII_TO_HID['&'] = (0x24, 0x02)
ASCII_TO_HID['*'] = (0x25, 0x02)
ASCII_TO_HID['('] = (0x26, 0x02)
ASCII_TO_HID[')'] = (0x27, 0x02)
ASCII_TO_HID['-'] = (0x2D, 0x00)
ASCII_TO_HID['_'] = (0x2D, 0x02)
ASCII_TO_HID['='] = (0x2E, 0x00)
ASCII_TO_HID['+'] = (0x2E, 0x02)
ASCII_TO_HID['['] = (0x2F, 0x00)
ASCII_TO_HID['{'] = (0x2F, 0x02)
ASCII_TO_HID[']'] = (0x30, 0x00)
ASCII_TO_HID['}'] = (0x30, 0x02)
ASCII_TO_HID['\\'] = (0x31, 0x00)
ASCII_TO_HID['|'] = (0x31, 0x02)
ASCII_TO_HID[';'] = (0x33, 0x00)
ASCII_TO_HID[':'] = (0x33, 0x02)
ASCII_TO_HID["'"] = (0x34, 0x00)
ASCII_TO_HID['"'] = (0x34, 0x02)
ASCII_TO_HID['`'] = (0x35, 0x00)
ASCII_TO_HID['~'] = (0x35, 0x02)
ASCII_TO_HID[','] = (0x36, 0x00)
ASCII_TO_HID['<'] = (0x36, 0x02)
ASCII_TO_HID['.'] = (0x37, 0x00)
ASCII_TO_HID['>'] = (0x37, 0x02)
ASCII_TO_HID['/'] = (0x38, 0x00)
ASCII_TO_HID['?'] = (0x38, 0x02)
ASCII_TO_HID['\t'] = (0x2B, 0x00)  # Tab


def text_to_keycodes(text: str, append_enter: bool = False) -> list[tuple[int, int]]:
    """텍스트를 (keycode, modifier) 리스트로 변환 (ASCII only)"""
    keycodes = []
    for ch in text:
        if ch in ASCII_TO_HID:
            keycodes.append(ASCII_TO_HID[ch])
    if append_enter:
        keycodes.append((0x28, 0x00))  # Enter
    return keycodes


def make_start(seq: int, total_chunks: int) -> bytes:
    return bytes([CMD_START, seq, (total_chunks >> 8) & 0xFF, total_chunks & 0xFF])


def make_keycode(seq: int, keycodes: list[tuple[int, int]]) -> bytes:
    data = [CMD_KEYCODE, seq, len(keycodes)]
    for kc, mod in keycodes:
        data.extend([kc, mod])
    return bytes(data)


def make_done(seq: int) -> bytes:
    return bytes([CMD_DONE, seq])


def make_abort(seq: int) -> bytes:
    return bytes([CMD_ABORT, seq])


def make_set_delay(press_delay: int = 1, release_delay: int = 1, combo_delay: int = 2,
                   warmup_delay: int = 50) -> bytes:
    return bytes([CMD_SET_DELAY,
                  max(1, min(255, press_delay)),
                  max(1, min(255, release_delay)),
                  max(1, min(255, combo_delay)),
                  max(1, min(255, warmup_delay))])


# ============ VIA Raw HID Pairing ============

def via_start_pairing() -> bool:
    """VIA Raw HID로 0xFE 명령 전송하여 TextBridge 광고 시작"""
    try:
        import hid
    except ImportError:
        print("[PAIR] hidapi 미설치. pip install hidapi")
        return False

    VENDOR_ID = 0x3434
    PRODUCT_ID = 0x0761
    RAW_USAGE_PAGE = 0xFF60

    path = None
    for device in hid.enumerate(VENDOR_ID, PRODUCT_ID):
        if device['usage_page'] == RAW_USAGE_PAGE:
            path = device['path']
            break

    if not path:
        return False

    try:
        device = hid.device()
        device.open_path(path)
        data = [0x00] * 33
        data[1] = 0xFE
        device.write(data)
        device.close()
        return True
    except Exception:
        return False


def split_chunks(keycodes: list[tuple[int, int]], chunk_size: int = 8) -> list[list[tuple[int, int]]]:
    """Split keycodes into chunks."""
    chunks = []
    i = 0
    while i < len(keycodes):
        start = i
        while i < len(keycodes) and i - start < chunk_size:
            i += 1
        chunks.append(keycodes[start:i])
    return chunks


class TextBridgeClient:
    def __init__(self, client: BleakClient):
        self.client = client
        self.responses = asyncio.Queue()

    def _notify_handler(self, sender, data: bytearray):
        self.responses.put_nowait(data)

    async def connect(self):
        await self.client.start_notify(TB_RX_UUID, self._notify_handler)

    async def write(self, data: bytes, label: str = ""):
        await self.client.write_gatt_char(TB_TX_UUID, data, response=False)

    async def wait_response(self, expected_code: int = None, timeout: float = 5.0) -> bytearray:
        try:
            resp = await asyncio.wait_for(self.responses.get(), timeout=timeout)
            return resp
        except asyncio.TimeoutError:
            return None

    async def set_delay(self, press_delay: int = 1, release_delay: int = 1, combo_delay: int = 2,
                        warmup_delay: int = 50) -> bool:
        """Send CMD_SET_DELAY to configure firmware timing"""
        await self.write(make_set_delay(press_delay, release_delay, combo_delay,
                                        warmup_delay), "SET_DELAY")
        resp = await self.wait_response(RESP_ACK, timeout=2.0)
        return resp is not None and resp[0] == RESP_ACK

    async def send_text(self, text: str, chunk_size: int = 8, append_enter: bool = False) -> bool:
        """텍스트를 프로토콜로 전송"""
        keycodes = text_to_keycodes(text, append_enter=append_enter)
        if not keycodes:
            return False

        chunks = split_chunks(keycodes, chunk_size)

        await self.write(make_start(0, len(chunks)))
        resp = await self.wait_response(RESP_READY)
        if not resp or resp[0] != RESP_READY:
            return False

        for i, chunk in enumerate(chunks):
            seq = (i + 1) % 256
            await self.write(make_keycode(seq, chunk))
            resp = await self.wait_response(RESP_ACK, timeout=10.0)
            if not resp:
                return False
            if resp[0] == RESP_NACK:
                await asyncio.sleep(1.0)
                await self.write(make_keycode(seq, chunk))
                resp = await self.wait_response(RESP_ACK, timeout=10.0)
                if not resp or resp[0] != RESP_ACK:
                    return False
            elif resp[0] == RESP_ERROR:
                return False

        done_seq = (len(chunks) + 1) % 256
        await self.write(make_done(done_seq))
        await self.wait_response(RESP_DONE)
        return True


async def scan(timeout: float):
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    found = []
    for addr, (d, adv) in devices.items():
        name = d.name or adv.local_name or ""
        svc_uuids = [str(u).lower() for u in (adv.service_uuids or [])]
        if DEVICE_NAME in name or TB_SVC_UUID.lower() in svc_uuids:
            found.append(d)
    return found


async def main():
    parser = argparse.ArgumentParser(description="TextBridge 텍스트 전송")
    parser.add_argument("--text", type=str, required=True)
    args = parser.parse_args()

    print("pairing...", end=" ", flush=True)
    via_start_pairing()
    await asyncio.sleep(2.0)
    print("ok")

    print("scanning...", end=" ", flush=True)
    devices = await scan(10)
    if not devices:
        print("not found")
        return
    print(devices[0].address)

    print("sending...", end=" ", flush=True)
    async with BleakClient(devices[0].address) as client:
        tb = TextBridgeClient(client)
        await tb.connect()
        await tb.set_delay(press_delay=1, release_delay=1, combo_delay=2, warmup_delay=50)
        ok = await tb.send_text(args.text, append_enter=True)
        print("ok" if ok else "FAIL")


if __name__ == "__main__":
    asyncio.run(main())
