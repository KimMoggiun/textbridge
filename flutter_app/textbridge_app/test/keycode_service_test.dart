import 'package:flutter_test/flutter_test.dart';
import 'package:textbridge_app/models/protocol.dart';
import 'package:textbridge_app/services/keycode_service.dart';

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

    test('non-ASCII characters are skipped', () {
      // Hangul, emoji, etc. are all skipped in compression-only mode
      final result = textToKeycodes('a\u{D55C}b');
      expect(result.keycodes.length, 2); // a, b
      expect(result.skippedCount, 1); // 한 skipped
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

    test('hex characters for compression mode', () {
      // Compression mode sends hex: 0-9, a-f
      final result = textToKeycodes('0123456789abcdef');
      expect(result.keycodes.length, 16);
      expect(result.skippedCount, 0);
    });
  });

  group('chunkSizeFromMtu', () {
    test('default MTU 23 gives chunk size 8', () {
      expect(chunkSizeFromMtu(23), 8);
    });

    test('MTU 247 clamped to firmware max 32', () {
      expect(chunkSizeFromMtu(247), 32);
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

    test('no special isolation needed', () {
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

    test('makeSetDelay produces 5 bytes', () {
      final pkt = makeSetDelay(
        pressDelay: 1,
        releaseDelay: 1,
        comboDelay: 2,
        warmupDelay: 50,
      );
      expect(pkt, [cmdSetDelay, 1, 1, 2, 50]);
    });
  });

  group('countMappedChars', () {
    test('all mapped', () {
      expect(countMappedChars('hello'), 5);
    });

    test('Hangul not mapped (compression handles it)', () {
      expect(countMappedChars('h\u{D55C}llo'), 4);
    });

    test('emoji not mapped', () {
      // 'h' + emoji(2 code units) + 'llo' = 6 chars via split(''), 4 mapped
      expect(countMappedChars('h\u{1F600}llo'), 4);
    });
  });
}
