import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

enum TransmissionMode { direct, compressed }

class SettingsService extends ChangeNotifier {
  static const _keyLastDeviceAddress = 'lastDeviceAddress';
  static const _keyPressDelay = 'compressedPressDelay';
  static const _keyReleaseDelay = 'compressedReleaseDelay';
  static const _keyComboDelay = 'comboDelay';
  static const _keyWarmupDelay = 'compressedWarmupDelay';
  static const _keyTransmissionMode = 'transmissionMode';

  String? _lastDeviceAddress;
  int _pressDelay = 1;
  int _releaseDelay = 1;
  int _comboDelay = 2;
  int _warmupDelay = 50;
  TransmissionMode _transmissionMode = TransmissionMode.compressed;

  String? get lastDeviceAddress => _lastDeviceAddress;
  int get pressDelay => _pressDelay;
  int get releaseDelay => _releaseDelay;
  int get comboDelay => _comboDelay;
  int get warmupDelay => _warmupDelay;
  TransmissionMode get transmissionMode => _transmissionMode;

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();

    _lastDeviceAddress = prefs.getString(_keyLastDeviceAddress);
    _pressDelay = (prefs.getInt(_keyPressDelay) ?? 1).clamp(1, 255);
    _releaseDelay = (prefs.getInt(_keyReleaseDelay) ?? 1).clamp(1, 255);
    _comboDelay = (prefs.getInt(_keyComboDelay) ?? 2).clamp(1, 255);
    _warmupDelay = (prefs.getInt(_keyWarmupDelay) ?? 50).clamp(1, 255);
    final modeStr = prefs.getString(_keyTransmissionMode);
    _transmissionMode = modeStr == 'direct'
        ? TransmissionMode.direct
        : TransmissionMode.compressed;
    notifyListeners();
  }

  Future<void> setPressDelay(int ms) async {
    _pressDelay = ms.clamp(1, 255);
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyPressDelay, _pressDelay);
  }

  Future<void> setReleaseDelay(int ms) async {
    _releaseDelay = ms.clamp(1, 255);
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyReleaseDelay, _releaseDelay);
  }

  Future<void> setComboDelay(int ms) async {
    _comboDelay = ms.clamp(1, 255);
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyComboDelay, _comboDelay);
  }

  Future<void> setWarmupDelay(int ms) async {
    _warmupDelay = ms.clamp(1, 255);
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyWarmupDelay, _warmupDelay);
  }

  Future<void> setTransmissionMode(TransmissionMode mode) async {
    _transmissionMode = mode;
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyTransmissionMode, mode == TransmissionMode.direct ? 'direct' : 'compressed');
  }

  Future<void> setLastDeviceAddress(String? address) async {
    _lastDeviceAddress = address;
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    if (address != null) {
      await prefs.setString(_keyLastDeviceAddress, address);
    } else {
      await prefs.remove(_keyLastDeviceAddress);
    }
  }
}
