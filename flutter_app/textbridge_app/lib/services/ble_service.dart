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
  int _mtu = 23;

  TbConnectionState _state = TbConnectionState.disconnected;
  TbConnectionState get state => _state;

  int get mtu => _mtu;
  String get deviceName => _device?.platformName ?? '';

  bool _wasTransmitting = false;
  bool get disconnectedDuringTransmission => _wasTransmitting;

  final _responseController = StreamController<Uint8List>.broadcast();
  Stream<Uint8List> get responses => _responseController.stream;

  /// Inject SettingsService for auto-reconnect support.
  void setSettingsService(SettingsService settings) {
    _settings = settings;
  }

  /// Attempt to reconnect to the last known device.
  Future<bool> tryAutoConnect() async {
    final address = _settings?.lastDeviceAddress;
    if (address == null) return false;

    try {
      final device = BluetoothDevice.fromId(address);
      await connect(device);
      return state.isConnected;
    } catch (_) {
      return false;
    }
  }

  /// Update connection state. Used by TransmissionService during send.
  void setState(TbConnectionState s) {
    _state = s;
    notifyListeners();
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
  Future<void> connect(BluetoothDevice device) async {
    setState(TbConnectionState.connecting);
    try {
      await device.connect(autoConnect: false, timeout: const Duration(seconds: 10));
      _device = device;

      // Listen for disconnection
      _connectionSub = device.connectionState.listen((s) {
        if (s == BluetoothConnectionState.disconnected) {
          _wasTransmitting = _state == TbConnectionState.transmitting;
          _cleanup();
          setState(TbConnectionState.disconnected);
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
      setState(TbConnectionState.disconnected);
      rethrow;
    }
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
    setState(TbConnectionState.disconnected);
  }

  void _cleanup() {
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
