import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:textbridge_app/models/protocol.dart';
import 'package:textbridge_app/services/keycode_service.dart';
import 'package:textbridge_app/services/settings_service.dart';

/// Dart 앱의 키코드 변환 결과를 JSON으로 익스포트.
/// Python 브릿지 테스트(test_app_bridge.py)가 이 JSON을 읽어
/// 실제 BLE 전송 → HID 주입을 검증한다.
void main() {
  test('export keycodes to JSON for bridge test', () {
    const testCases = <String, Map<String, dynamic>>{};
    final cases = <String, dynamic>{};

    // 테스트 케이스 정의: {이름: {text, os}}
    final inputs = [
      ('ascii_hello', 'hello world', TargetOS.windows),
      ('ascii_special', 'Hello, World! 123', TargetOS.windows),
      ('ascii_code', 'print("test");', TargetOS.windows),
      ('hangul_pure_win', '안녕하세요', TargetOS.windows),
      ('hangul_mixed_win', 'Hello 안녕 World 세계', TargetOS.windows),
      ('hangul_complex_win', '까닭없이', TargetOS.windows),
      ('hangul_jamo_win', '자모 닭 까닭없이 값', TargetOS.windows),
      ('hangul_pure_mac', '안녕하세요', TargetOS.macOS),
      ('hangul_mixed_mac', 'Hello 안녕 World 세계', TargetOS.macOS),
      ('hangul_complex_mac', '까닭없이', TargetOS.macOS),
      ('code_with_korean', '// 주석입니다\nvar x = 1;', TargetOS.windows),
      ('mixed_vars', '변수a = 값b', TargetOS.windows),
    ];

    for (final (name, text, os) in inputs) {
      final result = textToKeycodes(text, targetOS: os);
      final chunkSize = 8; // 기본 청크 사이즈 (테스트용)
      final chunks = chunkKeycodes(result.keycodes, chunkSize);

      // 키코드 쌍 리스트
      final keycodeList = result.keycodes
          .map((kp) => [kp.keycode, kp.modifier])
          .toList();

      // 프로토콜 바이트 (실제 BLE로 전송될 raw bytes)
      final protocolPackets = <Map<String, dynamic>>[];

      // START 패킷
      protocolPackets.add({
        'type': 'START',
        'bytes': makeStart(0, chunks.length),
      });

      // KEYCODE 청크 패킷
      for (final chunk in chunks) {
        protocolPackets.add({
          'type': 'KEYCODE',
          'seq': chunk.seq,
          'count': chunk.pairs.length,
          'bytes': chunk.toBytes(),
        });
      }

      // DONE 패킷
      final doneSeq = (chunks.length + 1) % 256;
      protocolPackets.add({
        'type': 'DONE',
        'bytes': makeDone(doneSeq),
      });

      cases[name] = {
        'text': text,
        'os': os == TargetOS.macOS ? 'macOS' : 'Windows',
        'keycode_count': result.keycodes.length,
        'skipped_count': result.skippedCount,
        'ends_in_korean': result.endsInKorean,
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
