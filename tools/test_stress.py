#!/usr/bin/env python3
"""
TextBridge 대용량 전송 스트레스 테스트
- 5,000자 영문 소스 코드 전송 후 PC 수신 텍스트와 비교
- 5회 연속 전송 실행
- 전송 속도 측정 (chars/sec)
- pynput으로 PC 입력 캡처하여 원본과 diff

사용법:
    python3 test_stress.py --test single        # 1회 전송
    python3 test_stress.py --test repeat         # 5회 반복
    python3 test_stress.py --test speed          # 속도 측정
    python3 test_stress.py --test all            # 전체
    python3 test_stress.py --chars 1000          # 글자 수 지정
    python3 test_stress.py --no-pair             # VIA 자동 페어링 스킵
    python3 test_stress.py --no-verify           # pynput 검증 스킵
"""

import asyncio
import argparse
import sys
import time

try:
    from bleak import BleakScanner, BleakClient
except ImportError:
    print("bleak 필요: pip3 install bleak")
    sys.exit(1)

# Import shared protocol from test_phase3_protocol
from test_phase3_protocol import (
    TB_SVC_UUID, TB_TX_UUID, TB_RX_UUID, DEVICE_NAME,
    TextBridgeClient, HIDVerifier, scan, via_start_pairing,
    text_to_keycodes,
)

# Sample source code for stress testing
SAMPLE_CODE = '''\
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct node {
    int value;
    struct node *next;
} Node;

Node *create_node(int val) {
    Node *n = (Node *)malloc(sizeof(Node));
    if (!n) return NULL;
    n->value = val;
    n->next = NULL;
    return n;
}

void insert_sorted(Node **head, int val) {
    Node *new_node = create_node(val);
    if (!new_node) return;
    if (!*head || (*head)->value >= val) {
        new_node->next = *head;
        *head = new_node;
        return;
    }
    Node *curr = *head;
    while (curr->next && curr->next->value < val) {
        curr = curr->next;
    }
    new_node->next = curr->next;
    curr->next = new_node;
}

void print_list(Node *head) {
    while (head) {
        printf("%d -> ", head->value);
        head = head->next;
    }
    printf("NULL\\n");
}

void free_list(Node *head) {
    while (head) {
        Node *tmp = head;
        head = head->next;
        free(tmp);
    }
}

int binary_search(int *arr, int n, int target) {
    int lo = 0, hi = n - 1;
    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2;
        if (arr[mid] == target) return mid;
        if (arr[mid] < target) lo = mid + 1;
        else hi = mid - 1;
    }
    return -1;
}

void quicksort(int *arr, int lo, int hi) {
    if (lo >= hi) return;
    int pivot = arr[hi];
    int i = lo;
    for (int j = lo; j < hi; j++) {
        if (arr[j] < pivot) {
            int tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
            i++;
        }
    }
    int tmp = arr[i]; arr[i] = arr[hi]; arr[hi] = tmp;
    quicksort(arr, lo, i - 1);
    quicksort(arr, i + 1, hi);
}

int main(int argc, char **argv) {
    Node *list = NULL;
    for (int i = 0; i < 20; i++) {
        insert_sorted(&list, (i * 7 + 3) % 20);
    }
    print_list(list);

    int arr[] = {1, 3, 5, 7, 9, 11, 13, 15, 17, 19};
    int n = sizeof(arr) / sizeof(arr[0]);
    quicksort(arr, 0, n - 1);

    for (int i = 0; i < n; i++) {
        int idx = binary_search(arr, n, arr[i]);
        printf("Found %d at index %d\\n", arr[i], idx);
    }

    free_list(list);
    return 0;
}
'''


