/// BLE connection lifecycle states.
enum TbConnectionState {
  unregistered,
  disconnected,
  scanning,
  connecting,
  reconnecting,
  connected,
  transmitting,
}

extension TbConnectionStateExt on TbConnectionState {
  String get label {
    switch (this) {
      case TbConnectionState.unregistered:
        return '미등록';
      case TbConnectionState.disconnected:
        return '미연결';
      case TbConnectionState.scanning:
        return '검색 중...';
      case TbConnectionState.connecting:
        return '연결 중...';
      case TbConnectionState.reconnecting:
        return '재연결 중...';
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
