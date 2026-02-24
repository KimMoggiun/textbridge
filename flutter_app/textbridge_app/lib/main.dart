import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'services/ble_service.dart';
import 'services/settings_service.dart';
import 'services/transmission_service.dart';
import 'screens/home_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final settings = SettingsService();
  await settings.load();
  runApp(TextBridgeApp(settings: settings));
}

class TextBridgeApp extends StatelessWidget {
  final SettingsService settings;
  const TextBridgeApp({super.key, required this.settings});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider.value(value: settings),
        ChangeNotifierProvider(create: (_) => BleService()),
        ChangeNotifierProxyProvider<BleService, TransmissionService>(
          create: (ctx) => TransmissionService(
            ctx.read<BleService>(),
            ctx.read<SettingsService>(),
          ),
          update: (ctx, ble, prev) => prev ?? TransmissionService(ble, ctx.read<SettingsService>()),
        ),
      ],
      child: MaterialApp(
        title: '침하하',
        theme: ThemeData(
          colorSchemeSeed: Colors.blue,
          useMaterial3: true,
        ),
        darkTheme: ThemeData(
          colorSchemeSeed: Colors.blue,
          brightness: Brightness.dark,
          useMaterial3: true,
        ),
        home: const HomeScreen(),
      ),
    );
  }
}
