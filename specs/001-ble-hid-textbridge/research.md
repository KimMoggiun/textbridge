# Korean Hangul Syllable Decomposition to Dubeolsik Keyboard Reference

## Technical Reference for TextBridge Project

This document provides a comprehensive technical reference for decomposing Korean Hangul syllables into Dubeolsik (두벌식) keyboard keycodes for HID keyboard input conversion.

---

## 1. Unicode Hangul Syllable Decomposition Algorithm

### 1.1 Mathematical Formula

Korean Hangul syllables in the Unicode Hangul Syllables block (U+AC00 to U+D7A3) can be algorithmically decomposed into their constituent jamo (letters).

```
Given a Hangul syllable character with code point char_code:

code = char_code - 0xAC00

초성_index (initial consonant) = code / (21 × 28) = code / 588
중성_index (medial vowel)     = (code % 588) / 28
종성_index (final consonant)  = code % 28
```

### 1.2 Example: Decomposing "왂" (U+C102)

```
char_code = 0xC102
code = 0xC102 - 0xAC00 = 0x1502 = 5378

초성_index = 5378 / 588 = 9  → ㅇ (U+110B)
중성_index = (5378 % 588) / 28 = 146 / 28 = 5  → ㅘ (U+1166)
종성_index = 5378 % 28 = 6  → ㄵ (U+11AE)

Result: 왂 = ㅇ + ㅘ + ㄵ
```

### 1.3 Example: Decomposing "안녕하세요"

| Syllable | Code Point | 초성 Index | 중성 Index | 종성 Index | 초성 | 중성 | 종성 |
|----------|-----------|-----------|-----------|-----------|------|------|------|
| 안 | U+C548 | 11 (ㅇ) | 0 (ㅏ) | 4 (ㄴ) | ㅇ | ㅏ | ㄴ |
| 녕 | U+B155 | 2 (ㄴ) | 4 (ㅕ) | 21 (ㅇ) | ㄴ | ㅕ | ㅇ |
| 하 | U+D558 | 18 (ㅎ) | 0 (ㅏ) | 0 (없음) | ㅎ | ㅏ | - |
| 세 | U+C138 | 9 (ㅅ) | 6 (ㅔ) | 0 (없음) | ㅅ | ㅔ | - |
| 요 | U+C694 | 11 (ㅇ) | 13 (ㅛ) | 0 (없음) | ㅇ | ㅛ | - |

---

## 2. Complete Jamo Lists

### 2.1 Initial Consonants (초성) - 19 Characters

| Index | Jamo | Unicode | Name | Romanization |
|-------|------|---------|------|--------------|
| 0 | ㄱ | U+1100 | 기역 | g/k |
| 1 | ㄲ | U+1101 | 쌍기역 | kk |
| 2 | ㄴ | U+1102 | 니은 | n |
| 3 | ㄷ | U+1103 | 디귿 | d/t |
| 4 | ㄸ | U+1104 | 쌍디귿 | tt |
| 5 | ㄹ | U+1105 | 리을 | r/l |
| 6 | ㅁ | U+1106 | 미음 | m |
| 7 | ㅂ | U+1107 | 비읍 | b/p |
| 8 | ㅃ | U+1108 | 쌍비읍 | pp |
| 9 | ㅅ | U+1109 | 시옷 | s |
| 10 | ㅆ | U+110A | 쌍시옷 | ss |
| 11 | ㅇ | U+110B | 이응 | (silent)/ng |
| 12 | ㅈ | U+110C | 지읒 | j |
| 13 | ㅉ | U+110D | 쌍지읒 | jj |
| 14 | ㅊ | U+110E | 치읓 | ch |
| 15 | ㅋ | U+110F | 키읔 | k |
| 16 | ㅌ | U+1110 | 티읕 | t |
| 17 | ㅍ | U+1111 | 피읖 | p |
| 18 | ㅎ | U+1112 | 히읗 | h |

