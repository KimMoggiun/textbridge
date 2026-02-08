import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'services/ble_service.dart';
import 'services/settings_service.dart';
import 'services/transmission_service.dart';
import 'screens/home_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const TextBridgeApp());
}

class TextBridgeApp extends StatelessWidget {
  const TextBridgeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => SettingsService()..load()),
        ChangeNotifierProvider(create: (_) => BleService()),
        ChangeNotifierProxyProvider<BleService, TransmissionService>(
          create: (ctx) => TransmissionService(
            ctx.read<BleService>(),
            ctx.read<SettingsService>(),
          ),
          update: (_, ble, prev) => prev ?? TransmissionService(ble),
        ),
      ],
      child: MaterialApp(
        title: 'TextBridge',
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
