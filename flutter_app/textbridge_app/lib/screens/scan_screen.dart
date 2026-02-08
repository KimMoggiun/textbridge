import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:provider/provider.dart';

import '../models/connection_state.dart';
import '../services/ble_service.dart';
import 'home_screen.dart';

class ScanScreen extends StatefulWidget {
  const ScanScreen({super.key});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  List<ScanResult> _results = [];
  bool _scanning = false;
  String? _error;

  Future<void> _onScanPressed() async {
    // Check permissions first
    try {
      final adapterState = await FlutterBluePlus.adapterState.first;
      if (adapterState != BluetoothAdapterState.on) {
        if (mounted) {
          setState(() => _error = 'Bluetooth is off. Please enable Bluetooth.');
        }
        return;
      }

      if (Platform.isAndroid) {
        final statuses = await [
          Permission.bluetoothScan,
          Permission.bluetoothConnect,
          Permission.location,
        ].request();
        final allGranted = statuses.values.every(
          (s) => s == PermissionStatus.granted,
        );
        if (!allGranted) {
          if (mounted) {
            setState(() => _error = 'Bluetooth permissions required.');
          }
          return;
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() => _error = 'Permission error: $e');
      }
      return;
    }

    // Start scan
    if (!mounted) return;
    setState(() {
      _results = [];
      _scanning = true;
      _error = null;
    });

    try {
      final ble = context.read<BleService>();
      final results = await ble.scan(timeout: 5);
      if (mounted) {
        setState(() {
          _results = results;
          _scanning = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _scanning = false;
          _error = e.toString();
        });
      }
    }
  }

  Future<void> _connectDevice(ScanResult result) async {
    final ble = context.read<BleService>();
    try {
      await ble.connect(result.device);
      if (mounted && ble.state.isConnected) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const HomeScreen()),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Connection failed: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('TextBridge'),
      ),
      body: Column(
        children: [
          if (_scanning)
            const LinearProgressIndicator()
          else
            const SizedBox(height: 4),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Text(_error!, style: const TextStyle(color: Colors.red)),
            ),
          if (!_scanning && _results.isEmpty)
            Expanded(
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.bluetooth_searching, size: 64, color: Colors.grey),
                    const SizedBox(height: 16),
                    const Text('Tap the button below to scan for devices.'),
                    const SizedBox(height: 24),
                    FilledButton.icon(
                      onPressed: _scanning ? null : _onScanPressed,
                      icon: const Icon(Icons.search),
                      label: const Text('Scan for Devices'),
                    ),
                  ],
                ),
              ),
            )
          else if (_scanning)
            const Expanded(
              child: Center(
                child: Text('Scanning for B6 TextBridge...'),
              ),
            )
          else
            Expanded(
              child: Column(
                children: [
                  Padding(
                    padding: const EdgeInsets.all(16),
                    child: Row(
                      children: [
                        Expanded(
                          child: Text(
                            'Tap a device to connect.',
                            style: Theme.of(context).textTheme.bodyLarge,
                          ),
                        ),
                        IconButton(
                          icon: const Icon(Icons.refresh),
                          onPressed: _onScanPressed,
                        ),
                      ],
                    ),
                  ),
                  Expanded(
                    child: Consumer<BleService>(
                      builder: (_, ble, child) {
                        final connecting = ble.state == TbConnectionState.connecting;
                        return ListView.builder(
                          itemCount: _results.length,
                          itemBuilder: (context, index) {
                            final r = _results[index];
                            final name = r.advertisementData.advName;
                            final rssi = r.rssi;
                            return ListTile(
                              leading: Icon(
                                Icons.bluetooth,
                                color: rssi > -60
                                    ? Colors.green
                                    : rssi > -80
                                        ? Colors.orange
                                        : Colors.red,
                              ),
                              title: Text(name.isEmpty ? 'Unknown' : name),
                              subtitle: Text('${r.device.remoteId}  RSSI: $rssi'),
                              trailing: connecting
                                  ? const SizedBox(
                                      width: 24,
                                      height: 24,
                                      child: CircularProgressIndicator(strokeWidth: 2),
                                    )
                                  : const Icon(Icons.chevron_right),
                              onTap: connecting ? null : () => _connectDevice(r),
                            );
                          },
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
