import '../models/protocol.dart';
import 'hangul_service.dart';
import 'settings_service.dart';

/// ASCII to HID keycode conversion table.
/// Ported from test_phase3_protocol.py ASCII_TO_HID.
const Map<String, KeycodePair> _asciiToHid = {
  // a-z: 0x04-0x1D, no modifier
  'a': KeycodePair(0x04, 0x00),
  'b': KeycodePair(0x05, 0x00),
  'c': KeycodePair(0x06, 0x00),
  'd': KeycodePair(0x07, 0x00),
  'e': KeycodePair(0x08, 0x00),
  'f': KeycodePair(0x09, 0x00),
  'g': KeycodePair(0x0A, 0x00),
  'h': KeycodePair(0x0B, 0x00),
  'i': KeycodePair(0x0C, 0x00),
  'j': KeycodePair(0x0D, 0x00),
  'k': KeycodePair(0x0E, 0x00),
  'l': KeycodePair(0x0F, 0x00),
  'm': KeycodePair(0x10, 0x00),
  'n': KeycodePair(0x11, 0x00),
  'o': KeycodePair(0x12, 0x00),
  'p': KeycodePair(0x13, 0x00),
  'q': KeycodePair(0x14, 0x00),
  'r': KeycodePair(0x15, 0x00),
  's': KeycodePair(0x16, 0x00),
  't': KeycodePair(0x17, 0x00),
  'u': KeycodePair(0x18, 0x00),
  'v': KeycodePair(0x19, 0x00),
  'w': KeycodePair(0x1A, 0x00),
  'x': KeycodePair(0x1B, 0x00),
  'y': KeycodePair(0x1C, 0x00),
  'z': KeycodePair(0x1D, 0x00),
  // A-Z: 0x04-0x1D, shift modifier
  'A': KeycodePair(0x04, 0x02),
  'B': KeycodePair(0x05, 0x02),
  'C': KeycodePair(0x06, 0x02),
  'D': KeycodePair(0x07, 0x02),
  'E': KeycodePair(0x08, 0x02),
  'F': KeycodePair(0x09, 0x02),
  'G': KeycodePair(0x0A, 0x02),
  'H': KeycodePair(0x0B, 0x02),
  'I': KeycodePair(0x0C, 0x02),
  'J': KeycodePair(0x0D, 0x02),
  'K': KeycodePair(0x0E, 0x02),
  'L': KeycodePair(0x0F, 0x02),
  'M': KeycodePair(0x10, 0x02),
  'N': KeycodePair(0x11, 0x02),
  'O': KeycodePair(0x12, 0x02),
  'P': KeycodePair(0x13, 0x02),
  'Q': KeycodePair(0x14, 0x02),
  'R': KeycodePair(0x15, 0x02),
  'S': KeycodePair(0x16, 0x02),
  'T': KeycodePair(0x17, 0x02),
  'U': KeycodePair(0x18, 0x02),
  'V': KeycodePair(0x19, 0x02),
  'W': KeycodePair(0x1A, 0x02),
  'X': KeycodePair(0x1B, 0x02),
  'Y': KeycodePair(0x1C, 0x02),
  'Z': KeycodePair(0x1D, 0x02),
  // 1-9
  '1': KeycodePair(0x1E, 0x00),
  '2': KeycodePair(0x1F, 0x00),
  '3': KeycodePair(0x20, 0x00),
  '4': KeycodePair(0x21, 0x00),
  '5': KeycodePair(0x22, 0x00),
  '6': KeycodePair(0x23, 0x00),
  '7': KeycodePair(0x24, 0x00),
  '8': KeycodePair(0x25, 0x00),
  '9': KeycodePair(0x26, 0x00),
  '0': KeycodePair(0x27, 0x00),
  // Whitespace
  ' ': KeycodePair(0x2C, 0x00), // Space
  '\n': KeycodePair(0x28, 0x00), // Enter
  '\t': KeycodePair(0x2B, 0x00), // Tab
  // Symbols (unshifted)
  '-': KeycodePair(0x2D, 0x00),
  '=': KeycodePair(0x2E, 0x00),
  '[': KeycodePair(0x2F, 0x00),
  ']': KeycodePair(0x30, 0x00),
  '\\': KeycodePair(0x31, 0x00),
  ';': KeycodePair(0x33, 0x00),
  "'": KeycodePair(0x34, 0x00),
  '`': KeycodePair(0x35, 0x00),
  ',': KeycodePair(0x36, 0x00),
  '.': KeycodePair(0x37, 0x00),
  '/': KeycodePair(0x38, 0x00),
  // Symbols (shifted)
  '!': KeycodePair(0x1E, 0x02),
  '@': KeycodePair(0x1F, 0x02),
  '#': KeycodePair(0x20, 0x02),
  '\$': KeycodePair(0x21, 0x02),
  '%': KeycodePair(0x22, 0x02),
  '^': KeycodePair(0x23, 0x02),
  '&': KeycodePair(0x24, 0x02),
  '*': KeycodePair(0x25, 0x02),
  '(': KeycodePair(0x26, 0x02),
  ')': KeycodePair(0x27, 0x02),
  '_': KeycodePair(0x2D, 0x02),
  '+': KeycodePair(0x2E, 0x02),
  '{': KeycodePair(0x2F, 0x02),
  '}': KeycodePair(0x30, 0x02),
  '|': KeycodePair(0x31, 0x02),
  ':': KeycodePair(0x33, 0x02),
  '"': KeycodePair(0x34, 0x02),
  '~': KeycodePair(0x35, 0x02),
  '<': KeycodePair(0x36, 0x02),
  '>': KeycodePair(0x37, 0x02),
  '?': KeycodePair(0x38, 0x02),
};

