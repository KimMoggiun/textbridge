import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:textbridge_app/services/compression_service.dart';
import 'package:textbridge_app/services/keycode_service.dart';

void main() {
  group('CompressionService', () {
    test('compressToHex produces valid hex string', () {
      final hex = CompressionService.compressToHex('hello');
      expect(hex, matches(RegExp(r'^[0-9a-f]+$')));
      expect(hex.length % 2, 0);
    });

    test('compressToHex roundtrip: hex → bytes → inflate → original', () {
      const original = '안녕하세요 Hello World 까닭없이';
      final hex = CompressionService.compressToHex(original);
      final bytes = <int>[];
      for (var i = 0; i < hex.length; i += 2) {
        bytes.add(int.parse(hex.substring(i, i + 2), radix: 16));
      }
      final inflated = ZLibDecoder().convert(bytes);
      final decoded = utf8.decode(inflated);
      expect(decoded, original);
    });

    test('compressToHex with empty string', () {
      final hex = CompressionService.compressToHex('');
      expect(hex.isNotEmpty, true);
      expect(hex, matches(RegExp(r'^[0-9a-f]+$')));
    });

    test('compressToHex with ASCII only', () {
      final hex = CompressionService.compressToHex('abcdef0123456789');
      final bytes = <int>[];
      for (var i = 0; i < hex.length; i += 2) {
        bytes.add(int.parse(hex.substring(i, i + 2), radix: 16));
      }
      final inflated = ZLibDecoder().convert(bytes);
      expect(utf8.decode(inflated), 'abcdef0123456789');
    });

    test('compressToHex with Korean only', () {
      const text = '대한민국 프로그래밍';
      final hex = CompressionService.compressToHex(text);
      final bytes = <int>[];
      for (var i = 0; i < hex.length; i += 2) {
        bytes.add(int.parse(hex.substring(i, i + 2), radix: 16));
      }
      final inflated = ZLibDecoder().convert(bytes);
      expect(utf8.decode(inflated), text);
    });

    test('compressionInfo returns correct sizes', () {
      const text = '안녕하세요';
      final info = CompressionService.compressionInfo(text);
      expect(info.originalBytes, utf8.encode(text).length);
      expect(info.compressedBytes, greaterThan(0));
      // Note: short text can EXPAND after zlib (header+checksum overhead)
      expect(info.hexChars, info.compressedBytes * 2);
    });

    test('compressionInfo empty string', () {
      final info = CompressionService.compressionInfo('');
      expect(info.originalBytes, 0);
      expect(info.compressedBytes, greaterThan(0));
      expect(info.hexChars, info.compressedBytes * 2);
    });

    test('compression reduces size for repetitive text', () {
      final repeated = '안녕하세요 ' * 100;
      final info = CompressionService.compressionInfo(repeated);
      expect(info.compressedBytes, lessThan(info.originalBytes ~/ 2));
    });

    test('decoderJava is non-empty and contains H class', () {
      expect(CompressionService.decoderJava.contains('class H'), true);
      expect(CompressionService.decoderJava.contains('Inflater'), true);
      expect(CompressionService.decoderJava.contains('Files.readAllBytes'), true);
      expect(CompressionService.decoderJava.contains('output.txt'), true);
      final open = CompressionService.decoderJava.split('{').length - 1;
      final close = CompressionService.decoderJava.split('}').length - 1;
      expect(open, close);
    });

    test('decoderJava every character is HID-typeable', () {
      final result = textToKeycodes(CompressionService.decoderJava);
      expect(result.skippedCount, 0,
          reason: 'Some characters in H.java have no HID mapping');
      expect(result.keycodes.isNotEmpty, true);
    });

    test('compressToHex never produces uppercase (no Shift needed)', () {
      final inputs = ['hello', '안녕하세요', 'A' * 1000, '😀🇰🇷'];
      for (final input in inputs) {
        final hex = CompressionService.compressToHex(input);
        expect(hex, matches(RegExp(r'^[0-9a-f]+$')),
            reason: 'Input "$input" produced invalid hex');
      }
    });

    test('hex output fed to textToKeycodes has no Shift or toggle keys', () {
      final hex = CompressionService.compressToHex('안녕하세요 Hello World 😀');
      final result = textToKeycodes(hex);
      for (final kp in result.keycodes) {
        expect(kp.modifier, 0x00,
            reason: 'hex keycode 0x${kp.keycode.toRadixString(16)} has modifier');
      }
      expect(result.skippedCount, 0);
    });

    test('compressed pipeline produces fewer keycodes than direct for repetitive Korean', () {
      final repeated = '안녕하세요 ' * 100;
      final directResult = textToKeycodes(repeated);
      final hex = CompressionService.compressToHex(repeated);
      final compressedResult = textToKeycodes(hex);
      expect(compressedResult.keycodes.length,
          lessThan(directResult.keycodes.length));
    });

    test('compressToHex roundtrip with emoji', () {
      const text = 'Hello 😀🇰🇷 안녕';
      final hex = CompressionService.compressToHex(text);
      final bytes = <int>[];
      for (var i = 0; i < hex.length; i += 2) {
        bytes.add(int.parse(hex.substring(i, i + 2), radix: 16));
      }
      final inflated = ZLibDecoder().convert(bytes);
      expect(utf8.decode(inflated), text);
    });

    test('compressToHex handles large text (50KB+)', () {
      final largeText = '안녕하세요 Hello World\n' * 4000;
      final hex = CompressionService.compressToHex(largeText);
      expect(hex, matches(RegExp(r'^[0-9a-f]+$')));
      final bytes = <int>[];
      for (var i = 0; i < hex.length; i += 2) {
        bytes.add(int.parse(hex.substring(i, i + 2), radix: 16));
      }
      final inflated = ZLibDecoder().convert(bytes);
      expect(utf8.decode(inflated), largeText);
    });
  });
}
