import 'package:flutter_test/flutter_test.dart';
import 'package:textbridge_app/models/protocol.dart';
import 'package:textbridge_app/services/hangul_service.dart';

void main() {
  group('isHangulSyllable', () {
    test('valid syllables', () {
      expect(HangulService.isHangulSyllable(0xAC00), isTrue); // 가
      expect(HangulService.isHangulSyllable(0xD7A3), isTrue); // 힣
      expect(HangulService.isHangulSyllable(0xC548), isTrue); // 안
    });

    test('non-syllables', () {
      expect(HangulService.isHangulSyllable(0x41), isFalse); // A
      expect(HangulService.isHangulSyllable(0xABFF), isFalse); // before range
      expect(HangulService.isHangulSyllable(0xD7A4), isFalse); // after range
    });
  });

  group('decompose', () {
    test('가 (U+AC00) = ㄱ(0) + ㅏ(0) + none(0)', () {
      final d = HangulService.decompose(0xAC00);
      expect(d.cho, 0);
      expect(d.jung, 0);
      expect(d.jong, 0);
    });

    test('나 (U+B098) = ㄴ(2) + ㅏ(0) + none(0)', () {
      final d = HangulService.decompose(0xB098);
      expect(d.cho, 2);
      expect(d.jung, 0);
      expect(d.jong, 0);
    });

    test('안 (U+C548) = ㅇ(11) + ㅏ(0) + ㄴ(4)', () {
      final d = HangulService.decompose(0xC548);
      expect(d.cho, 11);
      expect(d.jung, 0);
      expect(d.jong, 4);
    });

    test('녕 (U+B155) = ㄴ(2) + ㅕ(6) + ㅇ(21)', () {
      final d = HangulService.decompose(0xB155);
      expect(d.cho, 2);
      expect(d.jung, 6);
      expect(d.jong, 21);
    });

    test('까 (U+AE4C) = ㄲ(1) + ㅏ(0) + none(0)', () {
      final d = HangulService.decompose(0xAE4C);
      expect(d.cho, 1);
      expect(d.jung, 0);
      expect(d.jong, 0);
    });

    test('따 (U+B530) = ㄸ(4) + ㅏ(0) + none(0)', () {
      final d = HangulService.decompose(0xB530);
      expect(d.cho, 4);
      expect(d.jung, 0);
      expect(d.jong, 0);
    });

    // 왂 (U+C102): research.md claimed ㅇ+ㅘ+ㄵ, but actual math:
    // code = 0xC102 - 0xAC00 = 5378
    // cho = 5378 ~/ 588 = 9 (ㅅ), jung = (5378 % 588) ~/ 28 = 3 (ㅒ), jong = 86 % 28 = 2 (ㄲ)
    test('왂 (U+C102) = ㅅ(9) + ㅒ(3) + ㄲ(2)', () {
      final d = HangulService.decompose(0xC102);
      expect(d.cho, 9); // ㅅ
      expect(d.jung, 3); // ㅒ
      expect(d.jong, 2); // ㄲ
    });

    test('값 (U+AC12) = ㄱ(0) + ㅏ(0) + ㅄ(18)', () {
      final d = HangulService.decompose(0xAC12);
      expect(d.cho, 0); // ㄱ
      expect(d.jung, 0); // ㅏ
      expect(d.jong, 18); // ㅄ
    });

    test('앉 (U+C549) = ㅇ(11) + ㅏ(0) + ㄵ(5)', () {
      final d = HangulService.decompose(0xC549);
      expect(d.cho, 11);
      expect(d.jung, 0);
      expect(d.jong, 5);
    });

    test('왕 (U+C655) compound vowel ㅘ', () {
      final d = HangulService.decompose(0xC655);
      expect(d.cho, 11); // ㅇ
      expect(d.jung, 9); // ㅘ
      expect(d.jong, 21); // ㅇ
    });
  });

  group('syllableToKeycodes', () {
    test('가 → R, K (ㄱ + ㅏ)', () {
      final codes = HangulService.syllableToKeycodes(0xAC00);
      expect(codes, [
        const KeycodePair(0x15, 0x00), // R (ㄱ)
        const KeycodePair(0x0E, 0x00), // K (ㅏ)
      ]);
    });

    test('안 → D, K, S (ㅇ + ㅏ + ㄴ)', () {
      final codes = HangulService.syllableToKeycodes(0xC548);
      expect(codes, [
        const KeycodePair(0x07, 0x00), // D (ㅇ)
        const KeycodePair(0x0E, 0x00), // K (ㅏ)
        const KeycodePair(0x16, 0x00), // S (ㄴ)
      ]);
    });

    test('까 → R+Shift, K (ㄲ + ㅏ)', () {
      final codes = HangulService.syllableToKeycodes(0xAE4C);
      expect(codes, [
        const KeycodePair(0x15, 0x02), // R+Shift (ㄲ)
        const KeycodePair(0x0E, 0x00), // K (ㅏ)
      ]);
    });

    test('왕 → D, H, K, D (ㅇ + ㅘ(H,K) + ㅇ)', () {
      final codes = HangulService.syllableToKeycodes(0xC655);
      expect(codes, [
        const KeycodePair(0x07, 0x00), // D (ㅇ)
        const KeycodePair(0x0B, 0x00), // H (ㅗ)
        const KeycodePair(0x0E, 0x00), // K (ㅏ)
        const KeycodePair(0x07, 0x00), // D (ㅇ)
      ]);
    });

    test('값 → R, K, Q, T (ㄱ + ㅏ + ㅄ(Q,T))', () {
      final codes = HangulService.syllableToKeycodes(0xAC12);
      expect(codes, [
        const KeycodePair(0x15, 0x00), // R (ㄱ)
        const KeycodePair(0x0E, 0x00), // K (ㅏ)
        const KeycodePair(0x14, 0x00), // Q (ㅂ)
        const KeycodePair(0x17, 0x00), // T (ㅅ)
      ]);
    });

    test('앉 → D, K, S, W (ㅇ + ㅏ + ㄵ(S,W))', () {
      final codes = HangulService.syllableToKeycodes(0xC549);
      expect(codes, [
        const KeycodePair(0x07, 0x00), // D (ㅇ)
        const KeycodePair(0x0E, 0x00), // K (ㅏ)
        const KeycodePair(0x16, 0x00), // S (ㄴ)
        const KeycodePair(0x1A, 0x00), // W (ㅈ)
      ]);
    });

    // 안녕하세요 from research.md Section 8
    test('안녕하세요 matches research.md reference', () {
      // 안: D(0x07), K(0x0E), S(0x16)
      final an = HangulService.syllableToKeycodes('안'.codeUnitAt(0));
      expect(an.map((k) => k.keycode).toList(), [0x07, 0x0E, 0x16]);

      // 녕: S(0x16), U(0x18), D(0x07)
      final nyeong = HangulService.syllableToKeycodes('녕'.codeUnitAt(0));
      expect(nyeong.map((k) => k.keycode).toList(), [0x16, 0x18, 0x07]);

      // 하: G(0x0A), K(0x0E)
      final ha = HangulService.syllableToKeycodes('하'.codeUnitAt(0));
      expect(ha.map((k) => k.keycode).toList(), [0x0A, 0x0E]);

      // 세: T(0x17), P(0x13)
      final se = HangulService.syllableToKeycodes('세'.codeUnitAt(0));
      expect(se.map((k) => k.keycode).toList(), [0x17, 0x13]);

      // 요: D(0x07), Y(0x1C)
      final yo = HangulService.syllableToKeycodes('요'.codeUnitAt(0));
      expect(yo.map((k) => k.keycode).toList(), [0x07, 0x1C]);
    });

    test('웨 compound vowel ㅞ → N, P', () {
      // 웨 (U+C6E8) = ㅇ + ㅞ + none
      final codes = HangulService.syllableToKeycodes('웨'.codeUnitAt(0));
      expect(codes, [
        const KeycodePair(0x07, 0x00), // D (ㅇ)
        const KeycodePair(0x11, 0x00), // N (ㅜ)
        const KeycodePair(0x13, 0x00), // P (ㅔ)
      ]);
    });

    test('의 compound vowel ㅢ → M, L', () {
      // 의 (U+C758) = ㅇ + ㅢ + none
      final codes = HangulService.syllableToKeycodes('의'.codeUnitAt(0));
      expect(codes, [
        const KeycodePair(0x07, 0x00), // D (ㅇ)
        const KeycodePair(0x10, 0x00), // M (ㅡ)
        const KeycodePair(0x0F, 0x00), // L (ㅣ)
      ]);
    });
  });
}
