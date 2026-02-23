# Compressed Mode Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Compressed transmission mode (zlib+hex) to Flutter app alongside existing Direct mode.

**Architecture:** App-only change. Text → UTF-8 → zlib → hex string → existing keycode pipeline → existing BLE protocol. No firmware or protocol changes.

**Tech Stack:** Dart (dart:convert, dart:io ZLibCodec), Flutter (SegmentedButton, Provider), SharedPreferences

**Design doc:** `docs/plans/2026-02-23-compressed-mode-design.md`

---

### Task 1: CompressionService — core logic

**Files:**
- Create: `flutter_app/textbridge_app/lib/services/compression_service.dart`
- Create: `flutter_app/textbridge_app/test/compression_service_test.dart`

**Step 1: Write the failing tests**

```dart
// test/compression_service_test.dart
import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:textbridge_app/services/compression_service.dart';

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

      // Decode hex to bytes
      final bytes = <int>[];
      for (var i = 0; i < hex.length; i += 2) {
        bytes.add(int.parse(hex.substring(i, i + 2), radix: 16));
      }

      // Inflate
      final inflated = ZLibDecoder().convert(bytes);
      final decoded = utf8.decode(inflated);
      expect(decoded, original);
    });

    test('compressToHex with empty string', () {
      final hex = CompressionService.compressToHex('');
      // Empty string still produces zlib output (header + empty + checksum)
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
      expect(info.originalBytes, utf8.encode(text).length); // 15 bytes
      expect(info.compressedBytes, greaterThan(0));
      expect(info.compressedBytes, lessThanOrEqualTo(info.originalBytes));
      expect(info.hexChars, info.compressedBytes * 2);
    });

    test('compressionInfo empty string', () {
      final info = CompressionService.compressionInfo('');
      expect(info.originalBytes, 0);
      expect(info.compressedBytes, greaterThan(0)); // zlib header
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
    });
  });
}
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/evan/project/textbridge/flutter_app/textbridge_app && flutter test test/compression_service_test.dart`
Expected: FAIL — `compression_service.dart` doesn't exist yet

**Step 3: Implement CompressionService**

```dart
// lib/services/compression_service.dart
import 'dart:convert';
import 'dart:io';

class CompressionService {
  /// H.java hex decoder (~350 chars). User sends this to PC once via Direct mode.
  /// Usage: javac H.java (once) → java H data.txt (each time)
  static const String decoderJava =
      'import java.util.zip.*;\n'
      'import java.io.*;\n'
      'import java.nio.file.*;\n'
      'class H{public static void main(String[] a)throws Exception{\n'
      'String s=new String(Files.readAllBytes(Paths.get(a[0]))).trim();\n'
      'byte[]b=new byte[s.length()/2];\n'
      'for(int i=0;i<b.length;i++)b[i]=(byte)Integer.parseInt(s.substring(i*2,i*2+2),16);\n'
      'Inflater i=new Inflater();i.setInput(b);\n'
      'ByteArrayOutputStream o=new ByteArrayOutputStream();\n'
      'byte[]buf=new byte[4096];\n'
      'while(!i.finished()){int n=i.inflate(buf);o.write(buf,0,n);}\n'
      'i.end();\n'
      'Files.write(Paths.get("output.txt"),o.toByteArray());\n'
      'System.out.println("ok "+o.size()+"b");}}';

  /// Compress text to hex string: UTF-8 → zlib → lowercase hex.
  static String compressToHex(String text) {
    final utf8Bytes = utf8.encode(text);
    final compressed = ZLibCodec().encode(utf8Bytes);
    final sb = StringBuffer();
    for (final b in compressed) {
      sb.write(b.toRadixString(16).padLeft(2, '0'));
    }
    return sb.toString();
  }

  /// Get compression size info for UI display.
  static ({int originalBytes, int compressedBytes, int hexChars})
      compressionInfo(String text) {
    final utf8Bytes = utf8.encode(text);
    final compressed = ZLibCodec().encode(utf8Bytes);
    return (
      originalBytes: utf8Bytes.length,
      compressedBytes: compressed.length,
      hexChars: compressed.length * 2,
    );
  }
}
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/evan/project/textbridge/flutter_app/textbridge_app && flutter test test/compression_service_test.dart`
Expected: All 8 tests PASS