/// Han/Eng toggle key by OS.
const KeycodePair _toggleWindows = KeycodePair(0x90, 0x00); // LANG1
const KeycodePair _toggleMacOS = KeycodePair(0x2C, 0x01);   // Ctrl+Space


/// Convert a text string to a list of HID keycode pairs.
/// Handles ASCII, Hangul syllables, and automatic Han/Eng toggle insertion.
/// [targetOS] determines the toggle key used for Han/Eng switching.
/// [startInKorean] indicates the current OS IME state.
/// Returns keycodes, skippedCount, and [endsInKorean] for state tracking.
({List<KeycodePair> keycodes, int skippedCount, bool endsInKorean}) textToKeycodes(
  String text, {
  TargetOS targetOS = TargetOS.windows,
  bool startInKorean = false,
}) {
  final result = <KeycodePair>[];
  var skipped = 0;
  var inKorean = startInKorean;
  final togglePair = targetOS == TargetOS.macOS ? _toggleMacOS : _toggleWindows;

  for (final ch in text.split('')) {
    final cp = ch.codeUnitAt(0);

    if (HangulService.isHangulSyllable(cp)) {
      // Switch to Korean mode if needed
      if (!inKorean) {
        result.add(togglePair);
        inKorean = true;
      }
      result.addAll(HangulService.syllableToKeycodes(cp));
    } else {
      final pair = _asciiToHid[ch];
      if (pair != null) {
        // Switch to English mode if needed
        if (inKorean) {
          result.add(togglePair);
          inKorean = false;
        }
        result.add(pair);
      } else {
        skipped++;
      }
    }
  }

  return (keycodes: result, skippedCount: skipped, endsInKorean: inKorean);
}

/// Calculate chunk size from negotiated MTU.
/// Each keycode pair is 2 bytes. Protocol overhead: 3 bytes (cmd + seq + count).
/// BLE ATT overhead: 3 bytes.
int chunkSizeFromMtu(int mtu) {
  final available = mtu - 3 - 3; // ATT header + protocol header
  final size = available ~/ 2;
  return size.clamp(1, 127); // at least 1, max count fits in uint8
}

/// Check if a keycode pair is a Han/Eng toggle key.
bool _isToggleKey(KeycodePair pair) =>
    pair == _toggleWindows || pair == _toggleMacOS;

/// Split keycodes into chunks with sequence numbers.
/// Toggle keys (Han/Eng switch) are isolated into single-keycode chunks
/// to ensure OS input method switch completes before next keycodes.
/// Sequence starts at 1, wraps at 256.
List<KeycodeChunk> chunkKeycodes(List<KeycodePair> keycodes, int chunkSize) {
  final chunks = <KeycodeChunk>[];
  var i = 0;
  while (i < keycodes.length) {
    if (_isToggleKey(keycodes[i])) {
      final seq = (chunks.length + 1) % 256;
      chunks.add(KeycodeChunk(seq, [keycodes[i]]));
      i++;
    } else {
      final start = i;
      while (i < keycodes.length && i - start < chunkSize && !_isToggleKey(keycodes[i])) {
        i++;
      }
      final seq = (chunks.length + 1) % 256;
      chunks.add(KeycodeChunk(seq, keycodes.sublist(start, i)));
    }
  }
  return chunks;
}

/// Count how many characters in text have valid HID mappings.
int countMappedChars(String text) {
  var count = 0;
  for (final ch in text.split('')) {
    if (_asciiToHid.containsKey(ch) ||
        HangulService.isHangulSyllable(ch.codeUnitAt(0))) {
      count++;
    }
  }
  return count;
}

/// Check if a character has a valid HID mapping.
bool hasMapping(String ch) =>
    _asciiToHid.containsKey(ch) ||
    HangulService.isHangulSyllable(ch.codeUnitAt(0));
