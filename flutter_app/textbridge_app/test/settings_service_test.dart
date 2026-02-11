import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:textbridge_app/services/settings_service.dart';

void main() {
  group('SettingsService', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    test('defaults: targetOS=windows, delays=5/5/2/20/100/50, lastDeviceAddress=null', () async {
      final svc = SettingsService();
      await svc.load();

      expect(svc.targetOS, TargetOS.windows);
      expect(svc.pressDelay, 5);
      expect(svc.releaseDelay, 5);
      expect(svc.comboDelay, 2);
      expect(svc.togglePress, 20);
      expect(svc.toggleDelay, 100);
      expect(svc.warmupDelay, 50);
      expect(svc.lastDeviceAddress, isNull);
    });

    test('setTargetOS persists and updates toggleDelay to recommended value', () async {
      final svc = SettingsService();
      await svc.load();
      expect(svc.toggleDelay, 100); // Windows default

      await svc.setTargetOS(TargetOS.macOS);
      expect(svc.targetOS, TargetOS.macOS);
      expect(svc.toggleDelay, 300); // macOS recommended

      await svc.setTargetOS(TargetOS.windows);
      expect(svc.toggleDelay, 100); // Windows recommended

      // Reload from prefs
      final svc2 = SettingsService();
      await svc2.load();
      expect(svc2.targetOS, TargetOS.windows);
      expect(svc2.toggleDelay, 100);
    });

    test('macOS default toggleDelay is 300ms', () async {
      SharedPreferences.setMockInitialValues({
        'targetOS': TargetOS.macOS.index,
      });
      final svc = SettingsService();
      await svc.load();

      expect(svc.targetOS, TargetOS.macOS);
      expect(svc.toggleDelay, 300);
    });

    test('setPressDelay persists and reflects value', () async {
      final svc = SettingsService();
      await svc.load();

      await svc.setPressDelay(10);
      expect(svc.pressDelay, 10);

      final svc2 = SettingsService();
      await svc2.load();
      expect(svc2.pressDelay, 10);
    });

    test('setReleaseDelay persists and reflects value', () async {
      final svc = SettingsService();
      await svc.load();

      await svc.setReleaseDelay(8);
      expect(svc.releaseDelay, 8);

      final svc2 = SettingsService();
      await svc2.load();
      expect(svc2.releaseDelay, 8);
    });

    test('setComboDelay persists and reflects value', () async {
      final svc = SettingsService();
      await svc.load();

      await svc.setComboDelay(5);
      expect(svc.comboDelay, 5);

      final svc2 = SettingsService();
      await svc2.load();
      expect(svc2.comboDelay, 5);
    });

    test('setTogglePress persists and reflects value', () async {
      final svc = SettingsService();
      await svc.load();

      await svc.setTogglePress(15);
      expect(svc.togglePress, 15);

      final svc2 = SettingsService();
      await svc2.load();
      expect(svc2.togglePress, 15);
    });

    test('setToggleDelay persists and reflects value', () async {
      final svc = SettingsService();
      await svc.load();

      await svc.setToggleDelay(200);
      expect(svc.toggleDelay, 200);

      final svc2 = SettingsService();
      await svc2.load();
      expect(svc2.toggleDelay, 200);
    });

    test('setWarmupDelay persists and reflects value', () async {
      final svc = SettingsService();
      await svc.load();

      await svc.setWarmupDelay(30);
      expect(svc.warmupDelay, 30);

      final svc2 = SettingsService();
      await svc2.load();
      expect(svc2.warmupDelay, 30);
    });

    test('delay values are clamped to 1-255', () async {
      final svc = SettingsService();
      await svc.load();

      await svc.setPressDelay(0);
      expect(svc.pressDelay, 1);

      await svc.setReleaseDelay(300);
      expect(svc.releaseDelay, 255);

      await svc.setComboDelay(300);
      expect(svc.comboDelay, 255);

      await svc.setTogglePress(-5);
      expect(svc.togglePress, 1);

      await svc.setToggleDelay(-5);
      expect(svc.toggleDelay, 1);

      await svc.setWarmupDelay(0);
      expect(svc.warmupDelay, 1);
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

    test('notifyListeners fires on changes', () async {
      final svc = SettingsService();
      await svc.load();

      var notified = 0;
      svc.addListener(() => notified++);

      await svc.setTargetOS(TargetOS.macOS);
      expect(notified, 1);

      await svc.setPressDelay(10);
      expect(notified, 2);

      await svc.setReleaseDelay(8);
      expect(notified, 3);

      await svc.setComboDelay(5);
      expect(notified, 4);

      await svc.setTogglePress(15);
      expect(notified, 5);

      await svc.setToggleDelay(50);
      expect(notified, 6);

      await svc.setWarmupDelay(30);
      expect(notified, 7);

      await svc.setLastDeviceAddress('XX:XX');
      expect(notified, 8);
    });
  });
}
