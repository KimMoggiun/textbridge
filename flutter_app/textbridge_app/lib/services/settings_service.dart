import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

enum TargetOS { windows, macOS }

class SettingsService extends ChangeNotifier {
  static const _keyTargetOS = 'targetOS';
  static const _keyLastDeviceAddress = 'lastDeviceAddress';
  static const _keyPressDelay = 'pressDelay';
  static const _keyReleaseDelay = 'releaseDelay';
  static const _keyComboDelay = 'comboDelay';
  static const _keyTogglePress = 'togglePress';
  static const _keyToggleDelay = 'toggleDelay';
  static const _keyWarmupDelay = 'warmupDelay';

  /// OS별 권장 한영전환 딜레이 (ms)
  static const defaultToggleDelayWindows = 100;
  static const defaultToggleDelayMacOS = 300;

  static int recommendedToggleDelay(TargetOS os) =>
      os == TargetOS.macOS ? defaultToggleDelayMacOS : defaultToggleDelayWindows;

  TargetOS _targetOS = TargetOS.windows;
  String? _lastDeviceAddress;
  int _pressDelay = 5;
  int _releaseDelay = 5;
  int _comboDelay = 2;
  int _togglePress = 20;
  int _toggleDelay = defaultToggleDelayWindows;
  int _warmupDelay = 50;

  TargetOS get targetOS => _targetOS;
  String? get lastDeviceAddress => _lastDeviceAddress;
  int get pressDelay => _pressDelay;
  int get releaseDelay => _releaseDelay;
  int get comboDelay => _comboDelay;
  int get togglePress => _togglePress;
  int get toggleDelay => _toggleDelay;
  int get warmupDelay => _warmupDelay;

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();

    final osIndex = prefs.getInt(_keyTargetOS);
    if (osIndex != null && osIndex < TargetOS.values.length) {
      _targetOS = TargetOS.values[osIndex];
    }

    _lastDeviceAddress = prefs.getString(_keyLastDeviceAddress);
    _pressDelay = prefs.getInt(_keyPressDelay) ?? 5;
    _releaseDelay = prefs.getInt(_keyReleaseDelay) ?? 5;
    _comboDelay = prefs.getInt(_keyComboDelay) ?? 2;
    _togglePress = prefs.getInt(_keyTogglePress) ?? 20;
    _toggleDelay = prefs.getInt(_keyToggleDelay) ?? recommendedToggleDelay(_targetOS);
    _warmupDelay = prefs.getInt(_keyWarmupDelay) ?? 50;
    notifyListeners();
  }

  Future<void> setTargetOS(TargetOS os) async {
    _targetOS = os;
    _toggleDelay = recommendedToggleDelay(os);
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyTargetOS, os.index);
    await prefs.setInt(_keyToggleDelay, _toggleDelay);
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

  Future<void> setTogglePress(int ms) async {
    _togglePress = ms.clamp(1, 255);
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyTogglePress, _togglePress);
  }

  Future<void> setToggleDelay(int ms) async {
    _toggleDelay = ms.clamp(1, 255);
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyToggleDelay, _toggleDelay);
  }

  Future<void> setWarmupDelay(int ms) async {
    _warmupDelay = ms.clamp(1, 255);
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyWarmupDelay, _warmupDelay);
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