### 2.2 Medial Vowels (중성) - 21 Characters

| Index | Jamo | Unicode | Name | Romanization | Type |
|-------|------|---------|------|--------------|------|
| 0 | ㅏ | U+1161 | 아 | a | Simple |
| 1 | ㅐ | U+1162 | 애 | ae | Simple |
| 2 | ㅑ | U+1163 | 야 | ya | Simple |
| 3 | ㅒ | U+1164 | 얘 | yae | Simple |
| 4 | ㅓ | U+1165 | 어 | eo | Simple |
| 5 | ㅔ | U+1166 | 에 | e | Simple |
| 6 | ㅕ | U+1167 | 여 | yeo | Simple |
| 7 | ㅖ | U+1168 | 예 | ye | Simple |
| 8 | ㅗ | U+1169 | 오 | o | Simple |
| 9 | ㅘ | U+116A | 와 | wa | Compound |
| 10 | ㅙ | U+116B | 왜 | wae | Compound |
| 11 | ㅚ | U+116C | 외 | oe | Compound |
| 12 | ㅛ | U+116D | 요 | yo | Simple |
| 13 | ㅜ | U+116E | 우 | u | Simple |
| 14 | ㅝ | U+116F | 워 | wo | Compound |
| 15 | ㅞ | U+1170 | 웨 | we | Compound |
| 16 | ㅟ | U+1171 | 위 | wi | Compound |
| 17 | ㅠ | U+1172 | 유 | yu | Simple |
| 18 | ㅡ | U+1173 | 으 | eu | Simple |
| 19 | ㅢ | U+1174 | 의 | ui | Compound |
| 20 | ㅣ | U+1175 | 이 | i | Simple |

### 2.3 Final Consonants (종성) - 28 Positions

| Index | Jamo | Unicode | Name | Type | Note |
|-------|------|---------|------|------|------|
| 0 | (없음) | - | - | None | No final consonant |
| 1 | ㄱ | U+11A8 | 기역 | Simple | |
| 2 | ㄲ | U+11A9 | 쌍기역 | Simple | |
| 3 | ㄳ | U+11AA | 기역시옷 | Compound | ㄱ + ㅅ |
| 4 | ㄴ | U+11AB | 니은 | Simple | |
| 5 | ㄵ | U+11AC | 니은지읒 | Compound | ㄴ + ㅈ |
| 6 | ㄶ | U+11AD | 니은히읗 | Compound | ㄴ + ㅎ |
| 7 | ㄷ | U+11AE | 디귿 | Simple | |
| 8 | ㄹ | U+11AF | 리을 | Simple | |
| 9 | ㄺ | U+11B0 | 리을기역 | Compound | ㄹ + ㄱ |
| 10 | ㄻ | U+11B1 | 리을미음 | Compound | ㄹ + ㅁ |
| 11 | ㄼ | U+11B2 | 리을비읍 | Compound | ㄹ + ㅂ |
| 12 | ㄽ | U+11B3 | 리을시옷 | Compound | ㄹ + ㅅ |
| 13 | ㄾ | U+11B4 | 리을티읕 | Compound | ㄹ + ㅌ |
| 14 | ㄿ | U+11B5 | 리을피읖 | Compound | ㄹ + ㅍ |
| 15 | ㅀ | U+11B6 | 리을히읗 | Compound | ㄹ + ㅎ |
| 16 | ㅁ | U+11B7 | 미음 | Simple | |
| 17 | ㅂ | U+11B8 | 비읍 | Simple | |
| 18 | ㅄ | U+11B9 | 비읍시옷 | Compound | ㅂ + ㅅ |
| 19 | ㅅ | U+11BA | 시옷 | Simple | |
| 20 | ㅆ | U+11BB | 쌍시옷 | Simple | |
| 21 | ㅇ | U+11BC | 이응 | Simple | |
| 22 | ㅈ | U+11BD | 지읒 | Simple | |
| 23 | ㅊ | U+11BE | 치읓 | Simple | |
| 24 | ㅋ | U+11BF | 키읔 | Simple | |
| 25 | ㅌ | U+11C0 | 티읕 | Simple | |
| 26 | ㅍ | U+11C1 | 피읖 | Simple | |
| 27 | ㅎ | U+11C2 | 히읗 | Simple | |

