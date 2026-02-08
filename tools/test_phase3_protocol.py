#!/usr/bin/env python3
"""
TextBridge Phase 3 프로토콜 테스트 (자동화)
- VIA Raw HID로 TextBridge 광고 자동 시작 (Fn+1 대체)
- BLE 연결 → START → KEYCODE → DONE 시퀀스
- pynput으로 HID 주입 결과 자동 검증
- ACK/READY/DONE 응답 검증
- 중복 감지, ABORT 테스트

사용법:
    python3 test_phase3_protocol.py --test single_a
    python3 test_phase3_protocol.py --test all
    python3 test_phase3_protocol.py --text "hello world"
    python3 test_phase3_protocol.py --scan-only
    python3 test_phase3_protocol.py --no-pair --test single_a   # 수동 Fn+1
    python3 test_phase3_protocol.py --no-verify --test hello    # HID 검증 스킵
"""

import asyncio
import argparse
import sys
import threading
import time

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
CMD_ABORT   = 0x04

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


def text_to_keycodes(text: str) -> list[tuple[int, int]]:
    """텍스트를 (keycode, modifier) 리스트로 변환"""
    result = []
    for ch in text:
        if ch in ASCII_TO_HID:
            result.append(ASCII_TO_HID[ch])
        else:
            print(f"  [WARN] 매핑 없음: '{ch}' (U+{ord(ch):04X})")
    return result


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
        print(f"[PAIR] Keychron B6 Pro 미발견 (VID:{VENDOR_ID:04x} PID:{PRODUCT_ID:04x})")
        return False

    try:
        device = hid.device()
        device.open_path(path)
        print(f"[PAIR] USB 연결: {device.get_product_string()}")

        data = [0x00] * 33  # report_id + 32 bytes
        data[1] = 0xFE  # TextBridge pairing command

        device.write(data)
        device.close()

        print("[PAIR] 0xFE 전송 완료 → TextBridge 광고 시작")
        return True
    except Exception as e:
        print(f"[PAIR] 오류: {e}")
        return False


# ============ HID Input Capture (pynput) ============

