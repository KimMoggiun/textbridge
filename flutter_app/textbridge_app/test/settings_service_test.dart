import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:textbridge_app/services/settings_service.dart';
import 'package:textbridge_app/services/settings_service.dart' show TransmissionMode;

void main() {
  group('SettingsService', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    test('defaults: press=1, release=1, combo=2, warmup=50, lastDeviceAddress=null', () async {
      final svc = SettingsService();
      await svc.load();

      expect(svc.pressDelay, 1);
      expect(svc.releaseDelay, 1);
      expect(svc.comboDelay, 2);
      expect(svc.warmupDelay, 50);
      expect(svc.lastDeviceAddress, isNull);
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

      await svc.setWarmupDelay(0);
      expect(svc.warmupDelay, 1); // min 1ms — firmware treats 0 as default 50ms
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

      await svc.setPressDelay(10);
      expect(notified, 1);

      await svc.setReleaseDelay(8);
      expect(notified, 2);

      await svc.setComboDelay(5);
      expect(notified, 3);

      await svc.setWarmupDelay(30);
      expect(notified, 4);

      await svc.setLastDeviceAddress('XX:XX');
      expect(notified, 5);
    });

    test('default transmissionMode is compressed', () async {
      final svc = SettingsService();
      await svc.load();

      expect(svc.transmissionMode, TransmissionMode.compressed);
    });

    test('setTransmissionMode changes value and notifies listeners', () async {
      final svc = SettingsService();
      await svc.load();

      var notified = 0;
      svc.addListener(() => notified++);

      await svc.setTransmissionMode(TransmissionMode.direct);
      expect(svc.transmissionMode, TransmissionMode.direct);
      expect(notified, 1);

      await svc.setTransmissionMode(TransmissionMode.compressed);
      expect(svc.transmissionMode, TransmissionMode.compressed);
      expect(notified, 2);
    });

    test('setTransmissionMode persists and round-trip works', () async {
      final svc = SettingsService();
      await svc.load();

      await svc.setTransmissionMode(TransmissionMode.direct);
      expect(svc.transmissionMode, TransmissionMode.direct);

      final svc2 = SettingsService();
      await svc2.load();
      expect(svc2.transmissionMode, TransmissionMode.direct);
    });
  });
}