---

## 3. Dubeolsik (두벌식) Keyboard Mapping

### 3.1 Consonant Mapping (Left Side of Keyboard)

| Jamo | QWERTY Key | HID Keycode | Position | Shift Required | Notes |
|------|-----------|-------------|----------|----------------|-------|
| ㅂ | Q | 0x14 | Top row | No | 비읍 (b/p) |
| ㅃ | Q | 0x14 | Top row | **Yes** | 쌍비읍 (pp) |
| ㅈ | W | 0x1A | Top row | No | 지읒 (j) |
| ㅉ | W | 0x1A | Top row | **Yes** | 쌍지읒 (jj) |
| ㄷ | E | 0x08 | Top row | No | 디귿 (d/t) |
| ㄸ | E | 0x08 | Top row | **Yes** | 쌍디귿 (tt) |
| ㄱ | R | 0x15 | Top row | No | 기역 (g/k) |
| ㄲ | R | 0x15 | Top row | **Yes** | 쌍기역 (kk) |
| ㅅ | T | 0x17 | Top row | No | 시옷 (s) |
| ㅆ | T | 0x17 | Top row | **Yes** | 쌍시옷 (ss) |
| ㅁ | A | 0x04 | Home row | No | 미음 (m) |
| ㄴ | S | 0x16 | Home row | No | 니은 (n) |
| ㅇ | D | 0x07 | Home row | No | 이응 (silent/ng) |
| ㄹ | F | 0x09 | Home row | No | 리을 (r/l) |
| ㅎ | G | 0x0A | Home row | No | 히읗 (h) |
| ㅋ | Z | 0x1D | Bottom row | No | 키읔 (k) |
| ㅌ | X | 0x1B | Bottom row | No | 티읕 (t) |
| ㅊ | C | 0x06 | Bottom row | No | 치읓 (ch) |
| ㅍ | V | 0x19 | Bottom row | No | 피읖 (p) |

### 3.2 Vowel Mapping (Right Side of Keyboard)

| Jamo | QWERTY Key | HID Keycode | Position | Shift Required | Type |
|------|-----------|-------------|----------|----------------|------|
| ㅛ | Y | 0x1C | Top row | No | Simple |
| ㅕ | U | 0x18 | Top row | No | Simple |
| ㅑ | I | 0x0C | Top row | No | Simple |
| ㅐ | O | 0x12 | Top row | No | Simple |
| ㅔ | P | 0x13 | Top row | No | Simple |
| ㅒ | O | 0x12 | Top row | **Yes** | Simple |
| ㅖ | P | 0x13 | Top row | **Yes** | Simple |
| ㅗ | H | 0x0B | Home row | No | Simple |
| ㅓ | J | 0x0D | Home row | No | Simple |
| ㅏ | K | 0x0E | Home row | No | Simple |
| ㅣ | L | 0x0F | Home row | No | Simple |
| ㅠ | B | 0x05 | Bottom row | No | Simple |
| ㅜ | N | 0x11 | Bottom row | No | Simple |
| ㅡ | M | 0x10 | Bottom row | No | Simple |

**Note:** Compound vowels (ㅘ, ㅙ, ㅚ, ㅝ, ㅞ, ㅟ, ㅢ) are created by typing two simple vowels in sequence (see Section 4).

### 3.3 HID Modifier Keys

| Key | HID Keycode | Usage |
|-----|-------------|-------|
| Left Shift | 0xE1 | For double consonants (쌍자음) and ㅒ, ㅖ |
| Right Shift | 0xE5 | Same as Left Shift |

