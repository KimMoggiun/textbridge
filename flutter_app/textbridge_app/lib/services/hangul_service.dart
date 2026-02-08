import '../models/protocol.dart';

/// Hangul syllable decomposition and Dubeolsik keyboard mapping.
/// Based on research.md: Unicode 0xAC00~0xD7A3 decomposition algorithm.
class HangulService {
  static const int _syllableBase = 0xAC00;
  static const int _syllableEnd = 0xD7A3;

  static bool isHangulSyllable(int codepoint) =>
      codepoint >= _syllableBase && codepoint <= _syllableEnd;

  /// Decompose a Hangul syllable into (cho, jung, jong) indices.
  static ({int cho, int jung, int jong}) decompose(int codepoint) {
    final code = codepoint - _syllableBase;
    return (
      cho: code ~/ 588,
      jung: (code % 588) ~/ 28,
      jong: code % 28,
    );
  }

  /// Convert a Hangul syllable codepoint to HID keycodes.
  static List<KeycodePair> syllableToKeycodes(int codepoint) {
    final d = decompose(codepoint);
    final result = <KeycodePair>[];

    // Initial consonant (초성)
    result.addAll(_choKeycodes(d.cho));

    // Medial vowel (중성) - may expand for compound vowels
    result.addAll(_jungKeycodes(d.jung));

    // Final consonant (종성) - 0 = none, may expand for compound finals
    if (d.jong > 0) {
      result.addAll(_jongKeycodes(d.jong));
    }

    return result;
  }

  // --- 초성 (19 initial consonants) → Dubeolsik keycodes ---
  // Index: ㄱ(0) ㄲ(1) ㄴ(2) ㄷ(3) ㄸ(4) ㄹ(5) ㅁ(6) ㅂ(7) ㅃ(8)
  //        ㅅ(9) ㅆ(10) ㅇ(11) ㅈ(12) ㅉ(13) ㅊ(14) ㅋ(15) ㅌ(16) ㅍ(17) ㅎ(18)
  static List<KeycodePair> _choKeycodes(int index) {
    const table = <List<KeycodePair>>[
      [KeycodePair(0x15, 0x00)], // 0: ㄱ → R
      [KeycodePair(0x15, 0x02)], // 1: ㄲ → R+Shift
      [KeycodePair(0x16, 0x00)], // 2: ㄴ → S
      [KeycodePair(0x08, 0x00)], // 3: ㄷ → E
      [KeycodePair(0x08, 0x02)], // 4: ㄸ → E+Shift
      [KeycodePair(0x09, 0x00)], // 5: ㄹ → F
      [KeycodePair(0x04, 0x00)], // 6: ㅁ → A
      [KeycodePair(0x14, 0x00)], // 7: ㅂ → Q
      [KeycodePair(0x14, 0x02)], // 8: ㅃ → Q+Shift
      [KeycodePair(0x17, 0x00)], // 9: ㅅ → T
      [KeycodePair(0x17, 0x02)], // 10: ㅆ → T+Shift
      [KeycodePair(0x07, 0x00)], // 11: ㅇ → D
      [KeycodePair(0x1A, 0x00)], // 12: ㅈ → W
      [KeycodePair(0x1A, 0x02)], // 13: ㅉ → W+Shift
      [KeycodePair(0x06, 0x00)], // 14: ㅊ → C
      [KeycodePair(0x1D, 0x00)], // 15: ㅋ → Z
      [KeycodePair(0x1B, 0x00)], // 16: ㅌ → X
      [KeycodePair(0x19, 0x00)], // 17: ㅍ → V
      [KeycodePair(0x0A, 0x00)], // 18: ㅎ → G
    ];
    return table[index];
  }

