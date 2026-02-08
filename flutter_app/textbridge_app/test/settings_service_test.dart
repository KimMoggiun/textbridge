import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:textbridge_app/services/settings_service.dart';

void main() {
  group('SettingsService', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    test('defaults: targetOS=windows, typingSpeed=normal, lastDeviceAddress=null', () async {
      final svc = SettingsService();
      await svc.load();

      expect(svc.targetOS, TargetOS.windows);
      expect(svc.typingSpeed, TypingSpeed.normal);
      expect(svc.lastDeviceAddress, isNull);
    });

    test('setTargetOS persists and reflects value', () async {
      final svc = SettingsService();
      await svc.load();

      await svc.setTargetOS(TargetOS.macOS);
      expect(svc.targetOS, TargetOS.macOS);

      // Reload from prefs
      final svc2 = SettingsService();
      await svc2.load();
      expect(svc2.targetOS, TargetOS.macOS);
    });

    test('setTypingSpeed persists and reflects value', () async {
      final svc = SettingsService();
      await svc.load();

      await svc.setTypingSpeed(TypingSpeed.fast);
      expect(svc.typingSpeed, TypingSpeed.fast);
      expect(svc.typingSpeed.delayMs, 1);

      final svc2 = SettingsService();
      await svc2.load();
      expect(svc2.typingSpeed, TypingSpeed.fast);
    });

    test('setLastDeviceAddress persists and reflects value', () async {
      final svc = SettingsService();
      await svc.load();

      await svc.setLastDeviceAddress('AA:BB:CC:DD:EE:FF');
      expect(svc.lastDeviceAddress, 'AA:BB:CC:DD:EE:FF');

      final svc2 = SettingsService();
      await svc2.load();
      expect(svc2.lastDeviceAddress, 'AA:BB:CC:DD:EE:FF');
    });

    test('setLastDeviceAddress null clears value', () async {
      SharedPreferences.setMockInitialValues({
        'lastDeviceAddress': 'AA:BB:CC',
      });
      final svc = SettingsService();
      await svc.load();
      expect(svc.lastDeviceAddress, 'AA:BB:CC');

      await svc.setLastDeviceAddress(null);
      expect(svc.lastDeviceAddress, isNull);

      final svc2 = SettingsService();
      await svc2.load();
      expect(svc2.lastDeviceAddress, isNull);
    });

    test('TypingSpeed enum values are correct', () {
      expect(TypingSpeed.safe.delayMs, 10);
      expect(TypingSpeed.normal.delayMs, 5);
      expect(TypingSpeed.fast.delayMs, 1);
    });

    test('notifyListeners fires on changes', () async {
      final svc = SettingsService();
      await svc.load();

      var notified = 0;
      svc.addListener(() => notified++);

      await svc.setTargetOS(TargetOS.macOS);
      expect(notified, 1);

      await svc.setTypingSpeed(TypingSpeed.safe);
      expect(notified, 2);

      await svc.setLastDeviceAddress('XX:XX');
      expect(notified, 3);
    });
  });
}