---

## 4. Compound Vowel (복합모음) Expansion

Compound vowels in Unicode Hangul syllables must be expanded into two keystrokes when typing on a Dubeolsik keyboard.

### 4.1 Compound Vowel Keystroke Expansion Table

| Unicode Jamo | Romanization | Component 1 | Component 2 | Key 1 | HID 1 | Key 2 | HID 2 |
|--------------|--------------|-------------|-------------|-------|-------|-------|-------|
| ㅘ (U+116A) | wa | ㅗ (o) | ㅏ (a) | H | 0x0B | K | 0x0E |
| ㅙ (U+116B) | wae | ㅗ (o) | ㅐ (ae) | H | 0x0B | O | 0x12 |
| ㅚ (U+116C) | oe | ㅗ (o) | ㅣ (i) | H | 0x0B | L | 0x0F |
| ㅝ (U+116F) | wo | ㅜ (u) | ㅓ (eo) | N | 0x11 | J | 0x0D |
| ㅞ (U+1170) | we | ㅜ (u) | ㅔ (e) | N | 0x11 | P | 0x13 |
| ㅟ (U+1171) | wi | ㅜ (u) | ㅣ (i) | N | 0x11 | L | 0x0F |
| ㅢ (U+1174) | ui | ㅡ (eu) | ㅣ (i) | M | 0x10 | L | 0x0F |

### 4.2 Example: Typing "왂" (ㅇ + ㅘ + ㄵ)

Decomposition: 왂 = ㅇ + ㅘ + ㄵ

**Step 1:** Type initial consonant ㅇ
- Key: D, HID: 0x07

**Step 2:** Type compound vowel ㅘ (expanded to ㅗ + ㅏ)
- Key 1: H, HID: 0x0B (ㅗ)
- Key 2: K, HID: 0x0E (ㅏ)

**Step 3:** Type compound final ㄵ (expanded to ㄴ + ㅈ)
- Key 1: S, HID: 0x16 (ㄴ)
- Key 2: W, HID: 0x1A (ㅈ)

**Complete HID sequence:** D (0x07), H (0x0B), K (0x0E), S (0x16), W (0x1A)

---

## 5. Compound Final Consonants (겹받침) Expansion

Compound final consonants (double batchim) must be expanded into two separate consonant keystrokes.

### 5.1 Compound Final Consonant Expansion Table

| Unicode Jamo | 종성 Index | Component 1 | Component 2 | Key 1 | HID 1 | Key 2 | HID 2 |
|--------------|-----------|-------------|-------------|-------|-------|-------|-------|
| ㄳ (U+11AA) | 3 | ㄱ | ㅅ | R | 0x15 | T | 0x17 |
| ㄵ (U+11AC) | 5 | ㄴ | ㅈ | S | 0x16 | W | 0x1A |
| ㄶ (U+11AD) | 6 | ㄴ | ㅎ | S | 0x16 | G | 0x0A |
| ㄺ (U+11B0) | 9 | ㄹ | ㄱ | F | 0x09 | R | 0x15 |
| ㄻ (U+11B1) | 10 | ㄹ | ㅁ | F | 0x09 | A | 0x04 |
| ㄼ (U+11B2) | 11 | ㄹ | ㅂ | F | 0x09 | Q | 0x14 |
| ㄽ (U+11B3) | 12 | ㄹ | ㅅ | F | 0x09 | T | 0x17 |
| ㄾ (U+11B4) | 13 | ㄹ | ㅌ | F | 0x09 | X | 0x1B |
| ㄿ (U+11B5) | 14 | ㄹ | ㅍ | F | 0x09 | V | 0x19 |
| ㅀ (U+11B6) | 15 | ㄹ | ㅎ | F | 0x09 | G | 0x0A |
| ㅄ (U+11B9) | 18 | ㅂ | ㅅ | Q | 0x14 | T | 0x17 |

