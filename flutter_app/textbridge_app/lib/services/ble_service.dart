import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';

import '../models/connection_state.dart';
import '../models/protocol.dart';
import 'settings_service.dart';

/// Low-level BLE operations: scan, connect, disconnect, write, notify.
class BleService extends ChangeNotifier {
  SettingsService? _settings;
  BluetoothDevice? _device;
  BluetoothCharacteristic? _txChar;
  BluetoothCharacteristic? _rxChar;
  StreamSubscription? _connectionSub;
  StreamSubscription? _notifySub;
  Timer? _autoDetectTimer;
  int _mtu = 23;

  TbConnectionState _state = TbConnectionState.disconnected;
  TbConnectionState get state => _state;

  int get mtu => _mtu;
  String get deviceName => _device?.platformName ?? '';
  String? get registeredDeviceId => _settings?.lastDeviceAddress;

  bool _wasTransmitting = false;
  bool get disconnectedDuringTransmission => _wasTransmitting;

  final _responseController = StreamController<Uint8List>.broadcast();
  Stream<Uint8List> get responses => _responseController.stream;

  /// Inject SettingsService for auto-reconnect support.
  void setSettingsService(SettingsService settings) {
    _settings = settings;
  }

  /// Update connection state. Used by TransmissionService during send.
  void setState(TbConnectionState s) {
    _state = s;
    notifyListeners();
  }

  /// Try OS-level auto-connect, then bonded devices, then saved ID.
  /// Falls back to unregistered state if no saved device.
  Future<void> autoConnectOrDiscover() async {
    final savedId = _settings?.lastDeviceAddress;

    // 1. Check if OS already connected a TextBridge device.
    //    This catches: OS auto-reconnected bonded device, app data cleared,
    //    or first launch after OS-level bonding outside the app.
    try {
      final sysDevices = await FlutterBluePlus.systemDevices([Guid(tbServiceUuid)]);
      for (final d in sysDevices) {
        if (savedId == null || d.remoteId.str == savedId) {
          setState(TbConnectionState.connecting);
          await _connectAndDiscover(d, autoConnect: false);
          return;
        }
      }
    } catch (e) {
      debugPrint('[TB-BLE] systemDevices failed: $e');
    }

    if (savedId == null) {
      setState(TbConnectionState.unregistered);
      _startAutoDetect();
      return;
    }

    setState(TbConnectionState.connecting);

    // 2. Android: check bonded devices
    if (Platform.isAndroid) {
      try {
        final bonded = await FlutterBluePlus.bondedDevices;
        for (final d in bonded) {
          if (d.remoteId.str == savedId) {
            await _connectAndDiscover(d, autoConnect: true);
            return;
          }
        }
      } catch (e) {
        debugPrint('[TB-BLE] bondedDevices failed: $e');
      }
    }

    // 3. Connect by saved ID with autoConnect (OS manages connection)
    try {
      final device = BluetoothDevice.fromId(savedId);
      await _connectAndDiscover(device, autoConnect: true);
    } catch (e) {
      debugPrint('[TB-BLE] autoConnect failed: $e');
      setState(TbConnectionState.disconnected);
    }
  }

  /// Scan for TextBridge devices for [timeout] seconds.
  Future<List<ScanResult>> scan({int timeout = 5}) async {
    setState(TbConnectionState.scanning);
    try {
      final results = <ScanResult>[];
      final sub = FlutterBluePlus.onScanResults.listen((batch) {
        for (final r in batch) {
          final name = r.advertisementData.advName;
          final svcUuids = r.advertisementData.serviceUuids
              .map((u) => u.str.toLowerCase())
              .toList();
          if (name == tbDeviceName ||
              svcUuids.contains(tbServiceUuid.toLowerCase())) {
            if (!results.any((e) => e.device.remoteId == r.device.remoteId)) {
              results.add(r);
            }
          }
        }
      });

      await FlutterBluePlus.startScan(
        timeout: Duration(seconds: timeout),
        withServices: [Guid(tbServiceUuid)],
      );
      await Future.delayed(Duration(seconds: timeout + 1));
      sub.cancel();

      if (_state == TbConnectionState.scanning) {
        setState(TbConnectionState.disconnected);
      }
      return results;
    } catch (e) {
      setState(TbConnectionState.disconnected);
      rethrow;
    }
  }

  /// Connect to a specific device and discover TextBridge service.
  Future<void> connect(BluetoothDevice device, {bool autoConnect = false}) async {
    setState(TbConnectionState.connecting);
    await _connectAndDiscover(device, autoConnect: autoConnect);
  }

