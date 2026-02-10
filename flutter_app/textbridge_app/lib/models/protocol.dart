// TextBridge BLE protocol constants and data models.
// Matches Phase 3 firmware protocol exactly.

// BLE Service & Characteristic UUIDs
const String tbServiceUuid = '12340000-1234-1234-1234-123456789abc';
const String tbTxUuid = '12340001-1234-1234-1234-123456789abc';
const String tbRxUuid = '12340002-1234-1234-1234-123456789abc';
const String tbDeviceName = 'B6 TextBridge';

// Commands (phone -> keyboard)
const int cmdKeycode = 0x01;
const int cmdStart = 0x02;
const int cmdDone = 0x03;
const int cmdAbort = 0x04;
const int cmdSetDelay = 0x05;

// Responses (keyboard -> phone)
const int respAck = 0x01;
const int respNack = 0x02;
const int respReady = 0x03;
const int respDone = 0x04;
const int respError = 0x05;

String respName(int code) {
  switch (code) {
    case respAck:
      return 'ACK';
    case respNack:
      return 'NACK';
    case respReady:
      return 'READY';
    case respDone:
      return 'DONE';
    case respError:
      return 'ERROR';
    default:
      return '0x${code.toRadixString(16).padLeft(2, '0')}';
  }
}

/// A single HID keycode + modifier pair.
class KeycodePair {
  final int keycode;
  final int modifier;

  const KeycodePair(this.keycode, this.modifier);

  @override
  bool operator ==(Object other) =>
      other is KeycodePair &&
      other.keycode == keycode &&
      other.modifier == modifier;

  @override
  int get hashCode => keycode.hashCode ^ modifier.hashCode;

  @override
  String toString() =>
      'KC(0x${keycode.toRadixString(16)}, mod=0x${modifier.toRadixString(16)})';
}

/// A chunk of keycode pairs with sequence number.
class KeycodeChunk {
  final int seq;
  final List<KeycodePair> pairs;

  const KeycodeChunk(this.seq, this.pairs);

  /// Serialize to protocol bytes: [CMD_KEYCODE, seq, count, kc1, mod1, kc2, mod2, ...]
  List<int> toBytes() {
    final data = <int>[cmdKeycode, seq, pairs.length];
    for (final p in pairs) {
      data.add(p.keycode);
      data.add(p.modifier);
    }
    return data;
  }
}

/// Build a START packet.
List<int> makeStart(int seq, int totalChunks) {
  return [cmdStart, seq, (totalChunks >> 8) & 0xFF, totalChunks & 0xFF];
}

/// Build a DONE packet.
List<int> makeDone(int seq) {
  return [cmdDone, seq];
}

/// Build an ABORT packet.
List<int> makeAbort(int seq) {
  return [cmdAbort, seq];
}

/// Build a SET_DELAY packet (7 bytes).
/// [pressDelay] ms key press duration, 1-255.
/// [releaseDelay] ms between keys (release → next press), 1-255.
/// [comboDelay] ms within modifier combos (modifier → key), 1-255.
/// [togglePress] ms toggle key press duration, 1-255.
/// [toggleDelay] ms after IME toggle key release, 1-255.
/// [warmupDelay] ms USB host sync before each chunk, 1-255.
List<int> makeSetDelay({
  required int pressDelay,
  required int releaseDelay,
  required int comboDelay,
  required int togglePress,
  required int toggleDelay,
  required int warmupDelay,
}) {
  return [
    cmdSetDelay,
    pressDelay.clamp(1, 255),
    releaseDelay.clamp(1, 255),
    comboDelay.clamp(1, 255),
    togglePress.clamp(1, 255),
    toggleDelay.clamp(1, 255),
    warmupDelay.clamp(1, 255),
  ];
}