### 5.2 Example: Typing "값" (ㄱ + ㅏ + ㅄ)

Decomposition: 값 = ㄱ + ㅏ + ㅄ

**Step 1:** Type initial consonant ㄱ
- Key: R, HID: 0x15

**Step 2:** Type vowel ㅏ
- Key: K, HID: 0x0E

**Step 3:** Type compound final ㅄ (expanded to ㅂ + ㅅ)
- Key 1: Q, HID: 0x14 (ㅂ)
- Key 2: T, HID: 0x17 (ㅅ)

**Complete HID sequence:** R (0x15), K (0x0E), Q (0x14), T (0x17)

---

## 6. Han/Eng Toggle Keys by Operating System

Different operating systems use different HID keycodes for toggling between Hangul (Korean) and English input modes.

### 6.1 Toggle Key Mapping

| Operating System | Key Name | HID Keycode | Notes |
|------------------|----------|-------------|-------|
| **Windows** | 한/영 (Han/Eng) | 0x90 | HID Keyboard LANG1 |
| **macOS** | Ctrl+Space | 0x2C (mod=0x01) | Ctrl modifier + Space key. Right GUI (0xE7)는 HID 인젝션 시 작동하지 않음 |
| **Linux** | 한/영 (Han/Eng) | 0x90 | Same as Windows |

### 6.2 Usage Notes

- **Windows & Linux:** The dedicated 한/영 key (LANG1, 0x90) is the standard method. Some users also configure Right Alt or other keys.
- **macOS:** Ctrl+Space (HID keycode 0x2C with Ctrl modifier 0x01)로 한영 전환. Right GUI (0xE7)는 OS-level 키 매핑이 HID 인젝션에 적용되지 않아 작동하지 않음 (2026-02-08 실제 하드웨어 테스트로 확인).
- **Best Practice for TextBridge:** Implement OS detection and use the appropriate toggle key:
  - Windows/Linux: Send 0x90
  - macOS: Send Ctrl+Space (0x2C, modifier 0x01). 전환 후 100ms 딜레이 필요 (TB_TOGGLE_DELAY_MS).

---

## 7. State Machine for Mixed ASCII/Hangul Text

When processing text that contains both ASCII (English) characters and Hangul (Korean) syllables, the system must intelligently insert Han/Eng toggle keys to minimize mode switches.

### 7.1 Text Segmentation Algorithm

```
Input: Mixed text string (e.g., "Hello안녕123world")

1. Scan through the text character by character
2. Classify each character:
   - ASCII (0x0020-0x007E): English mode
   - Hangul Syllable (0xAC00-0xD7A3): Korean mode
   - Hangul Jamo (0x1100-0x11FF): Korean mode
   - Digits/symbols: Context-dependent (usually English mode)

3. Segment the text into contiguous blocks:
   - Segment 1: "Hello" (English)
   - Segment 2: "안녕" (Korean)
   - Segment 3: "123world" (English)

4. Generate toggle sequence:
   - [ENGLISH MODE] → "Hello" → [TOGGLE] → "안녕" → [TOGGLE] → "123world"
```

### 7.2 State Machine Diagram

```
                    ┌─────────────┐
                    │   START     │
                    │ (Eng Mode)  │
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              │                         │
         ASCII Char                Hangul Char
              │                         │
              ▼                         ▼
      ┌───────────────┐         ┌──────────────┐
      │  English Mode │◄───────►│  Korean Mode │
      │               │  Toggle │              │
      └───────────────┘   (한/영) └──────────────┘
              │                         │
          Type ASCII               Type Hangul
           keycodes                 keycodes
```

### 7.3 Toggle Optimization Strategy

**Merge Adjacent Segments of Same Type:**
```
Before optimization:
"Hi" (Eng) → "안녕" (Kor) → "하세요" (Kor) → "!" (Eng)
Toggles: 3

After optimization:
"Hi" (Eng) → "안녕하세요" (Kor, merged) → "!" (Eng)
Toggles: 3 (no change, but fewer segments)
```

