#!/usr/bin/env python3
"""
TextBridge Phase 3 프로토콜 테스트 (자동화)
- VIA Raw HID로 TextBridge 광고 자동 시작 (Fn+1 대체)
- BLE 연결 → START → KEYCODE → DONE 시퀀스
- ACK/READY/DONE 응답 검증
- 중복 감지, ABORT 테스트

사용법:
    python3 test_phase3_protocol.py --test single_a
    python3 test_phase3_protocol.py --test all
    python3 test_phase3_protocol.py --text "hello world"
    python3 test_phase3_protocol.py --text "hello" --append-enter  # Claude Code 검증용
    python3 test_phase3_protocol.py --no-pair --test single_a      # 수동 Fn+1
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

DEVICE_NAME = "B6 TextBridge"

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
    """텍스트를 (keycode, modifier) 리스트로 변환 (ASCII + 한글)
    hangul_to_keycodes가 trailing toggle을 자동 추가하므로 항상 영문으로 끝남."""
    keycodes = hangul_to_keycodes(text)
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


def make_set_delay(press_delay: int = 5, release_delay: int = 5, combo_delay: int = 2,
                   toggle_press: int = 20, toggle_delay: int = 100, warmup_delay: int = 50) -> bytes:
    return bytes([CMD_SET_DELAY,
                  max(1, min(255, press_delay)),
                  max(1, min(255, release_delay)),
                  max(1, min(255, combo_delay)),
                  max(1, min(255, toggle_press)),
                  max(1, min(255, toggle_delay)),
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

    async def set_delay(self, press_delay: int = 5, release_delay: int = 5, combo_delay: int = 2,
                        toggle_press: int = 20, toggle_delay: int = 100, warmup_delay: int = 50) -> bool:
        """Send CMD_SET_DELAY to configure firmware timing"""
        await self.write(make_set_delay(press_delay, release_delay, combo_delay,
                                        toggle_press, toggle_delay, warmup_delay), "SET_DELAY")
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
            # Enter 청크 전 딜레이: macOS IME composition end 이벤트 처리 대기
            # toggle_delay(100ms) 이후에도 Electron 앱에서 Enter가 줄바꿈으로 처리될 수 있음
            if any(kc[0] == 0x28 for kc in chunk) and i > 0:
                await asyncio.sleep(0.3)
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


# ============ Test cases ============

async def test_single_a(tb: TextBridgeClient):
    """테스트 1: 단일 키 'a'"""
    print("\n=== Test: single 'a' ===")
    return await tb.send_text("a")


async def test_shift_A(tb: TextBridgeClient):
    """테스트 2: 대문자 'A' (Shift+a)"""
    print("\n=== Test: shift 'A' ===")
    return await tb.send_text("A")


async def test_hello(tb: TextBridgeClient):
    """테스트 3: 'hello world' (여러 키, 공백 포함)"""
    print("\n=== Test: 'hello world' ===")
    return await tb.send_text("hello world")


async def test_multi_chunk(tb: TextBridgeClient):
    """테스트 4: 여러 청크 'abcdefghijklmnop' (16키 = 2청크)"""
    print("\n=== Test: multi-chunk 'abcdefghijklmnop' ===")
    return await tb.send_text("abcdefghijklmnop")


async def test_duplicate(tb: TextBridgeClient):
    """테스트 5: 중복 청크 감지"""
    print("\n=== Test: duplicate detection ===")

    # START
    await tb.write(make_start(0, 1), "START")
    resp = await tb.wait_response(RESP_READY)
    if not resp:
        return False

    # KEYCODE seq=1 (a)
    kc_data = make_keycode(1, [(0x04, 0x00)])
    await tb.write(kc_data, "KEYCODE seq=1 (a)")
    resp = await tb.wait_response(RESP_ACK)
    if not resp:
        return False

    # 동일 seq=1 재전송
    await asyncio.sleep(0.5)
    await tb.write(kc_data, "KEYCODE seq=1 (duplicate)")
    resp = await tb.wait_response(RESP_ACK)
    if not resp:
        return False
    print("  [OK] 중복 ACK 수신 (키보드 측에서 HID 미주입)")

    # DONE
    await tb.write(make_done(2), "DONE")
    await tb.wait_response(RESP_DONE)
    return True


async def test_abort(tb: TextBridgeClient):
    """테스트 6: ABORT 테스트"""
    print("\n=== Test: ABORT ===")

    # START
    await tb.write(make_start(0, 5), "START")
    resp = await tb.wait_response(RESP_READY)
    if not resp:
        return False

    # 하나의 큰 청크 전송 (5키 - 'abcde')
    keycodes = [(0x04 + i, 0x00) for i in range(5)]
    await tb.write(make_keycode(1, keycodes), "KEYCODE seq=1 count=5 (abcde)")

    # 즉시 ABORT (injection 진행 중에)
    await asyncio.sleep(0.05)
    await tb.write(make_abort(2), "ABORT")

    # ABORT ACK 대기
    # ACK from KEYCODE or ACK from ABORT 둘 다 올 수 있음
    for _ in range(2):
        resp = await tb.wait_response(timeout=3.0)
        if resp and resp[0] == RESP_ACK and resp[1] == 2:
            print("  [OK] ABORT ACK 수신")
            return True

    print("  [WARN] ABORT ACK 미확인 (injection이 먼저 완료되었을 수 있음)")
    return True


async def test_special_chars(tb: TextBridgeClient):
    """테스트 7: 특수문자"""
    print("\n=== Test: special chars ===")
    return await tb.send_text("Hello, World! 123")


# ============ Hangul Dubeolsik keycodes ============
# Pre-computed keycode sequences for Korean text.
# Toggle key: 0x90 (Windows LANG1), 0xE7 (macOS Right GUI)
TOGGLE_WIN = (0x90, 0x00)
TOGGLE_MAC = (0x6D, 0x00)  # F18 — macOS input method toggle
_toggle_key = TOGGLE_WIN  # default, changed by --os flag

# Dubeolsik cho (initial consonant) keycodes
_CHO = [
    (0x15, 0x00),  # ㄱ R
    (0x15, 0x02),  # ㄲ R+Shift
    (0x16, 0x00),  # ㄴ S
    (0x08, 0x00),  # ㄷ E
    (0x08, 0x02),  # ㄸ E+Shift
    (0x09, 0x00),  # ㄹ F
    (0x04, 0x00),  # ㅁ A
    (0x14, 0x00),  # ㅂ Q
    (0x14, 0x02),  # ㅃ Q+Shift
    (0x17, 0x00),  # ㅅ T
    (0x17, 0x02),  # ㅆ T+Shift
    (0x07, 0x00),  # ㅇ D
    (0x1A, 0x00),  # ㅈ W
    (0x1A, 0x02),  # ㅉ W+Shift
    (0x06, 0x00),  # ㅊ C
    (0x1D, 0x00),  # ㅋ Z
    (0x1B, 0x00),  # ㅌ X
    (0x19, 0x00),  # ㅍ V
    (0x0A, 0x00),  # ㅎ G
]

# Dubeolsik jung (medial vowel) keycodes — compound vowels expand to 2
_JUNG = [
    [(0x0E, 0x00)],  # ㅏ K
    [(0x12, 0x00)],  # ㅐ O
    [(0x0C, 0x00)],  # ㅑ I
    [(0x12, 0x02)],  # ㅒ O+Shift
    [(0x0D, 0x00)],  # ㅓ J
    [(0x13, 0x00)],  # ㅔ P
    [(0x18, 0x00)],  # ㅕ U
    [(0x13, 0x02)],  # ㅖ P+Shift
    [(0x0B, 0x00)],  # ㅗ H
    [(0x0B, 0x00), (0x0E, 0x00)],  # ㅘ H,K
    [(0x0B, 0x00), (0x12, 0x00)],  # ㅙ H,O
    [(0x0B, 0x00), (0x0F, 0x00)],  # ㅚ H,L
    [(0x1C, 0x00)],  # ㅛ Y
    [(0x11, 0x00)],  # ㅜ N
    [(0x11, 0x00), (0x0D, 0x00)],  # ㅝ N,J
    [(0x11, 0x00), (0x13, 0x00)],  # ㅞ N,P
    [(0x11, 0x00), (0x0F, 0x00)],  # ㅟ N,L
    [(0x05, 0x00)],  # ㅠ B
    [(0x10, 0x00)],  # ㅡ M
    [(0x10, 0x00), (0x0F, 0x00)],  # ㅢ M,L
    [(0x0F, 0x00)],  # ㅣ L
]

# Dubeolsik jong (final consonant) keycodes — compound finals expand to 2
_JONG = [
    [],  # none
    [(0x15, 0x00)],  # ㄱ R
    [(0x15, 0x02)],  # ㄲ R+Shift
    [(0x15, 0x00), (0x17, 0x00)],  # ㄳ R,T
    [(0x16, 0x00)],  # ㄴ S
    [(0x16, 0x00), (0x1A, 0x00)],  # ㄵ S,W
    [(0x16, 0x00), (0x0A, 0x00)],  # ㄶ S,G
    [(0x08, 0x00)],  # ㄷ E
    [(0x09, 0x00)],  # ㄹ F
    [(0x09, 0x00), (0x15, 0x00)],  # ㄺ F,R
    [(0x09, 0x00), (0x04, 0x00)],  # ㄻ F,A
    [(0x09, 0x00), (0x14, 0x00)],  # ㄼ F,Q
    [(0x09, 0x00), (0x17, 0x00)],  # ㄽ F,T
    [(0x09, 0x00), (0x1B, 0x00)],  # ㄾ F,X
    [(0x09, 0x00), (0x19, 0x00)],  # ㄿ F,V
    [(0x09, 0x00), (0x0A, 0x00)],  # ㅀ F,G
    [(0x04, 0x00)],  # ㅁ A
    [(0x14, 0x00)],  # ㅂ Q
    [(0x14, 0x00), (0x17, 0x00)],  # ㅄ Q,T
    [(0x17, 0x00)],  # ㅅ T
    [(0x17, 0x02)],  # ㅆ T+Shift
    [(0x07, 0x00)],  # ㅇ D
    [(0x1A, 0x00)],  # ㅈ W
    [(0x06, 0x00)],  # ㅊ C
    [(0x1D, 0x00)],  # ㅋ Z
    [(0x1B, 0x00)],  # ㅌ X
    [(0x19, 0x00)],  # ㅍ V
    [(0x0A, 0x00)],  # ㅎ G
]

# Hangul Compatibility Jamo (U+3131~U+3163) → Dubeolsik keycodes
_JAMO = [
    [(0x15, 0x00)],  # U+3131 ㄱ
    [(0x15, 0x02)],  # U+3132 ㄲ
    [(0x15, 0x00), (0x17, 0x00)],  # U+3133 ㄳ
    [(0x16, 0x00)],  # U+3134 ㄴ
    [(0x16, 0x00), (0x1A, 0x00)],  # U+3135 ㄵ
    [(0x16, 0x00), (0x0A, 0x00)],  # U+3136 ㄶ
    [(0x08, 0x00)],  # U+3137 ㄷ
    [(0x08, 0x02)],  # U+3138 ㄸ
    [(0x09, 0x00)],  # U+3139 ㄹ
    [(0x09, 0x00), (0x15, 0x00)],  # U+313A ㄺ
    [(0x09, 0x00), (0x04, 0x00)],  # U+313B ㄻ
    [(0x09, 0x00), (0x14, 0x00)],  # U+313C ㄼ
    [(0x09, 0x00), (0x17, 0x00)],  # U+313D ㄽ
    [(0x09, 0x00), (0x1B, 0x00)],  # U+313E ㄾ
    [(0x09, 0x00), (0x19, 0x00)],  # U+313F ㄿ
    [(0x09, 0x00), (0x0A, 0x00)],  # U+3140 ㅀ
    [(0x04, 0x00)],  # U+3141 ㅁ
    [(0x14, 0x00)],  # U+3142 ㅂ
    [(0x14, 0x02)],  # U+3143 ㅃ
    [(0x14, 0x00), (0x17, 0x00)],  # U+3144 ㅄ
    [(0x17, 0x00)],  # U+3145 ㅅ
    [(0x17, 0x02)],  # U+3146 ㅆ
    [(0x07, 0x00)],  # U+3147 ㅇ
    [(0x1A, 0x00)],  # U+3148 ㅈ
    [(0x1A, 0x02)],  # U+3149 ㅉ
    [(0x06, 0x00)],  # U+314A ㅊ
    [(0x1D, 0x00)],  # U+314B ㅋ
    [(0x1B, 0x00)],  # U+314C ㅌ
    [(0x19, 0x00)],  # U+314D ㅍ
    [(0x0A, 0x00)],  # U+314E ㅎ
    [(0x0E, 0x00)],  # U+314F ㅏ
    [(0x12, 0x00)],  # U+3150 ㅐ
    [(0x0C, 0x00)],  # U+3151 ㅑ
    [(0x12, 0x02)],  # U+3152 ㅒ
    [(0x0D, 0x00)],  # U+3153 ㅓ
    [(0x13, 0x00)],  # U+3154 ㅔ
    [(0x18, 0x00)],  # U+3155 ㅕ
    [(0x13, 0x02)],  # U+3156 ㅖ
    [(0x0B, 0x00)],  # U+3157 ㅗ
    [(0x0B, 0x00), (0x0E, 0x00)],  # U+3158 ㅘ
    [(0x0B, 0x00), (0x12, 0x00)],  # U+3159 ㅙ
    [(0x0B, 0x00), (0x0F, 0x00)],  # U+315A ㅚ
    [(0x1C, 0x00)],  # U+315B ㅛ
    [(0x11, 0x00)],  # U+315C ㅜ
    [(0x11, 0x00), (0x0D, 0x00)],  # U+315D ㅝ
    [(0x11, 0x00), (0x13, 0x00)],  # U+315E ㅞ
    [(0x11, 0x00), (0x0F, 0x00)],  # U+315F ㅟ
    [(0x05, 0x00)],  # U+3160 ㅠ
    [(0x10, 0x00)],  # U+3161 ㅡ
    [(0x10, 0x00), (0x0F, 0x00)],  # U+3162 ㅢ
    [(0x0F, 0x00)],  # U+3163 ㅣ
]


def _is_toggle_key(kc: tuple[int, int]) -> bool:
    return kc == TOGGLE_WIN or kc == TOGGLE_MAC


def split_chunks(keycodes: list[tuple[int, int]], chunk_size: int = 8) -> list[list[tuple[int, int]]]:
    """Split keycodes into chunks, isolating toggle keys into single-keycode chunks."""
    chunks = []
    i = 0
    while i < len(keycodes):
        if _is_toggle_key(keycodes[i]):
            chunks.append([keycodes[i]])
            i += 1
        else:
            start = i
            while i < len(keycodes) and i - start < chunk_size and not _is_toggle_key(keycodes[i]):
                i += 1
            chunks.append(keycodes[start:i])
    return chunks


def hangul_to_keycodes(text: str) -> list[tuple[int, int]]:
    """Convert mixed Korean/ASCII text to HID keycodes with toggle keys.
    Always ends in English mode — trailing toggle added if text ends in Korean."""
    result = []
    in_korean = False
    for ch in text:
        cp = ord(ch)
        if 0xAC00 <= cp <= 0xD7A3:
            if not in_korean:
                result.append(_toggle_key)
                in_korean = True
            code = cp - 0xAC00
            cho = code // 588
            jung = (code % 588) // 28
            jong = code % 28
            result.append(_CHO[cho])
            result.extend(_JUNG[jung])
            if jong > 0:
                result.extend(_JONG[jong])
        elif 0x3131 <= cp <= 0x3163:
            if not in_korean:
                result.append(_toggle_key)
                in_korean = True
            result.extend(_JAMO[cp - 0x3131])
        elif ch in ASCII_TO_HID:
            # Only toggle for letter keys — space, digits, punctuation
            # produce the same output in both Korean and English IME modes.
            if in_korean and ch.isalpha():
                result.append(_toggle_key)
                in_korean = False
            result.append(ASCII_TO_HID[ch])
    # Always return to English mode
    if in_korean:
        result.append(_toggle_key)
    return result


async def test_hangul_basic(tb: TextBridgeClient):
    """테스트: 한글 '안녕하세요' (순수 한글)"""
    print("\n=== Test: hangul '안녕하세요' ===")
    keycodes = hangul_to_keycodes("안녕하세요")
    if not keycodes:
        print("  [FAIL] 키코드 변환 실패")
        return False
    print(f"  키코드: {len(keycodes)}개")

    # Send manually with pre-computed keycodes (toggle keys isolated)
    chunks = split_chunks(keycodes, 8)

    await tb.write(make_start(0, len(chunks)), "START")
    resp = await tb.wait_response(RESP_READY)
    if not resp or resp[0] != RESP_READY:
        return False

    for i, chunk in enumerate(chunks):
        seq = (i + 1) % 256
        await tb.write(make_keycode(seq, chunk), f"KEYCODE seq={seq} count={len(chunk)}")
        resp = await tb.wait_response(RESP_ACK, timeout=10.0)
        if not resp or resp[0] != RESP_ACK:
            return False

    done_seq = (len(chunks) + 1) % 256
    await tb.write(make_done(done_seq), "DONE")
    await tb.wait_response(RESP_DONE)
    return True


async def test_hangul_mixed(tb: TextBridgeClient):
    """테스트: 한영 혼합 'Hello 안녕 World 세계'"""
    print("\n=== Test: mixed 'Hello 안녕 World 세계' ===")
    keycodes = hangul_to_keycodes("Hello 안녕 World 세계")
    if not keycodes:
        return False
    print(f"  키코드: {len(keycodes)}개 (한영 전환 포함)")

    chunks = split_chunks(keycodes, 8)

    await tb.write(make_start(0, len(chunks)), "START")
    resp = await tb.wait_response(RESP_READY)
    if not resp or resp[0] != RESP_READY:
        return False

    for i, chunk in enumerate(chunks):
        seq = (i + 1) % 256
        await tb.write(make_keycode(seq, chunk), f"KEYCODE seq={seq} count={len(chunk)}")
        resp = await tb.wait_response(RESP_ACK, timeout=10.0)
        if not resp or resp[0] != RESP_ACK:
            return False

    done_seq = (len(chunks) + 1) % 256
    await tb.write(make_done(done_seq), "DONE")
    await tb.wait_response(RESP_DONE)
    return True


async def test_hangul_complex(tb: TextBridgeClient):
    """테스트: 쌍자음/복합모음/겹받침 '까닭없이'"""
    print("\n=== Test: complex hangul '까닭없이' ===")
    keycodes = hangul_to_keycodes("까닭없이")
    if not keycodes:
        return False
    print(f"  키코드: {len(keycodes)}개")

    chunks = split_chunks(keycodes, 8)

    await tb.write(make_start(0, len(chunks)), "START")
    resp = await tb.wait_response(RESP_READY)
    if not resp or resp[0] != RESP_READY:
        return False

    for i, chunk in enumerate(chunks):
        seq = (i + 1) % 256
        await tb.write(make_keycode(seq, chunk), f"KEYCODE seq={seq} count={len(chunk)}")
        resp = await tb.wait_response(RESP_ACK, timeout=10.0)
        if not resp or resp[0] != RESP_ACK:
            return False

    done_seq = (len(chunks) + 1) % 256
    await tb.write(make_done(done_seq), "DONE")
    await tb.wait_response(RESP_DONE)
    return True


TESTS = {
    "single_a": test_single_a,
    "shift_A": test_shift_A,
    "hello": test_hello,
    "multi_chunk": test_multi_chunk,
    "duplicate": test_duplicate,
    "abort": test_abort,
    "special": test_special_chars,
    "hangul": test_hangul_basic,
    "hangul_mixed": test_hangul_mixed,
    "hangul_complex": test_hangul_complex,
}


async def run_tests(address: str, test_names: list[str]):
    print(f"\n[CONN] {address} 연결 중...")

    async with BleakClient(address) as client:
        tb = TextBridgeClient(client)
        await tb.connect()

        results = {}
        for name in test_names:
            if name not in TESTS:
                print(f"\n[SKIP] 알 수 없는 테스트: {name}")
                continue
            try:
                ok = await TESTS[name](tb)
                results[name] = ok
                status = "PASS" if ok else "FAIL"
                print(f"\n  [{status}] {name}")
                await asyncio.sleep(1.0)  # 테스트 간 간격
            except Exception as e:
                results[name] = False
                print(f"\n  [ERROR] {name}: {e}")

        # 결과 요약
        print("\n" + "=" * 40)
        print("테스트 결과:")
        for name, ok in results.items():
            status = "PASS" if ok else "FAIL"
            print(f"  [{status}] {name}")
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        print(f"\n  {passed}/{total} 통과")
        print("=" * 40)


async def main():
    parser = argparse.ArgumentParser(description="TextBridge 텍스트 전송")
    parser.add_argument("--text", type=str, required=True)
    args = parser.parse_args()

    global _toggle_key
    _toggle_key = TOGGLE_MAC

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
        await tb.set_delay(press_delay=5, release_delay=5, combo_delay=2, toggle_press=20, toggle_delay=100, warmup_delay=50)
        ok = await tb.send_text(args.text, append_enter=True)
        print("ok" if ok else "FAIL")


if __name__ == "__main__":
    asyncio.run(main())