def generate_text(char_count: int) -> str:
    """Generate test text of approximately char_count characters."""
    if char_count <= len(SAMPLE_CODE):
        return SAMPLE_CODE[:char_count]
    # Repeat sample to reach target length
    repeats = (char_count // len(SAMPLE_CODE)) + 1
    return (SAMPLE_CODE * repeats)[:char_count]


def diff_texts(expected: str, actual: str) -> str:
    """Show first difference between two texts."""
    for i, (e, a) in enumerate(zip(expected, actual)):
        if e != a:
            ctx_start = max(0, i - 20)
            return (
                f"First diff at position {i}:\n"
                f"  expected[{ctx_start}:{i+20}]: {repr(expected[ctx_start:i+20])}\n"
                f"  actual[{ctx_start}:{i+20}]:   {repr(actual[ctx_start:i+20])}"
            )
    if len(expected) != len(actual):
        return f"Length mismatch: expected {len(expected)}, got {len(actual)}"
    return ""


async def test_single_transmission(
    address: str, char_count: int, verifier: HIDVerifier = None
) -> tuple[bool, float]:
    """Single large text transmission. Returns (success, chars_per_sec)."""
    text = generate_text(char_count)
    keycodes = text_to_keycodes(text)

    print(f"\n  Text length: {len(text)} chars")
    print(f"  Mappable keycodes: {len(keycodes)}")

    if verifier:
        verifier.clear()

    async with BleakClient(address) as client:
        tb = TextBridgeClient(client, verifier=verifier)
        await tb.connect()

        start_time = time.monotonic()
        ok = await tb.send_text(text, verify=False)
        elapsed = time.monotonic() - start_time

        chars_per_sec = len(text) / elapsed if elapsed > 0 else 0

        print(f"\n  Elapsed: {elapsed:.2f}s ({chars_per_sec:.0f} chars/sec)")

        if not ok:
            print("  [FAIL] Transmission failed")
            return False, chars_per_sec

        if verifier:
            # Wait for HID injection to complete
            wait_time = len(keycodes) * 0.02 + 2.0  # ~20ms per key + buffer
            print(f"  Waiting {wait_time:.1f}s for HID injection...")
            await asyncio.sleep(wait_time)
            captured = verifier.get_captured()
            if captured == text:
                print(f"  [PASS] {len(captured)} chars verified")
            else:
                d = diff_texts(text, captured)
                print(f"  [FAIL] Verification failed\n  {d}")
                return False, chars_per_sec

        return True, chars_per_sec


async def test_repeat(
    address: str, char_count: int, runs: int, verifier: HIDVerifier = None
) -> bool:
    """Repeat transmission multiple times."""
    print(f"\n=== Repeat test: {runs} runs of {char_count} chars ===")
    results = []

    for i in range(runs):
        print(f"\n--- Run {i + 1}/{runs} ---")
        ok, cps = await test_single_transmission(address, char_count, verifier)
        results.append((ok, cps))
        if not ok:
            print(f"  [FAIL] Run {i + 1} failed, stopping")
            break
        # Brief pause between runs
        await asyncio.sleep(2.0)

    # Summary
    print(f"\n{'='*40}")
    print(f"Repeat test results ({char_count} chars x {runs}):")
    for i, (ok, cps) in enumerate(results):
        status = "PASS" if ok else "FAIL"
        print(f"  Run {i+1}: [{status}] {cps:.0f} chars/sec")

    passed = sum(1 for ok, _ in results if ok)
    print(f"\n  {passed}/{len(results)} passed")
    print(f"{'='*40}")
    return passed == len(results)


async def test_speed(address: str, verifier: HIDVerifier = None) -> bool:
    """Measure transmission speed at different payload sizes."""
    print("\n=== Speed test ===")
    sizes = [100, 500, 1000, 2000, 5000]
    results = []

    for size in sizes:
        print(f"\n--- {size} chars ---")
        ok, cps = await test_single_transmission(address, size, verifier=None)
        results.append((size, ok, cps))
        await asyncio.sleep(2.0)

    # Summary table
    print(f"\n{'='*50}")
    print(f"{'Size':>6} | {'Status':>6} | {'Speed':>12} | {'Time':>8}")
    print(f"{'-'*6}-+-{'-'*6}-+-{'-'*12}-+-{'-'*8}")
    for size, ok, cps in results:
        status = "PASS" if ok else "FAIL"
        est_time = size / cps if cps > 0 else 0
        print(f"{size:>6} | {status:>6} | {cps:>8.0f} c/s | {est_time:>6.1f}s")
    print(f"{'='*50}")
    return all(ok for _, ok, _ in results)


TESTS = {
    "single": "single",
    "repeat": "repeat",
    "speed": "speed",
}


async def main():
    parser = argparse.ArgumentParser(description="TextBridge 스트레스 테스트")
    parser.add_argument("--test", type=str, default="single",
                        help="테스트: single, repeat, speed, all")
    parser.add_argument("--chars", type=int, default=5000,
                        help="전송 글자 수 (기본 5000)")
    parser.add_argument("--runs", type=int, default=5,
                        help="반복 횟수 (기본 5)")
    parser.add_argument("--address", type=str, default=None)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--no-pair", action="store_true")
    parser.add_argument("--no-verify", action="store_true")
    args = parser.parse_args()

    # Auto pairing
    if not args.no_pair:
        print("\n[STEP 1] VIA 명령으로 TextBridge 광고 시작")
        if not via_start_pairing():
            print("[WARN] VIA 페어링 실패. 수동으로 Fn+1을 누르세요.")
        else:
            await asyncio.sleep(2.0)

    # HID verification
    verifier = None
    if not args.no_verify:
        verifier = HIDVerifier()
        if not verifier.start():
            print("[WARN] pynput 초기화 실패. HID 검증 없이 진행.")
            verifier = None

    try:
        # Find device
        address = args.address
        if not address:
            print("\n[STEP 2] BLE 스캔")
            devices = await scan(args.timeout)
            if not devices:
                return
            address = devices[0].address

        # Run tests
        test_list = (
            list(TESTS.keys()) if args.test == "all"
            else [t.strip() for t in args.test.split(",")]
        )

        results = {}
        for test_name in test_list:
            if test_name == "single":
                print(f"\n=== Single transmission: {args.chars} chars ===")
                ok, _ = await test_single_transmission(
                    address, args.chars, verifier
                )
                results["single"] = ok
            elif test_name == "repeat":
                ok = await test_repeat(
                    address, args.chars, args.runs, verifier
                )
                results["repeat"] = ok
            elif test_name == "speed":
                ok = await test_speed(address, verifier)
                results["speed"] = ok
            else:
                print(f"[SKIP] Unknown test: {test_name}")

            await asyncio.sleep(2.0)

        # Final summary
        if results:
            print(f"\n{'='*40}")
            print("Final results:")
            for name, ok in results.items():
                print(f"  [{('PASS' if ok else 'FAIL')}] {name}")
            print(f"{'='*40}")

    finally:
        if verifier:
            verifier.stop()


if __name__ == "__main__":
    asyncio.run(main())
