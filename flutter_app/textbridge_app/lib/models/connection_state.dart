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
        return '연결 안됨';
      case TbConnectionState.scanning:
        return '검색 중...';
      case TbConnectionState.connecting:
        return '연결 중...';
      case TbConnectionState.connected:
        return '연결됨';
      case TbConnectionState.transmitting:
        return '전송 중...';
    }
  }

  bool get isConnected =>
      this == TbConnectionState.connected ||
      this == TbConnectionState.transmitting;
}