**Step 5: Commit**

```bash
cd /Users/evan/project/textbridge && git add flutter_app/textbridge_app/lib/services/compression_service.dart flutter_app/textbridge_app/test/compression_service_test.dart && git commit -m "feat: add CompressionService with zlib+hex encoding"
```

---

### Task 2: SettingsService — TransmissionMode + compressed delays

**Files:**
- Modify: `flutter_app/textbridge_app/lib/services/settings_service.dart`
- Modify: `flutter_app/textbridge_app/test/settings_service_test.dart`

**Step 1: Write the failing tests**

Append to `test/settings_service_test.dart` inside the existing `group('SettingsService', ...)`:

```dart
    test('default transmissionMode is direct', () async {
      final svc = SettingsService();
      await svc.load();
      expect(svc.transmissionMode, TransmissionMode.direct);
    });

    test('setTransmissionMode persists compressed', () async {
      final svc = SettingsService();
      await svc.load();

      await svc.setTransmissionMode(TransmissionMode.compressed);
      expect(svc.transmissionMode, TransmissionMode.compressed);

      final svc2 = SettingsService();
      await svc2.load();
      expect(svc2.transmissionMode, TransmissionMode.compressed);
    });

    test('compressed delay defaults: press=1, release=1, warmup=50', () async {
      final svc = SettingsService();
      await svc.load();
      expect(svc.compressedPressDelay, 1);
      expect(svc.compressedReleaseDelay, 1);
      expect(svc.compressedWarmupDelay, 50);
    });

    test('setCompressedPressDelay persists', () async {
      final svc = SettingsService();
      await svc.load();

      await svc.setCompressedPressDelay(3);
      expect(svc.compressedPressDelay, 3);

      final svc2 = SettingsService();
      await svc2.load();
      expect(svc2.compressedPressDelay, 3);
    });

    test('setCompressedReleaseDelay persists', () async {
      final svc = SettingsService();
      await svc.load();

      await svc.setCompressedReleaseDelay(5);
      expect(svc.compressedReleaseDelay, 5);

      final svc2 = SettingsService();
      await svc2.load();
      expect(svc2.compressedReleaseDelay, 5);
    });

    test('setCompressedWarmupDelay persists', () async {
      final svc = SettingsService();
      await svc.load();

      await svc.setCompressedWarmupDelay(30);
      expect(svc.compressedWarmupDelay, 30);

      final svc2 = SettingsService();
      await svc2.load();
      expect(svc2.compressedWarmupDelay, 30);
    });

    test('compressed delays are clamped to 1-255', () async {
      final svc = SettingsService();
      await svc.load();

      await svc.setCompressedPressDelay(0);
      expect(svc.compressedPressDelay, 1);

      await svc.setCompressedReleaseDelay(300);
      expect(svc.compressedReleaseDelay, 255);

      await svc.setCompressedWarmupDelay(-1);
      expect(svc.compressedWarmupDelay, 1);
    });
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/evan/project/textbridge/flutter_app/textbridge_app && flutter test test/settings_service_test.dart`
Expected: FAIL — `TransmissionMode` and compressed delay fields don't exist

**Step 3: Implement settings changes**

Add to `settings_service.dart`:

1. Add `TransmissionMode` enum before `SettingsService` class:

```dart
enum TransmissionMode { direct, compressed }
```

2. Add pref keys (after existing `_keyWarmupDelay`):

```dart
  static const _keyTransmissionMode = 'transmissionMode';
  static const _keyCompressedPressDelay = 'compressedPressDelay';
  static const _keyCompressedReleaseDelay = 'compressedReleaseDelay';
  static const _keyCompressedWarmupDelay = 'compressedWarmupDelay';
```

3. Add fields (after `_warmupDelay`):

```dart
  TransmissionMode _transmissionMode = TransmissionMode.direct;
  int _compressedPressDelay = 1;
  int _compressedReleaseDelay = 1;
  int _compressedWarmupDelay = 50;
```