**Skip Toggle for Single Characters (Optional):**
- For very short segments (1 character), evaluate if toggling is worth the overhead.
- Example: "Hi안Bye" might be better as "Hi" + [TOGGLE] + "안" + [TOGGLE] + "Bye"
- Or, depending on keyboard behavior, it might auto-reset.

**Initial Mode Detection:**
- Start in English mode by default (most common)
- If the first character is Hangul, send a toggle first

### 7.4 Example: "Hello안녕123world"

**Step 1: Segment**
- Segment A: "Hello" (English)
- Segment B: "안녕" (Korean)
- Segment C: "123world" (English)

**Step 2: Generate HID sequence**

1. **Type "Hello"** (English mode active by default)
   - H: 0x0B, E: 0x08, L: 0x0F, L: 0x0F, O: 0x12

2. **Toggle to Korean**
   - Windows: 0x90
   - macOS: 0xE7

3. **Type "안녕"**
   - 안 (ㅇ + ㅏ + ㄴ): D (0x07), K (0x0E), S (0x16)
   - 녕 (ㄴ + ㅕ + ㅇ): S (0x16), U (0x18), D (0x07)

4. **Toggle to English**
   - Windows: 0x90
   - macOS: 0xE7

5. **Type "123world"**
   - 1: 0x1E, 2: 0x1F, 3: 0x20
   - W: 0x1A, O: 0x12, R: 0x15, L: 0x0F, D: 0x07

### 7.5 Pseudo-code Implementation

```c
typedef enum {
    MODE_ENGLISH,
    MODE_KOREAN
} InputMode;

InputMode current_mode = MODE_ENGLISH;

void process_mixed_text(const char* utf8_text) {
    // 1. Convert UTF-8 to Unicode code points
    uint32_t* codepoints = utf8_to_codepoints(utf8_text);

    // 2. Iterate through codepoints
    for (int i = 0; codepoints[i] != 0; i++) {
        uint32_t cp = codepoints[i];

        if (is_ascii(cp)) {
            // Need English mode
            if (current_mode != MODE_ENGLISH) {
                send_toggle_key();
                current_mode = MODE_ENGLISH;
            }
            send_ascii_keycode(cp);

        } else if (is_hangul_syllable(cp)) {
            // Need Korean mode
            if (current_mode != MODE_KOREAN) {
                send_toggle_key();
                current_mode = MODE_KOREAN;
            }
            send_hangul_syllable(cp);
        }
    }
}

bool is_hangul_syllable(uint32_t cp) {
    return (cp >= 0xAC00 && cp <= 0xD7A3);
}

void send_hangul_syllable(uint32_t cp) {
    // Decompose syllable
    uint32_t code = cp - 0xAC00;
    int cho = code / 588;
    int jung = (code % 588) / 28;
    int jong = code % 28;

    // Send initial consonant
    send_jamo_keycode(CHO, cho);

    // Send medial vowel (may expand to 2 keys if compound)
    send_jamo_keycode(JUNG, jung);

    // Send final consonant if present (may expand to 2 keys if compound)
    if (jong > 0) {
        send_jamo_keycode(JONG, jong);
    }
}
```

---

## 8. Complete Example: "안녕하세요"

### 8.1 Full Decomposition

| Step | Syllable | 초성 | 중성 | 종성 | Key Sequence | HID Sequence |
|------|----------|------|------|------|--------------|--------------|
| 1 | 안 | ㅇ (D) | ㅏ (K) | ㄴ (S) | D, K, S | 0x07, 0x0E, 0x16 |
| 2 | 녕 | ㄴ (S) | ㅕ (U) | ㅇ (D) | S, U, D | 0x16, 0x18, 0x07 |
| 3 | 하 | ㅎ (G) | ㅏ (K) | - | G, K | 0x0A, 0x0E |
| 4 | 세 | ㅅ (T) | ㅔ (P) | - | T, P | 0x17, 0x13 |
| 5 | 요 | ㅇ (D) | ㅛ (Y) | - | D, Y | 0x07, 0x1C |