  Future<void> _connectAndDiscover(BluetoothDevice device, {required bool autoConnect}) async {
    try {
      await device.connect(
        autoConnect: autoConnect,
        timeout: autoConnect ? const Duration(minutes: 10) : const Duration(seconds: 10),
      );
      _device = device;

      // Listen for disconnection
      _connectionSub = device.connectionState.listen((s) {
        if (s == BluetoothConnectionState.disconnected) {
          _wasTransmitting = _state == TbConnectionState.transmitting;
          _cleanup();
          _onDisconnect();
        }
      });

      // Request higher MTU (Android only; iOS negotiates automatically)
      if (Platform.isAndroid) {
        _mtu = await device.requestMtu(247);
      } else {
        _mtu = device.mtuNow;
      }

      // Discover services
      final services = await device.discoverServices();
      BluetoothService? tbService;
      for (final svc in services) {
        if (svc.uuid.str.toLowerCase() == tbServiceUuid.toLowerCase()) {
          tbService = svc;
          break;
        }
      }

      if (tbService == null) {
        await device.disconnect();
        throw Exception('TextBridge service not found');
      }

      // Find TX and RX characteristics
      for (final c in tbService.characteristics) {
        final uuid = c.uuid.str.toLowerCase();
        if (uuid == tbTxUuid.toLowerCase()) {
          _txChar = c;
        } else if (uuid == tbRxUuid.toLowerCase()) {
          _rxChar = c;
        }
      }

      if (_txChar == null || _rxChar == null) {
        await device.disconnect();
        throw Exception('TextBridge characteristics not found');
      }

      // Enable notifications on RX
      await _rxChar!.setNotifyValue(true);
      _notifySub = _rxChar!.onValueReceived.listen((value) {
        debugPrint('[TB-BLE] RX notify: ${value.map((b) => "0x${b.toRadixString(16)}").toList()}');
        _responseController.add(Uint8List.fromList(value));
      });

      setState(TbConnectionState.connected);
      _settings?.setLastDeviceAddress(device.remoteId.str);
    } catch (e) {
      _cleanup();
      // Don't reset to unregistered on connect failure if we have a saved device
      if (_settings?.lastDeviceAddress != null) {
        setState(TbConnectionState.disconnected);
      } else {
        setState(TbConnectionState.unregistered);
      }
      rethrow;
    }
  }

  /// Poll systemDevices while in unregistered state to detect
  /// OS-level auto-connections (e.g. iOS bonded reconnect).
  void _startAutoDetect() {
    _autoDetectTimer?.cancel();
    var retries = 0;
    _autoDetectTimer = Timer.periodic(const Duration(seconds: 2), (_) async {
      retries++;
      if (_state != TbConnectionState.unregistered || retries > 5) {
        _autoDetectTimer?.cancel();
        _autoDetectTimer = null;
        return;
      }
      try {
        final sysDevices = await FlutterBluePlus.systemDevices([Guid(tbServiceUuid)]);
        if (sysDevices.isNotEmpty && _state == TbConnectionState.unregistered) {
          _autoDetectTimer?.cancel();
          _autoDetectTimer = null;
          setState(TbConnectionState.connecting);
          try {
            await _connectAndDiscover(sysDevices.first, autoConnect: false);
          } catch (e) {
            debugPrint('[TB-BLE] auto-detect connect failed: $e');
            setState(TbConnectionState.unregistered);
          }
        }
      } catch (e) {
        debugPrint('[TB-BLE] auto-detect check failed: $e');
      }
    });
  }

  void _onDisconnect() {
    final savedId = _settings?.lastDeviceAddress;
    if (savedId != null) {
      setState(TbConnectionState.reconnecting);
      _attemptReconnect(savedId);
    } else {
      setState(TbConnectionState.unregistered);
    }
  }

  Future<void> _attemptReconnect(String deviceId) async {
    try {
      final device = BluetoothDevice.fromId(deviceId);
      // autoConnect: true — OS가 기기 광고를 감지하면 자동 연결
      await _connectAndDiscover(device, autoConnect: true);
    } catch (e) {
      debugPrint('[TB-BLE] reconnect failed: $e');
      if (_state != TbConnectionState.connected &&
          _state != TbConnectionState.transmitting) {
        setState(TbConnectionState.disconnected);
      }
    }
  }

  /// Unregister the saved device. Clears saved address and disconnects.
  Future<void> unregisterDevice() async {
    await _settings?.setLastDeviceAddress(null);
    await _device?.disconnect();
    _cleanup();
    setState(TbConnectionState.unregistered);
  }

  /// Write data to the TX characteristic (Write Without Response).
  Future<void> write(List<int> data) async {
    if (_txChar == null) throw Exception('Not connected');
    await _txChar!.write(data, withoutResponse: true);
  }

  /// Disconnect from the current device.
  Future<void> disconnect() async {
    await _device?.disconnect();
    _cleanup();
    if (_settings?.lastDeviceAddress != null) {
      setState(TbConnectionState.disconnected);
    } else {
      setState(TbConnectionState.unregistered);
    }
  }

  void _cleanup() {
    _autoDetectTimer?.cancel();
    _autoDetectTimer = null;
    _notifySub?.cancel();
    _notifySub = null;
    _connectionSub?.cancel();
    _connectionSub = null;
    _txChar = null;
    _rxChar = null;
    _device = null;
  }

  @override
  void dispose() {
    _cleanup();
    _responseController.close();
    super.dispose();
  }
}
