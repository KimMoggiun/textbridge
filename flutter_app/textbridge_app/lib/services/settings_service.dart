import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

enum TargetOS { windows, macOS }

enum TypingSpeed {
  safe(10, 'Safe (10ms)'),
  normal(5, 'Normal (5ms)'),
  fast(1, 'Fast (1ms)');

  final int delayMs;
  final String label;
  const TypingSpeed(this.delayMs, this.label);
}

class SettingsService extends ChangeNotifier {
  static const _keyTargetOS = 'targetOS';
  static const _keyTypingSpeed = 'typingSpeed';
  static const _keyLastDeviceAddress = 'lastDeviceAddress';

  TargetOS _targetOS = TargetOS.windows;
  TypingSpeed _typingSpeed = TypingSpeed.normal;
  String? _lastDeviceAddress;

  TargetOS get targetOS => _targetOS;
  TypingSpeed get typingSpeed => _typingSpeed;
  String? get lastDeviceAddress => _lastDeviceAddress;

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();

    final osIndex = prefs.getInt(_keyTargetOS);
    if (osIndex != null && osIndex < TargetOS.values.length) {
      _targetOS = TargetOS.values[osIndex];
    }

    final speedIndex = prefs.getInt(_keyTypingSpeed);
    if (speedIndex != null && speedIndex < TypingSpeed.values.length) {
      _typingSpeed = TypingSpeed.values[speedIndex];
    }

    _lastDeviceAddress = prefs.getString(_keyLastDeviceAddress);
    notifyListeners();
  }

  Future<void> setTargetOS(TargetOS os) async {
    _targetOS = os;
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyTargetOS, os.index);
  }

  Future<void> setTypingSpeed(TypingSpeed speed) async {
    _typingSpeed = speed;
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyTypingSpeed, speed.index);
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