4. Add getters (after `warmupDelay` getter):

```dart
  TransmissionMode get transmissionMode => _transmissionMode;
  int get compressedPressDelay => _compressedPressDelay;
  int get compressedReleaseDelay => _compressedReleaseDelay;
  int get compressedWarmupDelay => _compressedWarmupDelay;
```

5. Add to `load()` method (after `_warmupDelay` load):

```dart
    final modeIndex = prefs.getInt(_keyTransmissionMode);
    if (modeIndex != null && modeIndex < TransmissionMode.values.length) {
      _transmissionMode = TransmissionMode.values[modeIndex];
    }
    _compressedPressDelay = prefs.getInt(_keyCompressedPressDelay) ?? 1;
    _compressedReleaseDelay = prefs.getInt(_keyCompressedReleaseDelay) ?? 1;
    _compressedWarmupDelay = prefs.getInt(_keyCompressedWarmupDelay) ?? 50;
```

6. Add setters (after `setWarmupDelay`):

```dart
  Future<void> setTransmissionMode(TransmissionMode mode) async {
    _transmissionMode = mode;
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyTransmissionMode, mode.index);
  }

  Future<void> setCompressedPressDelay(int ms) async {
    _compressedPressDelay = ms.clamp(1, 255);
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyCompressedPressDelay, _compressedPressDelay);
  }

  Future<void> setCompressedReleaseDelay(int ms) async {
    _compressedReleaseDelay = ms.clamp(1, 255);
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyCompressedReleaseDelay, _compressedReleaseDelay);
  }

  Future<void> setCompressedWarmupDelay(int ms) async {
    _compressedWarmupDelay = ms.clamp(1, 255);
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyCompressedWarmupDelay, _compressedWarmupDelay);
  }
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/evan/project/textbridge/flutter_app/textbridge_app && flutter test test/settings_service_test.dart`
Expected: All tests PASS (existing 11 + new 7 = 18)

**Step 5: Commit**

```bash
cd /Users/evan/project/textbridge && git add flutter_app/textbridge_app/lib/services/settings_service.dart flutter_app/textbridge_app/test/settings_service_test.dart && git commit -m "feat: add TransmissionMode and compressed delay settings"
```

---

### Task 3: TransmissionService — mode branching

**Files:**
- Modify: `flutter_app/textbridge_app/lib/services/transmission_service.dart`

**Step 1: Add import and mode branching**

Add import at top of `transmission_service.dart`:

```dart
import '../services/compression_service.dart';
```

Replace the keycode conversion block in `sendText()` (lines 69-78) with mode-aware logic:

```dart
    // Convert text based on transmission mode
    final mode = _settings?.transmissionMode ?? TransmissionMode.direct;
    final String textToSend;
    if (mode == TransmissionMode.compressed) {
      textToSend = CompressionService.compressToHex(text);
    } else {
      textToSend = text;
    }

    final result = textToKeycodes(
      textToSend,
      targetOS: _settings?.targetOS ?? TargetOS.windows,
    );
    final keycodes = result.keycodes;
    if (keycodes.isEmpty) {
      _lastError = 'No mappable characters';
      notifyListeners();
      return false;
    }
```

Replace the SET_DELAY block (lines 109-120) to use compressed delays when in compressed mode:

```dart
      if (_settings != null) {
        final mode = _settings!.transmissionMode;
        await _ble.write(makeSetDelay(
          pressDelay: mode == TransmissionMode.compressed
              ? _settings!.compressedPressDelay
              : _settings!.pressDelay,
          releaseDelay: mode == TransmissionMode.compressed
              ? _settings!.compressedReleaseDelay
              : _settings!.releaseDelay,
          comboDelay: _settings!.comboDelay,
          togglePress: _settings!.togglePress,
          toggleDelay: _settings!.toggleDelay,
          warmupDelay: mode == TransmissionMode.compressed
              ? _settings!.compressedWarmupDelay
              : _settings!.warmupDelay,
        ));
        final delayResp = await _dequeue(responseQueue, () => responseWaiter, (c) => responseWaiter = c, const Duration(seconds: 2));
        debugPrint('[TB] SET_DELAY resp: ${delayResp != null ? delayResp.map((b) => "0x${b.toRadixString(16)}").toList() : "TIMEOUT"}');
      }
```

