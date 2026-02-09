import 'package:flutter_test/flutter_test.dart';
import 'package:textbridge_app/models/protocol.dart';
import 'package:textbridge_app/services/keycode_service.dart';
import 'package:textbridge_app/services/settings_service.dart';

void main() {
  group('textToKeycodes', () {
    test('lowercase letters', () {
      final result = textToKeycodes('abc');
      expect(result.keycodes.length, 3);
      expect(result.skippedCount, 0);
      expect(result.keycodes[0], const KeycodePair(0x04, 0x00)); // a
      expect(result.keycodes[1], const KeycodePair(0x05, 0x00)); // b
      expect(result.keycodes[2], const KeycodePair(0x06, 0x00)); // c
    });

    test('uppercase letters use shift modifier', () {
      final result = textToKeycodes('AB');
      expect(result.keycodes.length, 2);
      expect(result.skippedCount, 0);
      expect(result.keycodes[0], const KeycodePair(0x04, 0x02)); // A
      expect(result.keycodes[1], const KeycodePair(0x05, 0x02)); // B
    });

    test('digits', () {
      final result = textToKeycodes('190');
      expect(result.keycodes.length, 3);
      expect(result.keycodes[0], const KeycodePair(0x1E, 0x00)); // 1
      expect(result.keycodes[1], const KeycodePair(0x26, 0x00)); // 9
      expect(result.keycodes[2], const KeycodePair(0x27, 0x00)); // 0
    });

    test('space and enter', () {
      final result = textToKeycodes(' \n');
      expect(result.keycodes.length, 2);
      expect(result.keycodes[0], const KeycodePair(0x2C, 0x00)); // Space
      expect(result.keycodes[1], const KeycodePair(0x28, 0x00)); // Enter
    });

    test('special characters', () {
      final result = textToKeycodes('!@#');
      expect(result.keycodes.length, 3);
      expect(result.keycodes[0], const KeycodePair(0x1E, 0x02)); // !
      expect(result.keycodes[1], const KeycodePair(0x1F, 0x02)); // @
      expect(result.keycodes[2], const KeycodePair(0x20, 0x02)); // #
    });

    test('mixed hello world', () {
      final result = textToKeycodes('Hello, World!');
      expect(result.keycodes.length, 13);
      expect(result.skippedCount, 0);
      // H = shift + h
      expect(result.keycodes[0], const KeycodePair(0x0B, 0x02));
      // e
      expect(result.keycodes[1], const KeycodePair(0x08, 0x00));
      // space
      expect(result.keycodes[6], const KeycodePair(0x2C, 0x00));
      // !
      expect(result.keycodes[12], const KeycodePair(0x1E, 0x02));
    });

    test('Hangul characters are now mapped (not skipped)', () {
      // 한 (U+D55C) is a Hangul syllable → mapped
      final result = textToKeycodes('a\u{D55C}b');
      // a + toggle + 한(keycodes) + toggle + b
      expect(result.skippedCount, 0);
      expect(result.keycodes.first, const KeycodePair(0x04, 0x00)); // a
    });

    test('emoji characters are skipped', () {
      final result = textToKeycodes('a\u{1F600}b');
      expect(result.keycodes.length, 2); // a, b
      // Emoji is a surrogate pair (2 UTF-16 code units), each skipped
      expect(result.skippedCount, 2);
    });

    test('empty string returns empty list', () {
      final result = textToKeycodes('');
      expect(result.keycodes, isEmpty);
      expect(result.skippedCount, 0);
    });

    test('all printable ASCII symbols', () {
      const symbols = "-=[]\\;'`,./!@#\$%^&*()_+{}|:\"~<>?";
      final result = textToKeycodes(symbols);
      expect(result.keycodes.length, symbols.length);
      expect(result.skippedCount, 0);
    });

    test('tab character', () {
      final result = textToKeycodes('\t');
      expect(result.keycodes.length, 1);
      expect(result.keycodes[0], const KeycodePair(0x2B, 0x00));
    });

    test('only unmapped characters (emoji)', () {
      final result = textToKeycodes('\u{1F600}\u{1F601}');
      expect(result.keycodes, isEmpty);
      // Each emoji is a surrogate pair (2 UTF-16 code units), so 4 skipped
      expect(result.skippedCount, 4);
    });

    test('pure Hangul text produces keycodes with toggle at start only', () {
      // 한글 = two Hangul syllables
      // Expected: toggle(enter Korean) + 한 keycodes + 글 keycodes (no trailing toggle)
      final result = textToKeycodes('\u{D55C}\u{AE00}');
      expect(result.skippedCount, 0);
      expect(result.endsInKorean, true);
      // First: toggle to Korean
      expect(result.keycodes.first, const KeycodePair(0x90, 0x00));
      // Last: 글's final jamo (not a toggle)
      expect(result.keycodes.last, isNot(const KeycodePair(0x90, 0x00)));
    });

    test('mixed English and Hangul with toggle keys (Windows)', () {
      // "a한b" → a + toggle + 한(keycodes) + toggle + b
      final result = textToKeycodes('a\u{D55C}b', targetOS: TargetOS.windows);
      expect(result.skippedCount, 0);
      expect(result.endsInKorean, false);
      // a
      expect(result.keycodes[0], const KeycodePair(0x04, 0x00));
      // toggle to Korean (0x90)
      expect(result.keycodes[1], const KeycodePair(0x90, 0x00));
      // 한 = ㅎ(G:0x0A) + ㅏ(K:0x0E) + ㄴ(S:0x16)
      expect(result.keycodes[2], const KeycodePair(0x0A, 0x00)); // ㅎ
      expect(result.keycodes[3], const KeycodePair(0x0E, 0x00)); // ㅏ
      expect(result.keycodes[4], const KeycodePair(0x16, 0x00)); // ㄴ
      // toggle back to English (0x90)
      expect(result.keycodes[5], const KeycodePair(0x90, 0x00));
      // b
      expect(result.keycodes[6], const KeycodePair(0x05, 0x00));
      expect(result.keycodes.length, 7);
    });

    test('mixed English and Hangul with toggle keys (macOS)', () {
      // "a한b" → a + toggle + 한(keycodes) + toggle + b
      final result = textToKeycodes('a\u{D55C}b', targetOS: TargetOS.macOS);
      expect(result.skippedCount, 0);
      expect(result.endsInKorean, false);
      // a
      expect(result.keycodes[0], const KeycodePair(0x04, 0x00));
      // toggle to Korean (macOS: Ctrl+Space = 0x2C, mod=0x01)
      expect(result.keycodes[1], const KeycodePair(0x2C, 0x01));
      // 한 keycodes
      expect(result.keycodes[2], const KeycodePair(0x0A, 0x00)); // ㅎ
      expect(result.keycodes[3], const KeycodePair(0x0E, 0x00)); // ㅏ
      expect(result.keycodes[4], const KeycodePair(0x16, 0x00)); // ㄴ
      // toggle back to English (macOS: Ctrl+Space)
      expect(result.keycodes[5], const KeycodePair(0x2C, 0x01));
      // b
      expect(result.keycodes[6], const KeycodePair(0x05, 0x00));
    });

    test('contiguous Hangul segments merge (no extra toggles)', () {
      // 안녕 = two Hangul syllables, only 1 toggle pair needed, no trailing toggle
      final result = textToKeycodes('\u{C548}\u{B155}');
      expect(result.skippedCount, 0);
      expect(result.endsInKorean, true);
      // toggle to Korean
      expect(result.keycodes[0], const KeycodePair(0x90, 0x00));
      // 안: D(0x07) K(0x0E) S(0x16)
      expect(result.keycodes[1], const KeycodePair(0x07, 0x00));
      expect(result.keycodes[2], const KeycodePair(0x0E, 0x00));
      expect(result.keycodes[3], const KeycodePair(0x16, 0x00));
      // 녕: S(0x16) U(0x18) D(0x07)
      expect(result.keycodes[4], const KeycodePair(0x16, 0x00));
      expect(result.keycodes[5], const KeycodePair(0x18, 0x00));
      expect(result.keycodes[6], const KeycodePair(0x07, 0x00));
      // no trailing toggle — ends in Korean
      expect(result.keycodes.length, 7);
    });

    test('multiple language switches', () {
      // "Hi안녕ok" → H,i + toggle + 안녕 + toggle + o,k (ends in English)
      final result = textToKeycodes('Hi\u{C548}\u{B155}ok');
      expect(result.skippedCount, 0);
      expect(result.endsInKorean, false);
      // H(shift), i, toggle, 안(3 keys), 녕(3 keys), toggle, o, k
      expect(result.keycodes.length, 12);
      // H
      expect(result.keycodes[0], const KeycodePair(0x0B, 0x02));
      // i
      expect(result.keycodes[1], const KeycodePair(0x0C, 0x00));
      // toggle to Korean
      expect(result.keycodes[2], const KeycodePair(0x90, 0x00));
      // toggle back to English
      expect(result.keycodes[9], const KeycodePair(0x90, 0x00));
      // o
      expect(result.keycodes[10], const KeycodePair(0x12, 0x00));
      // k
      expect(result.keycodes[11], const KeycodePair(0x0E, 0x00));
    });

    test('text ending in Korean has no trailing toggle', () {
      // "a한" → a + toggle + 한 keycodes (no trailing toggle)
      final result = textToKeycodes('a\u{D55C}');
      expect(result.endsInKorean, true);
      // a, toggle, ㅎ, ㅏ, ㄴ = 5 keycodes (no trailing toggle)
      expect(result.keycodes.length, 5);
    });

    test('startInKorean skips initial toggle', () {
      // 한 with startInKorean=true → no toggle, just jamo
      final result = textToKeycodes('\u{D55C}', startInKorean: true);
      expect(result.endsInKorean, true);
      // ㅎ, ㅏ, ㄴ = 3 keycodes (no toggles at all)
      expect(result.keycodes.length, 3);
      expect(result.keycodes[0], const KeycodePair(0x0A, 0x00)); // ㅎ
    });
  });

  group('chunkSizeFromMtu', () {
    test('default MTU 23 gives chunk size 8', () {
      expect(chunkSizeFromMtu(23), 8);
    });

    test('MTU 247 gives chunk size 120', () {
      expect(chunkSizeFromMtu(247), 120);
    });

    test('minimum MTU gives at least 1', () {
      expect(chunkSizeFromMtu(7), 1);
    });
  });

  group('chunkKeycodes', () {
    test('single chunk when keycodes fit', () {
      final keycodes = textToKeycodes('abc').keycodes;
      final chunks = chunkKeycodes(keycodes, 8);
      expect(chunks.length, 1);
      expect(chunks[0].seq, 1);
      expect(chunks[0].pairs.length, 3);
    });

    test('multiple chunks', () {
      final keycodes = textToKeycodes('abcdefghijklmnop').keycodes;
      final chunks = chunkKeycodes(keycodes, 8);
      expect(chunks.length, 2);
      expect(chunks[0].seq, 1);
      expect(chunks[0].pairs.length, 8);
      expect(chunks[1].seq, 2);
      expect(chunks[1].pairs.length, 8);
    });

    test('partial last chunk', () {
      final keycodes = textToKeycodes('abcdefghij').keycodes;
      final chunks = chunkKeycodes(keycodes, 8);
      expect(chunks.length, 2);
      expect(chunks[0].pairs.length, 8);
      expect(chunks[1].pairs.length, 2);
    });

    test('toggle key isolated into single-keycode chunk (Windows)', () {
      // "a한b" → a, toggle(0x90), ㅎ, ㅏ, ㄴ, toggle(0x90), b = 7 keycodes
      final keycodes = textToKeycodes('a\u{D55C}b', targetOS: TargetOS.windows).keycodes;
      final chunks = chunkKeycodes(keycodes, 8);
      // [a], [toggle], [ㅎ,ㅏ,ㄴ], [toggle], [b] = 5 chunks
      expect(chunks.length, 5);
      expect(chunks[0].pairs, [const KeycodePair(0x04, 0x00)]); // a
      expect(chunks[1].pairs, [const KeycodePair(0x90, 0x00)]); // toggle
      expect(chunks[2].pairs.length, 3); // ㅎ,ㅏ,ㄴ
      expect(chunks[3].pairs, [const KeycodePair(0x90, 0x00)]); // toggle
      expect(chunks[4].pairs, [const KeycodePair(0x05, 0x00)]); // b
    });

    test('toggle key isolated into single-keycode chunk (macOS)', () {
      final keycodes = textToKeycodes('a\u{D55C}b', targetOS: TargetOS.macOS).keycodes;
      final chunks = chunkKeycodes(keycodes, 8);
      expect(chunks.length, 5);
      expect(chunks[1].pairs, [const KeycodePair(0x2C, 0x01)]); // Ctrl+Space
      expect(chunks[3].pairs, [const KeycodePair(0x2C, 0x01)]); // Ctrl+Space
    });

    test('pure Hangul: toggle isolated at start', () {
      // "안녕" → toggle, 안(3), 녕(3) = 7 keycodes
      final keycodes = textToKeycodes('\u{C548}\u{B155}').keycodes;
      final chunks = chunkKeycodes(keycodes, 8);
      // [toggle], [안녕 jamo × 6] = 2 chunks
      expect(chunks.length, 2);
      expect(chunks[0].pairs.length, 1); // toggle alone
      expect(chunks[0].pairs[0], const KeycodePair(0x90, 0x00));
      expect(chunks[1].pairs.length, 6); // all jamo
    });

    test('no toggle keys unchanged', () {
      final keycodes = textToKeycodes('abcdefghij').keycodes;
      final chunks = chunkKeycodes(keycodes, 8);
      expect(chunks.length, 2);
      expect(chunks[0].pairs.length, 8);
      expect(chunks[1].pairs.length, 2);
    });

    test('sequence wraps at 256', () {
      final keycodes = List.generate(256, (_) => const KeycodePair(0x04, 0x00));
      final chunks = chunkKeycodes(keycodes, 1);
      expect(chunks.length, 256);
      expect(chunks[0].seq, 1);
      expect(chunks[254].seq, 255);
      expect(chunks[255].seq, 0); // wraps
    });
  });

  group('KeycodeChunk.toBytes', () {
    test('serializes correctly', () {
      final chunk = KeycodeChunk(1, [
        const KeycodePair(0x04, 0x00), // a
        const KeycodePair(0x05, 0x02), // B
      ]);
      final bytes = chunk.toBytes();
      expect(bytes, [cmdKeycode, 1, 2, 0x04, 0x00, 0x05, 0x02]);
    });
  });

  group('protocol packet builders', () {
    test('makeStart', () {
      final pkt = makeStart(0, 5);
      expect(pkt, [cmdStart, 0, 0, 5]);
    });

    test('makeStart with large chunk count', () {
      final pkt = makeStart(0, 300);
      expect(pkt, [cmdStart, 0, 1, 44]); // 300 = 0x012C
    });

    test('makeDone', () {
      expect(makeDone(3), [cmdDone, 3]);
    });

    test('makeAbort', () {
      expect(makeAbort(2), [cmdAbort, 2]);
    });
  });

  group('countMappedChars', () {
    test('all mapped', () {
      expect(countMappedChars('hello'), 5);
    });

    test('Hangul counts as mapped', () {
      expect(countMappedChars('h\u{D55C}llo'), 5);
    });

    test('emoji not mapped', () {
      // 'h' + emoji(2 code units) + 'llo' = 6 chars via split(''), 4 mapped
      expect(countMappedChars('h\u{1F600}llo'), 4);
    });
  });
}
