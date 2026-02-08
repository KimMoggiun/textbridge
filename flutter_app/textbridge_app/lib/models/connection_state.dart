/// BLE connection lifecycle states.
enum TbConnectionState {
  disconnected,
  scanning,
  connecting,
  connected,
  transmitting,
}

extension TbConnectionStateExt on TbConnectionState {
  String get label {
    switch (this) {
      case TbConnectionState.disconnected:
        return 'Disconnected';
      case TbConnectionState.scanning:
        return 'Scanning...';
      case TbConnectionState.connecting:
        return 'Connecting...';
      case TbConnectionState.connected:
        return 'Connected';
      case TbConnectionState.transmitting:
        return 'Transmitting...';
    }
  }

  bool get isConnected =>
      this == TbConnectionState.connected ||
      this == TbConnectionState.transmitting;
}