  // --- 중성 (21 medial vowels) → Dubeolsik keycodes ---
  // Simple vowels map to 1 key, compound vowels expand to 2 keys.
  // Index: ㅏ(0) ㅐ(1) ㅑ(2) ㅒ(3) ㅓ(4) ㅔ(5) ㅕ(6) ㅖ(7) ㅗ(8)
  //        ㅘ(9) ㅙ(10) ㅚ(11) ㅛ(12) ㅜ(13) ㅝ(14) ㅞ(15) ㅟ(16) ㅠ(17)
  //        ㅡ(18) ㅢ(19) ㅣ(20)
  static List<KeycodePair> _jungKeycodes(int index) {
    const table = <List<KeycodePair>>[
      [KeycodePair(0x0E, 0x00)], // 0: ㅏ → K
      [KeycodePair(0x12, 0x00)], // 1: ㅐ → O
      [KeycodePair(0x0C, 0x00)], // 2: ㅑ → I
      [KeycodePair(0x12, 0x02)], // 3: ㅒ → O+Shift
      [KeycodePair(0x0D, 0x00)], // 4: ㅓ → J
      [KeycodePair(0x13, 0x00)], // 5: ㅔ → P
      [KeycodePair(0x18, 0x00)], // 6: ㅕ → U
      [KeycodePair(0x13, 0x02)], // 7: ㅖ → P+Shift
      [KeycodePair(0x0B, 0x00)], // 8: ㅗ → H
      [KeycodePair(0x0B, 0x00), KeycodePair(0x0E, 0x00)], // 9: ㅘ → H, K
      [KeycodePair(0x0B, 0x00), KeycodePair(0x12, 0x00)], // 10: ㅙ → H, O
      [KeycodePair(0x0B, 0x00), KeycodePair(0x0F, 0x00)], // 11: ㅚ → H, L
      [KeycodePair(0x1C, 0x00)], // 12: ㅛ → Y
      [KeycodePair(0x11, 0x00)], // 13: ㅜ → N
      [KeycodePair(0x11, 0x00), KeycodePair(0x0D, 0x00)], // 14: ㅝ → N, J
      [KeycodePair(0x11, 0x00), KeycodePair(0x13, 0x00)], // 15: ㅞ → N, P
      [KeycodePair(0x11, 0x00), KeycodePair(0x0F, 0x00)], // 16: ㅟ → N, L
      [KeycodePair(0x05, 0x00)], // 17: ㅠ → B
      [KeycodePair(0x10, 0x00)], // 18: ㅡ → M
      [KeycodePair(0x10, 0x00), KeycodePair(0x0F, 0x00)], // 19: ㅢ → M, L
      [KeycodePair(0x0F, 0x00)], // 20: ㅣ → L
    ];
    return table[index];
  }

  // --- 종성 (28 final consonants, 0=none) → Dubeolsik keycodes ---
  // Compound finals (겹받침) expand to 2 keys.
  // Index: (0=none) ㄱ(1) ㄲ(2) ㄳ(3) ㄴ(4) ㄵ(5) ㄶ(6) ㄷ(7) ㄹ(8)
  //        ㄺ(9) ㄻ(10) ㄼ(11) ㄽ(12) ㄾ(13) ㄿ(14) ㅀ(15) ㅁ(16) ㅂ(17)
  //        ㅄ(18) ㅅ(19) ㅆ(20) ㅇ(21) ㅈ(22) ㅊ(23) ㅋ(24) ㅌ(25) ㅍ(26) ㅎ(27)
  static List<KeycodePair> _jongKeycodes(int index) {
    const table = <List<KeycodePair>>[
      [], // 0: none
      [KeycodePair(0x15, 0x00)], // 1: ㄱ → R
      [KeycodePair(0x15, 0x02)], // 2: ㄲ → R+Shift
      [KeycodePair(0x15, 0x00), KeycodePair(0x17, 0x00)], // 3: ㄳ → R, T
      [KeycodePair(0x16, 0x00)], // 4: ㄴ → S
      [KeycodePair(0x16, 0x00), KeycodePair(0x1A, 0x00)], // 5: ㄵ → S, W
      [KeycodePair(0x16, 0x00), KeycodePair(0x0A, 0x00)], // 6: ㄶ → S, G
      [KeycodePair(0x08, 0x00)], // 7: ㄷ → E
      [KeycodePair(0x09, 0x00)], // 8: ㄹ → F
      [KeycodePair(0x09, 0x00), KeycodePair(0x15, 0x00)], // 9: ㄺ → F, R
      [KeycodePair(0x09, 0x00), KeycodePair(0x04, 0x00)], // 10: ㄻ → F, A
      [KeycodePair(0x09, 0x00), KeycodePair(0x14, 0x00)], // 11: ㄼ → F, Q
      [KeycodePair(0x09, 0x00), KeycodePair(0x17, 0x00)], // 12: ㄽ → F, T
      [KeycodePair(0x09, 0x00), KeycodePair(0x1B, 0x00)], // 13: ㄾ → F, X
      [KeycodePair(0x09, 0x00), KeycodePair(0x19, 0x00)], // 14: ㄿ → F, V
      [KeycodePair(0x09, 0x00), KeycodePair(0x0A, 0x00)], // 15: ㅀ → F, G
      [KeycodePair(0x04, 0x00)], // 16: ㅁ → A
      [KeycodePair(0x14, 0x00)], // 17: ㅂ → Q
      [KeycodePair(0x14, 0x00), KeycodePair(0x17, 0x00)], // 18: ㅄ → Q, T
      [KeycodePair(0x17, 0x00)], // 19: ㅅ → T
      [KeycodePair(0x17, 0x02)], // 20: ㅆ → T+Shift
      [KeycodePair(0x07, 0x00)], // 21: ㅇ → D
      [KeycodePair(0x1A, 0x00)], // 22: ㅈ → W
      [KeycodePair(0x06, 0x00)], // 23: ㅊ → C
      [KeycodePair(0x1D, 0x00)], // 24: ㅋ → Z
      [KeycodePair(0x1B, 0x00)], // 25: ㅌ → X
      [KeycodePair(0x19, 0x00)], // 26: ㅍ → V
      [KeycodePair(0x0A, 0x00)], // 27: ㅎ → G
    ];
    return table[index];
  }
}