Also update the dynamic ACK timeout calculation (around line 146-159) to use compressed delays:

```dart
        final mode = _settings?.transmissionMode ?? TransmissionMode.direct;
        final pressMs = mode == TransmissionMode.compressed
            ? (_settings?.compressedPressDelay ?? 1)
            : (_settings?.pressDelay ?? 5);
        final releaseMs = mode == TransmissionMode.compressed
            ? (_settings?.compressedReleaseDelay ?? 1)
            : (_settings?.releaseDelay ?? 5);
        final comboMs = _settings?.comboDelay ?? 2;
        final togglePressMs = _settings?.togglePress ?? 20;
        final toggleDelayMs = _settings?.toggleDelay ?? 100;
        final warmupMs = (i == 0)
            ? (mode == TransmissionMode.compressed
                ? (_settings?.compressedWarmupDelay ?? 50)
                : (_settings?.warmupDelay ?? 50))
            : 0;
```

**Step 2: Run all existing tests to verify nothing broke**

Run: `cd /Users/evan/project/textbridge/flutter_app/textbridge_app && flutter test`
Expected: All 77+ tests PASS

**Step 3: Commit**

```bash
cd /Users/evan/project/textbridge && git add flutter_app/textbridge_app/lib/services/transmission_service.dart && git commit -m "feat: add compressed mode branching in TransmissionService"
```

---

### Task 4: HomeScreen UI — mode toggle, decoder button, compressed char count

**Files:**
- Modify: `flutter_app/textbridge_app/lib/screens/home_screen.dart`

**Step 1: Add imports**

Add at top:

```dart
import '../services/compression_service.dart';
```

**Step 2: Add decoder button in AppBar**

In AppBar `title` Row children (after the paste IconButton, around line 156), add:

```dart
            Consumer<SettingsService>(
              builder: (_, settings, __) =>
                  settings.transmissionMode == TransmissionMode.compressed
                      ? IconButton(
                          icon: const Icon(Icons.code, size: 21),
                          tooltip: 'H.java 디코더 삽입',
                          onPressed: () {
                            _textController.text = CompressionService.decoderJava;
                            _textController.selection = TextSelection.collapsed(
                                offset: CompressionService.decoderJava.length);
                          },
                        )
                      : const SizedBox.shrink(),
            ),
```

**Step 3: Replace `_CharCount` widget**

Replace the `_CharCount` class (lines 431-451) with mode-aware version:

```dart
class _CharCount extends StatelessWidget {
  final String text;
  final TransmissionMode mode;
  const _CharCount({required this.text, required this.mode});

  @override
  Widget build(BuildContext context) {
    final style = Theme.of(context).textTheme.bodySmall;
    if (text.isEmpty) {
      return Text('0자', style: style);
    }

    if (mode == TransmissionMode.compressed) {
      final info = CompressionService.compressionInfo(text);
      final ratio = info.originalBytes > 0
          ? ((1 - info.compressedBytes / info.originalBytes) * 100).round()
          : 0;
      return Text(
        '${text.length}자 → ${info.compressedBytes}B → ${info.hexChars} hex → ${info.hexChars} 키코드 (압축률 $ratio%)',
        style: style,
      );
    }

    final total = text.length;
    final mapped = countMappedChars(text);
    final keycodeCount = textToKeycodes(text).keycodes.length;
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text('$total자 → $keycodeCount 키코드', style: style),
        if (total != mapped)
          Text('${total - mapped}자 건너뜀',
              style: style?.copyWith(color: Colors.orange)),
      ],
    );
  }
}
```

Update the `_CharCount` usage (around line 198) to pass mode:

```dart
            Consumer<SettingsService>(
              builder: (_, settings, __) => ListenableBuilder(
                listenable: _textController,
                builder: (context, _) => _CharCount(
                  text: _textController.text,
                  mode: settings.transmissionMode,
                ),
              ),
            ),
```

**Step 4: Add mode toggle next to send button**