### 8.2 Complete HID Keystroke Sequence

Assuming the keyboard starts in English mode and needs to switch to Korean:

1. **Toggle to Korean mode** (Windows): 0x90
2. **Type 안**: 0x07, 0x0E, 0x16
3. **Type 녕**: 0x16, 0x18, 0x07
4. **Type 하**: 0x0A, 0x0E
5. **Type 세**: 0x17, 0x13
6. **Type 요**: 0x07, 0x1C

**Full sequence (Windows):**
```
[0x90] [0x07] [0x0E] [0x16] [0x16] [0x18] [0x07] [0x0A] [0x0E] [0x17] [0x13] [0x07] [0x1C]
```

---

## 9. Reference Tables

### 9.1 USB HID Keycode Reference (Letters)

| Key | HID Keycode | Key | HID Keycode | Key | HID Keycode |
|-----|-------------|-----|-------------|-----|-------------|
| A | 0x04 | J | 0x0D | S | 0x16 |
| B | 0x05 | K | 0x0E | T | 0x17 |
| C | 0x06 | L | 0x0F | U | 0x18 |
| D | 0x07 | M | 0x10 | V | 0x19 |
| E | 0x08 | N | 0x11 | W | 0x1A |
| F | 0x09 | O | 0x12 | X | 0x1B |
| G | 0x0A | P | 0x13 | Y | 0x1C |
| H | 0x0B | Q | 0x14 | Z | 0x1D |
| I | 0x0C | R | 0x15 | | |

### 9.2 USB HID Keycode Reference (Numbers)

| Key | HID Keycode | Key | HID Keycode |
|-----|-------------|-----|-------------|
| 1 ! | 0x1E | 6 ^ | 0x23 |
| 2 @ | 0x1F | 7 & | 0x24 |
| 3 # | 0x20 | 8 * | 0x25 |
| 4 $ | 0x21 | 9 ( | 0x26 |
| 5 % | 0x22 | 0 ) | 0x27 |

### 9.3 USB HID Modifier Keys

| Modifier | HID Keycode | Bit Position |
|----------|-------------|--------------|
| Left Ctrl | 0xE0 | Bit 0 |
| Left Shift | 0xE1 | Bit 1 |
| Left Alt | 0xE2 | Bit 2 |
| Left GUI (Win/Cmd) | 0xE3 | Bit 3 |
| Right Ctrl | 0xE4 | Bit 4 |
| Right Shift | 0xE5 | Bit 5 |
| Right Alt | 0xE6 | Bit 6 |
| Right GUI (Win/Cmd) | 0xE7 | Bit 7 |

---

## 10. Implementation Checklist

### 10.1 Core Algorithm
- [ ] Implement Unicode Hangul syllable decomposition (0xAC00 offset calculation)
- [ ] Create lookup tables for 19 초성, 21 중성, 28 종성
- [ ] Map jamo indices to Dubeolsik keyboard positions
- [ ] Map keyboard positions to USB HID keycodes

### 10.2 Compound Character Handling
- [ ] Implement compound vowel expansion (7 cases)
- [ ] Implement compound final consonant expansion (11 cases)
- [ ] Handle double consonants (쌍자음) with Shift modifier

### 10.3 Mixed Text Processing
- [ ] Implement text segmentation (ASCII vs Hangul)
- [ ] Implement state machine for mode tracking
- [ ] Optimize toggle key insertion
- [ ] OS detection for appropriate toggle key (0x90 vs 0xE7)

