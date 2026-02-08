import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:provider/provider.dart';

import '../models/connection_state.dart';
import '../services/ble_service.dart';
import '../services/keycode_service.dart';
import '../services/settings_service.dart';
import '../services/transmission_service.dart';
import 'settings_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _textController = TextEditingController();
  final _focusNode = FocusNode();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _focusNode.requestFocus();
      // Listen for disconnect-during-transmission
      context.read<BleService>().addListener(_onBleStateChanged);
    });
  }

  void _onBleStateChanged() {
    final ble = context.read<BleService>();
    if (ble.state == TbConnectionState.disconnected &&
        ble.disconnectedDuringTransmission) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('연결 끊김으로 전송 중단'),
          backgroundColor: Colors.orange,
        ),
      );
    }
  }

  @override
  void dispose() {
    context.read<BleService>().removeListener(_onBleStateChanged);
    _focusNode.dispose();
    _textController.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final text = _textController.text;
    if (text.isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('전송할 텍스트가 없습니다')),
        );
      }
      return;
    }

    _focusNode.unfocus();
    final tx = context.read<TransmissionService>();
    final ok = await tx.sendText(text);

    if (mounted) {
      if (ok) {
        HapticFeedback.mediumImpact();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Sent successfully!'),
            backgroundColor: Colors.green,
          ),
        );
        _textController.clear();
      } else {
        HapticFeedback.heavyImpact();
        final failPos = tx.failedAtKeycode;
        final msg = failPos != null
            ? 'Failed at keycode $failPos: ${tx.lastError}'
            : 'Failed: ${tx.lastError}';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(msg), backgroundColor: Colors.red),
        );
      }
    }
  }

  void _abort() {
    context.read<TransmissionService>().abort();
  }

  Future<void> _showConnectionSheet() async {
    _focusNode.unfocus();
    final ble = context.read<BleService>();

    // If already connected, show disconnect option
    if (ble.state.isConnected) {
      final disconnect = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text('Connected: ${ble.deviceName}'),
          content: const Text('Disconnect from this device?'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Disconnect')),
          ],
        ),
      );
      if (disconnect == true) {
        await ble.disconnect();
      }
      return;
    }

    // Show scan bottom sheet
    if (!mounted) return;
    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (_) => ChangeNotifierProvider.value(
        value: ble,
        child: const _ScanSheet(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('TextBridge'),
        actions: [
          Consumer<BleService>(
            builder: (_, ble, child) => GestureDetector(
              onTap: _showConnectionSheet,
              child: _ConnectionBadge(state: ble.state),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const SettingsScreen()),
            ),
          ),
        ],
      ),
      resizeToAvoidBottomInset: true,
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Expanded(
              child: TextField(
                controller: _textController,
                focusNode: _focusNode,
                maxLines: null,
                expands: true,
                keyboardType: TextInputType.multiline,
                textAlignVertical: TextAlignVertical.top,
                decoration: const InputDecoration(
                  hintText: 'Type text here to send to keyboard...',
                  border: OutlineInputBorder(),
                ),
              ),
            ),
            const SizedBox(height: 8),
            ListenableBuilder(
              listenable: _textController,
              builder: (context, _) => _CharCount(text: _textController.text),
            ),
            const SizedBox(height: 8),
            // Progress bar
            Consumer2<TransmissionService, SettingsService>(
              builder: (_, tx, settings, child) {
                if (!tx.isTransmitting) return const SizedBox.shrink();
                final remaining = tx.progress.totalKeycodes - tx.progress.sentKeycodes;
                final etaMs = remaining * settings.typingSpeed.delayMs;
                final etaSec = (etaMs / 1000).ceil();
                return Column(
                  children: [
                    LinearProgressIndicator(value: tx.progress.fraction),
                    const SizedBox(height: 4),
                    Text(
                      '${tx.progress.sentChunks}/${tx.progress.totalChunks} chunks  '
                      '(${tx.progress.sentKeycodes}/${tx.progress.totalKeycodes} keys)  '
                      '~${etaSec}s remaining',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    const SizedBox(height: 8),
                  ],
                );
              },
            ),
            // Send / Stop button
            Consumer2<BleService, TransmissionService>(
              builder: (_, ble, tx, child) {
                if (tx.isTransmitting) {
                  return FilledButton.tonal(
                    onPressed: _abort,
                    child: const Text('Stop'),
                  );
                }
                if (!ble.state.isConnected) {
                  return FilledButton(
                    onPressed: _showConnectionSheet,
                    child: const Text('Connect to Send'),
                  );
                }
                return ListenableBuilder(
                  listenable: _textController,
                  builder: (context, _) => FilledButton(
                    onPressed: _textController.text.isEmpty ? null : _send,
                    child: const Text('Send'),
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

// --- Bottom sheet for BLE scanning ---

class _ScanSheet extends StatefulWidget {
  const _ScanSheet();

  @override
  State<_ScanSheet> createState() => _ScanSheetState();
}

class _ScanSheetState extends State<_ScanSheet> {
  List<ScanResult> _results = [];
  bool _scanning = false;
  String? _error;
  bool _showPermissionDenied = false;

  @override
  void initState() {
    super.initState();
    _startScan();
  }

  Future<void> _startScan() async {
    try {
      final adapterState = await FlutterBluePlus.adapterState.first;
      if (adapterState != BluetoothAdapterState.on) {
        if (mounted) setState(() => _error = 'Bluetooth is off.');
        return;
      }
      if (Platform.isAndroid) {
        final statuses = await [
          Permission.bluetoothScan,
          Permission.bluetoothConnect,
          Permission.location,
        ].request();
        if (!statuses.values.every((s) => s == PermissionStatus.granted)) {
          if (mounted) {
            setState(() => _error = 'Bluetooth permissions required.');
            _showPermissionDenied = true;
          }
          return;
        }
      }
    } catch (e) {
      if (mounted) setState(() => _error = 'Permission error: $e');
      return;
    }

    if (!mounted) return;
    setState(() { _results = []; _scanning = true; _error = null; });

    try {
      final ble = context.read<BleService>();
      final results = await ble.scan(timeout: 5);
      // Sort bonded devices first
      results.sort((a, b) {
        final aBonded = a.device.isConnected ? 0 : 1;
        final bBonded = b.device.isConnected ? 0 : 1;
        if (aBonded != bBonded) return aBonded - bBonded;
        return b.rssi.compareTo(a.rssi); // then by signal strength
      });
      if (mounted) setState(() { _results = results; _scanning = false; });
    } catch (e) {
      if (mounted) setState(() { _scanning = false; _error = e.toString(); });
    }
  }

  Future<void> _connect(ScanResult result) async {
    final ble = context.read<BleService>();
    try {
      await FlutterBluePlus.stopScan();
      await ble.connect(result.device);
      if (mounted && ble.state.isConnected) {
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _error = 'Connection failed: $e');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      initialChildSize: 0.5,
      minChildSize: 0.3,
      maxChildSize: 0.8,
      expand: false,
      builder: (context, scrollController) => Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 8, 0),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    _scanning ? 'Scanning...' : 'Select Device',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                if (_scanning)
                  const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                else
                  IconButton(icon: const Icon(Icons.refresh), onPressed: _startScan),
                IconButton(icon: const Icon(Icons.close), onPressed: () => Navigator.pop(context)),
              ],
            ),
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 13)),
                  if (_showPermissionDenied)
                    TextButton(
                      onPressed: () => openAppSettings(),
                      child: const Text('Open Settings'),
                    ),
                ],
              ),
            ),
          if (_scanning) const LinearProgressIndicator(),
          Expanded(
            child: Consumer<BleService>(
              builder: (_, ble, child) {
                final connecting = ble.state == TbConnectionState.connecting;
                if (_results.isEmpty && !_scanning) {
                  return const Center(child: Text('No devices found.'));
                }
                return ListView.builder(
                  controller: scrollController,
                  itemCount: _results.length,
                  itemBuilder: (context, index) {
                    final r = _results[index];
                    final name = r.advertisementData.advName;
                    return ListTile(
                      leading: const Icon(Icons.bluetooth, color: Colors.blue),
                      title: Text(name.isEmpty ? 'Unknown' : name),
                      subtitle: Text('RSSI: ${r.rssi}'),
                      trailing: connecting
                          ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                          : const Icon(Icons.chevron_right),
                      onTap: connecting ? null : () => _connect(r),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

// --- Widgets ---

class _ConnectionBadge extends StatelessWidget {
  final TbConnectionState state;
  const _ConnectionBadge({required this.state});

  @override
  Widget build(BuildContext context) {
    final connected = state.isConnected;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: Chip(
        avatar: Icon(Icons.circle, size: 10, color: connected ? Colors.green : Colors.grey),
        label: Text(state.label, style: const TextStyle(fontSize: 12)),
        visualDensity: VisualDensity.compact,
      ),
    );
  }
}

class _CharCount extends StatelessWidget {
  final String text;
  const _CharCount({required this.text});

  @override
  Widget build(BuildContext context) {
    final total = text.length;
    final mapped = countMappedChars(text);
    final keycodeCount = text.isEmpty ? 0 : textToKeycodes(text).keycodes.length;
    final style = Theme.of(context).textTheme.bodySmall;
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text('$total chars → $keycodeCount keycodes', style: style),
        if (total != mapped)
          Text('${total - mapped} skipped',
              style: style?.copyWith(color: Colors.orange)),
      ],
    );
  }
}
