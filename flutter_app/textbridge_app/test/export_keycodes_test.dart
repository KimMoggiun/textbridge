import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:textbridge_app/models/protocol.dart';
import 'package:textbridge_app/services/keycode_service.dart';

/// Dart 앱의 키코드 변환 결과를 JSON으로 익스포트.
/// Python 브릿지 테스트(test_app_bridge.py)가 이 JSON을 읽어
/// 실제 BLE 전송 → HID 주입을 검증한다.
void main() {
  test('export keycodes to JSON for bridge test', () {
    final cases = <String, dynamic>{};

    // 테스트 케이스 정의: ASCII only (compression mode handles non-ASCII)
    final inputs = [
      ('ascii_hello', 'hello world'),
      ('ascii_special', 'Hello, World! 123'),
      ('ascii_code', 'print("test");'),
      ('hex_sample', '789c4bcacc4b07000336011b'),
    ];

    for (final (name, text) in inputs) {
      final result = textToKeycodes(text);
      final chunkSize = 8;
      final chunks = chunkKeycodes(result.keycodes, chunkSize);

      final keycodeList = result.keycodes
          .map((kp) => [kp.keycode, kp.modifier])
          .toList();

      final protocolPackets = <Map<String, dynamic>>[];

      // START
      protocolPackets.add({
        'type': 'START',
        'bytes': makeStart(0, chunks.length),
      });

      // KEYCODE chunks
      for (final chunk in chunks) {
        protocolPackets.add({
          'type': 'KEYCODE',
          'seq': chunk.seq,
          'count': chunk.pairs.length,
          'bytes': chunk.toBytes(),
        });
      }

      // DONE
      final doneSeq = (chunks.length + 1) % 256;
      protocolPackets.add({
        'type': 'DONE',
        'bytes': makeDone(doneSeq),
      });

      cases[name] = {
        'text': text,
        'keycode_count': result.keycodes.length,
        'skipped_count': result.skippedCount,
        'chunk_count': chunks.length,
        'chunk_size': chunkSize,
        'keycodes': keycodeList,
        'packets': protocolPackets,
      };
    }

    // JSON 파일로 저장
    final outputPath = '${Directory.current.path}/../../tools/dart_keycodes.json';
    final file = File(outputPath);
    file.writeAsStringSync(
      const JsonEncoder.withIndent('  ').convert(cases),
    );

    print('Exported ${cases.length} test cases to $outputPath');

    // 기본 검증: 모든 케이스가 키코드를 생성했는지
    for (final entry in cases.entries) {
      final data = entry.value as Map<String, dynamic>;
      expect(data['keycode_count'] as int, greaterThan(0),
          reason: '${entry.key} should produce keycodes');
      expect(data['skipped_count'] as int, 0,
          reason: '${entry.key} should not skip characters');
    }
  });
}