### 10.4 Testing
- [ ] Test with simple syllables (e.g., "가", "나")
- [ ] Test with compound vowels (e.g., "왕", "웨")
- [ ] Test with compound finals (e.g., "값", "앉")
- [ ] Test with mixed text (e.g., "Hello안녕")
- [ ] Test with full sentences (e.g., "안녕하세요")
- [ ] Test with all 11,172 possible syllables (stress test)

### 10.5 Edge Cases
- [ ] Handle invalid Unicode code points
- [ ] Handle empty strings
- [ ] Handle ASCII-only text (no Korean)
- [ ] Handle Korean-only text (no ASCII)
- [ ] Handle special characters and punctuation
- [ ] Handle numbers in mixed text

---

## 11. Sources and References

### Academic and Technical Documentation
- [Hangul Syllables - Wikipedia](https://en.wikipedia.org/wiki/Hangul_Syllables)
- [Hangul Jamo (Unicode block) - Wikipedia](https://en.wikipedia.org/wiki/Hangul_Jamo_(Unicode_block))
- [Unicode Hangul Decomposition Technical Note](https://www.unicode.org/L2/L2006/06310-hangul-decompose9.pdf)
- [Generating Hangul Syllables - Unifoundry](https://unifoundry.com/hangul/hangul-generation.html)
- [List of Hangul jamo - Wikipedia](https://en.wikipedia.org/wiki/List_of_Hangul_jamo)
- [Hangul consonant and vowel tables - Wikipedia](https://en.wikipedia.org/wiki/Hangul_consonant_and_vowel_tables)

### Dubeolsik Keyboard Layout
- [Korean Keyboard - Complete Guide - 90 Day Korean](https://www.90daykorean.com/korean-keyboard/)
- [Korean Input Methods - Captain Alan](https://captainalan.github.io/language-and-linguistics/languages/korean/input.html)
- [Korean language and computers - Wikipedia](https://en.wikipedia.org/wiki/Korean_language_and_computers)
- [Learn to Type Korean By Dubeolsik Keyboard - SayJack](https://www.sayjack.com/korean/korean-hangul/type-by-dubeolsik/)
- [Hangul Keyboard layout - Nathan W. Kester](http://www.ke5ter.com/archives/2008/02/26/hangul-keyboard-layout)
- [GitHub - HDKU: Hangul Dubeolsik Keystroke Utils](https://github.com/haven-jeon/HDKU)

### USB HID Keycodes
- [USB HID Keyboard scan codes - GitHub Gist](https://gist.github.com/MightyPork/6da26e382a7ad91b5496ee55fdc73db2)
- [HID keyboard key codes - Microchip Documentation](https://onlinedocs.microchip.com/oxy/GUID-49CD424A-D8EB-4F60-95E5-12E07036AA34-en-US-4/GUID-70C4159D-8412-4C45-A6F8-9824A327EF6E.html)
- [USB HID usage table - FreeBSD Diary](http://www.freebsddiary.org/APC/usb_hid_usages.php)
- [USB Human Interface Devices - OSDev Wiki](https://wiki.osdev.org/USB_Human_Interface_Devices)

### Korean Language Input
- [Batchim (받침) - Korean Final Consonants - 90 Day Korean](https://www.90daykorean.com/batchim/)
- [How to Read Double Final Consonants in Korean](https://www.mykoreanlesson.com/post/double-final-consonants-in-korean)
- [Korean IME - Microsoft Learn](https://learn.microsoft.com/en-us/globalization/input/korean-ime)
- [Korean (Hangul) Input Method User Guide for Mac - Apple Support](https://support.apple.com/guide/korean-input-method/welcome/mac)

---

## Document Metadata

- **Version:** 1.0
- **Date:** 2026-02-08
- **Author:** Technical Research for TextBridge Project
- **Purpose:** Reference document for implementing Korean Hangul to Dubeolsik HID keyboard conversion
- **Unicode Version:** Based on Unicode Standard (Hangul Syllables block U+AC00–U+D7A3)
- **Keyboard Standard:** KS X 5002 (Dubeolsik/두벌식)