Replace the send/stop button section (lines 224-246) with mode toggle + button row:

```dart
            Consumer2<BleService, TransmissionService>(
              builder: (_, ble, tx, child) {
                if (tx.isTransmitting) {
                  return FilledButton.tonal(
                    onPressed: _abort,
                    child: const Text('중지'),
                  );
                }
                if (!ble.state.isConnected) {
                  return FilledButton(
                    onPressed: _showConnectionSheet,
                    child: const Text('연결하여 전송'),
                  );
                }
                return Row(
                  children: [
                    Consumer<SettingsService>(
                      builder: (_, settings, __) => SegmentedButton<TransmissionMode>(
                        segments: const [
                          ButtonSegment(
                            value: TransmissionMode.direct,
                            label: Text('D', style: TextStyle(fontSize: 12)),
                          ),
                          ButtonSegment(
                            value: TransmissionMode.compressed,
                            label: Text('C', style: TextStyle(fontSize: 12)),
                          ),
                        ],
                        selected: {settings.transmissionMode},
                        onSelectionChanged: (v) => settings.setTransmissionMode(v.first),
                        style: ButtonStyle(
                          visualDensity: VisualDensity.compact,
                          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: ListenableBuilder(
                        listenable: _textController,
                        builder: (context, _) => FilledButton(
                          onPressed: _textController.text.isEmpty ? null : _send,
                          child: const Text('전송'),
                        ),
                      ),
                    ),
                  ],
                );
              },
            ),
```

**Step 5: Run app to verify UI renders**

Run: `cd /Users/evan/project/textbridge/flutter_app/textbridge_app && flutter test`
Expected: All tests PASS (widget_test may need adjustment if it references _CharCount)

**Step 6: Commit**

```bash
cd /Users/evan/project/textbridge && git add flutter_app/textbridge_app/lib/screens/home_screen.dart && git commit -m "feat: add compressed mode UI (toggle, decoder button, compression stats)"
```

---

### Task 5: SettingsScreen — compressed delay sliders

**Files:**
- Modify: `flutter_app/textbridge_app/lib/screens/settings_screen.dart`

**Step 1: Add compressed delay section**

After the existing `키 딜레이` section (after line 106), add a new Consumer section:

```dart
          Consumer<SettingsService>(
            builder: (_, settings, child) => _Section(
              title: '압축 모드 딜레이',
              children: [
                _DelaySlider(
                  label: '키 누름',
                  description: 'hex 문자 press 타이밍',
                  value: settings.compressedPressDelay,
                  min: 1,
                  max: 20,
                  onChanged: (v) => settings.setCompressedPressDelay(v),
                ),
                _DelaySlider(
                  label: '키 해제',
                  description: 'hex 문자 release 타이밍',
                  value: settings.compressedReleaseDelay,
                  min: 1,
                  max: 20,
                  onChanged: (v) => settings.setCompressedReleaseDelay(v),
                ),
                _DelaySlider(
                  label: '워밍업',
                  description: '첫 청크 전 USB 호스트 동기화',
                  value: settings.compressedWarmupDelay,
                  min: 1,
                  max: 100,
                  onChanged: (v) => settings.setCompressedWarmupDelay(v),
                ),
              ],
            ),
          ),
```

**Step 2: Run tests**

Run: `cd /Users/evan/project/textbridge/flutter_app/textbridge_app && flutter test`
Expected: All tests PASS

**Step 3: Commit**

```bash
cd /Users/evan/project/textbridge && git add flutter_app/textbridge_app/lib/screens/settings_screen.dart && git commit -m "feat: add compressed mode delay sliders to settings"
```

---

### Task 6: Run all tests and verify

**Step 1: Run full Dart test suite**

Run: `cd /Users/evan/project/textbridge/flutter_app/textbridge_app && flutter test`
Expected: All tests PASS (77 existing + ~15 new ≈ 92)

**Step 2: Verify test count**

Run: `cd /Users/evan/project/textbridge/flutter_app/textbridge_app && flutter test --reporter expanded 2>&1 | tail -5`
Expected: Shows total test count with 0 failures

**Step 3: Final commit if any fixups needed**

If all green, no action needed.