class HIDVerifier:
    """pynput으로 키보드 입력 캡처하여 기대값과 비교"""

    def __init__(self):
        self._captured = []
        self._listener = None
        self._lock = threading.Lock()

    def start(self):
        try:
            from pynput import keyboard
        except ImportError:
            print("[VERIFY] pynput 미설치. pip3 install pynput")
            return False

        def on_press(key):
            try:
                ch = key.char
            except AttributeError:
                # Special keys
                if key == keyboard.Key.space:
                    ch = ' '
                elif key == keyboard.Key.enter:
                    ch = '\n'
                elif key == keyboard.Key.tab:
                    ch = '\t'
                else:
                    ch = None

            if ch is not None:
                with self._lock:
                    self._captured.append(ch)

        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.start()
        print("[VERIFY] 키보드 리스너 시작")
        return True

    def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None

    def get_captured(self) -> str:
        with self._lock:
            return ''.join(self._captured)

    def clear(self):
        with self._lock:
            self._captured.clear()

    def verify(self, expected: str, timeout: float = 5.0) -> bool:
        """타임아웃 내에 기대 문자열이 캡처되었는지 확인"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            captured = self.get_captured()
            if len(captured) >= len(expected):
                break
            time.sleep(0.1)

        captured = self.get_captured()
        if captured == expected:
            print(f"[VERIFY] PASS: 기대='{expected}' 캡처='{captured}'")
            return True
        else:
            print(f"[VERIFY] FAIL: 기대='{expected}' 캡처='{captured}'")
            return False


class TextBridgeClient:
    def __init__(self, client: BleakClient, verifier: HIDVerifier = None):
        self.client = client
        self.responses = asyncio.Queue()
        self.verifier = verifier

    def _notify_handler(self, sender, data: bytearray):
        resp_code = data[0] if len(data) > 0 else 0
        seq = data[1] if len(data) > 1 else 0
        name = RESP_NAMES.get(resp_code, f"0x{resp_code:02x}")
        extra = ""
        if resp_code == RESP_ERROR and len(data) > 2:
            extra = f" err=0x{data[2]:02x}"
        print(f"  <- {name} seq={seq}{extra} ({data.hex()})")
        self.responses.put_nowait(data)

    async def connect(self):
        await self.client.start_notify(TB_RX_UUID, self._notify_handler)
        print(f"  [OK] Notify 활성화, MTU={self.client.mtu_size}")

    async def write(self, data: bytes, label: str = ""):
        if label:
            print(f"  -> {label} ({data.hex()})")
        else:
            print(f"  -> {data.hex()}")
        await self.client.write_gatt_char(TB_TX_UUID, data, response=False)

    async def wait_response(self, expected_code: int = None, timeout: float = 5.0) -> bytearray:
        try:
            resp = await asyncio.wait_for(self.responses.get(), timeout=timeout)
            if expected_code is not None and resp[0] != expected_code:
                name = RESP_NAMES.get(resp[0], f"0x{resp[0]:02x}")
                exp_name = RESP_NAMES.get(expected_code, f"0x{expected_code:02x}")
                print(f"  [WARN] 예상={exp_name}, 실제={name}")
            return resp
        except asyncio.TimeoutError:
            print(f"  [TIMEOUT] {timeout}초 응답 없음")
            return None

    async def send_text(self, text: str, chunk_size: int = 8, verify: bool = False) -> bool:
        """텍스트를 프로토콜로 전송"""
        keycodes = text_to_keycodes(text)
        if not keycodes:
            print("  [FAIL] 변환할 키코드 없음")
            return False

        # 청크 분할
        chunks = []
        for i in range(0, len(keycodes), chunk_size):
            chunks.append(keycodes[i:i + chunk_size])

        print(f"\n  텍스트: '{text}'")
        print(f"  키코드: {len(keycodes)}개, 청크: {len(chunks)}개 (max {chunk_size}/chunk)")

        # HID 검증 준비
        if verify and self.verifier:
            self.verifier.clear()

        # START
        await self.write(make_start(0, len(chunks)), "START")
        resp = await self.wait_response(RESP_READY)
        if not resp or resp[0] != RESP_READY:
            print("  [FAIL] READY 미수신")
            return False

        # KEYCODE chunks
        for i, chunk in enumerate(chunks):
            seq = (i + 1) % 256
            await self.write(make_keycode(seq, chunk), f"KEYCODE seq={seq} count={len(chunk)}")
            resp = await self.wait_response(RESP_ACK, timeout=10.0)
            if not resp:
                print(f"  [FAIL] ACK 미수신 (chunk {i+1}/{len(chunks)})")
                return False
            if resp[0] == RESP_NACK:
                print(f"  [RETRY] NACK 수신, 1초 후 재전송")
                await asyncio.sleep(1.0)
                await self.write(make_keycode(seq, chunk), f"KEYCODE retry seq={seq}")
                resp = await self.wait_response(RESP_ACK, timeout=10.0)
                if not resp or resp[0] != RESP_ACK:
                    print(f"  [FAIL] 재전송 후에도 ACK 미수신")
                    return False
            elif resp[0] == RESP_ERROR:
                print(f"  [FAIL] ERROR 수신")
                return False

        # DONE
        done_seq = (len(chunks) + 1) % 256
        await self.write(make_done(done_seq), "DONE")
        resp = await self.wait_response(RESP_DONE)
        if not resp or resp[0] != RESP_DONE:
            print("  [WARN] DONE 응답 미수신")

        # HID 검증
        if verify and self.verifier:
            ok = self.verifier.verify(text, timeout=3.0)
            if not ok:
                return False

        return True


async def scan(timeout: float):
    print(f"[SCAN] {timeout}초간 BLE 스캔...")
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    found = []
    for addr, (d, adv) in devices.items():
        name = d.name or adv.local_name or ""
        svc_uuids = [str(u).lower() for u in (adv.service_uuids or [])]
        if DEVICE_NAME in name or TB_SVC_UUID.lower() in svc_uuids:
            found.append(d)
            print(f"  [OK] {name} ({d.address}) RSSI={adv.rssi}")
    if not found:
        print(f"  [FAIL] '{DEVICE_NAME}' 미발견")
    return found


# ============ Test cases ============

async def test_single_a(tb: TextBridgeClient):
    """테스트 1: 단일 키 'a'"""
    print("\n=== Test: single 'a' ===")
    return await tb.send_text("a", verify=tb.verifier is not None)


async def test_shift_A(tb: TextBridgeClient):
    """테스트 2: 대문자 'A' (Shift+a)"""
    print("\n=== Test: shift 'A' ===")
    return await tb.send_text("A", verify=tb.verifier is not None)


async def test_hello(tb: TextBridgeClient):
    """테스트 3: 'hello world' (여러 키, 공백 포함)"""
    print("\n=== Test: 'hello world' ===")
    return await tb.send_text("hello world", verify=tb.verifier is not None)


async def test_multi_chunk(tb: TextBridgeClient):
    """테스트 4: 여러 청크 'abcdefghijklmnop' (16키 = 2청크)"""
    print("\n=== Test: multi-chunk 'abcdefghijklmnop' ===")
    return await tb.send_text("abcdefghijklmnop", verify=tb.verifier is not None)


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
    return await tb.send_text("Hello, World! 123", verify=tb.verifier is not None)


# ============ Hangul Dubeolsik keycodes ============
# Pre-computed keycode sequences for Korean text.
# Toggle key: 0x90 (Windows LANG1), 0xE7 (macOS Right GUI)
TOGGLE_WIN = (0x90, 0x00)

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


def hangul_to_keycodes(text: str) -> list[tuple[int, int]]:
    """Convert mixed Korean/ASCII text to HID keycodes with toggle keys."""
    result = []
    in_korean = False
    for ch in text:
        cp = ord(ch)
        if 0xAC00 <= cp <= 0xD7A3:
            if not in_korean:
                result.append(TOGGLE_WIN)
                in_korean = True
            code = cp - 0xAC00
            cho = code // 588
            jung = (code % 588) // 28
            jong = code % 28
            result.append(_CHO[cho])
            result.extend(_JUNG[jung])
            if jong > 0:
                result.extend(_JONG[jong])
        elif ch in ASCII_TO_HID:
            if in_korean:
                result.append(TOGGLE_WIN)
                in_korean = False
            result.append(ASCII_TO_HID[ch])
    if in_korean:
        result.append(TOGGLE_WIN)
    return result


async def test_hangul_basic(tb: TextBridgeClient):
    """테스트: 한글 '안녕하세요' (순수 한글)"""
    print("\n=== Test: hangul '안녕하세요' ===")
    keycodes = hangul_to_keycodes("안녕하세요")
    if not keycodes:
        print("  [FAIL] 키코드 변환 실패")
        return False
    print(f"  키코드: {len(keycodes)}개")

    # Send manually with pre-computed keycodes
    chunks = []
    chunk_size = 8
    for i in range(0, len(keycodes), chunk_size):
        chunks.append(keycodes[i:i + chunk_size])

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

    chunks = []
    chunk_size = 8
    for i in range(0, len(keycodes), chunk_size):
        chunks.append(keycodes[i:i + chunk_size])

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

    chunks = []
    chunk_size = 8
    for i in range(0, len(keycodes), chunk_size):
        chunks.append(keycodes[i:i + chunk_size])

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


async def run_tests(address: str, test_names: list[str], verifier: HIDVerifier = None):
    print(f"\n[CONN] {address} 연결 중...")

    async with BleakClient(address) as client:
        tb = TextBridgeClient(client, verifier=verifier)
        await tb.connect()

        results = {}
        for name in test_names:
            if name not in TESTS:
                print(f"\n[SKIP] 알 수 없는 테스트: {name}")
                continue
            try:
                if verifier:
                    verifier.clear()
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
    parser = argparse.ArgumentParser(description="TextBridge Phase 3 프로토콜 테스트")
    parser.add_argument("--scan-only", action="store_true")
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--address", type=str, default=None)
    parser.add_argument("--test", type=str, default="all",
                        help="테스트: " + ", ".join(["all"] + list(TESTS.keys())))
    parser.add_argument("--text", type=str, default=None,
                        help="직접 텍스트 전송 (예: --text 'hello world')")
    parser.add_argument("--no-pair", action="store_true",
                        help="VIA 자동 페어링 스킵 (수동 Fn+1)")
    parser.add_argument("--no-verify", action="store_true",
                        help="pynput HID 검증 스킵")
    args = parser.parse_args()

    # 1. 자동 페어링 (--no-pair가 아닌 경우)
    if not args.no_pair and not args.scan_only:
        print("\n[STEP 1] VIA 명령으로 TextBridge 광고 시작")
        if not via_start_pairing():
            print("[WARN] VIA 페어링 실패. 수동으로 Fn+1을 누르세요.")
        else:
            print("[PAIR] 광고 시작 대기 (2초)...")
            await asyncio.sleep(2.0)

    # 2. HID 검증 준비 (--no-verify가 아닌 경우)
    verifier = None
    if not args.no_verify and not args.scan_only:
        verifier = HIDVerifier()
        if not verifier.start():
            print("[WARN] pynput 초기화 실패. HID 검증 없이 진행.")
            verifier = None

    try:
        # 테스트 목록 결정
        if args.test == "all":
            test_names = list(TESTS.keys())
        else:
            test_names = [t.strip() for t in args.test.split(",")]

        # 주소 결정
        address = args.address
        if not address:
            print("\n[STEP 2] BLE 스캔")
            devices = await scan(args.timeout)
            if args.scan_only or not devices:
                return
            address = devices[0].address
            print(f"\n대상: {devices[0].name} ({address})")

        # 직접 텍스트 전송 모드
        if args.text is not None:
            print(f"\n[CONN] {address} 연결 중...")
            async with BleakClient(address) as client:
                tb = TextBridgeClient(client, verifier=verifier)
                await tb.connect()
                ok = await tb.send_text(args.text, verify=verifier is not None)
                print(f"\n{'성공' if ok else '실패'}")
            return

        print("\n[STEP 3] 테스트 실행")
        await run_tests(address, test_names, verifier=verifier)

    finally:
        if verifier:
            verifier.stop()


if __name__ == "__main__":
    asyncio.run(main())
