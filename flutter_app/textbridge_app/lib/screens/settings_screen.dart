import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/ble_service.dart';
import '../services/keycode_service.dart';
import '../services/settings_service.dart';
import '../services/transmission_service.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        children: [
          Consumer<BleService>(
            builder: (_, ble, child) => _Section(
              title: 'Connection',
              children: [
                _InfoTile('Device', ble.deviceName.isEmpty ? '-' : ble.deviceName),
                _InfoTile('MTU', '${ble.mtu}'),
                _InfoTile('Chunk size', '${chunkSizeFromMtu(ble.mtu)} keycodes'),
              ],
            ),
          ),
          Consumer<SettingsService>(
            builder: (_, settings, child) => _Section(
              title: 'Target OS',
              children: [
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: SegmentedButton<TargetOS>(
                    segments: const [
                      ButtonSegment(value: TargetOS.windows, label: Text('Windows')),
                      ButtonSegment(value: TargetOS.macOS, label: Text('macOS')),
                    ],
                    selected: {settings.targetOS},
                    onSelectionChanged: (v) => settings.setTargetOS(v.first),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Text(
                    'Determines the Han/Eng toggle key sent to the PC.',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
              ],
            ),
          ),
          Consumer<SettingsService>(
            builder: (_, settings, child) => _Section(
              title: 'Key Delays',
              children: [
                _DelaySlider(
                  label: 'Press duration',
                  description: 'How long each key is held down',
                  value: settings.pressDelay,
                  min: 1,
                  max: 50,
                  onChanged: (v) => settings.setPressDelay(v),
                ),
                _DelaySlider(
                  label: 'Release delay',
                  description: 'Gap between keystrokes (release → next press)',
                  value: settings.releaseDelay,
                  min: 1,
                  max: 50,
                  onChanged: (v) => settings.setReleaseDelay(v),
                ),
                _DelaySlider(
                  label: 'Combo delay',
                  description: 'Within Shift/Ctrl combos (modifier → key)',
                  value: settings.comboDelay,
                  min: 1,
                  max: 20,
                  onChanged: (v) => settings.setComboDelay(v),
                ),
                _DelaySlider(
                  label: 'Toggle press',
                  description: 'Han/Eng toggle key press duration',
                  value: settings.togglePress,
                  min: 5,
                  max: 50,
                  onChanged: (v) => settings.setTogglePress(v),
                ),
                _DelaySlider(
                  label: 'Toggle delay',
                  description: 'Wait after Han/Eng toggle for IME switch',
                  value: settings.toggleDelay,
                  min: 10,
                  max: 255,
                  onChanged: (v) => settings.setToggleDelay(v),
                ),
                _DelaySlider(
                  label: 'Warmup delay',
                  description: 'USB host sync before first chunk only',
                  value: settings.warmupDelay,
                  min: 1,
                  max: 100,
                  onChanged: (v) => settings.setWarmupDelay(v),
                ),
              ],
            ),
          ),
          Consumer<TransmissionService>(
            builder: (_, tx, child) => _Section(
              title: 'Transmission',
              children: [
                ListTile(
                  title: const Text('Max retries'),
                  subtitle: Text('${tx.maxRetries}'),
                  trailing: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      IconButton(
                        icon: const Icon(Icons.remove),
                        onPressed: tx.maxRetries > 1
                            ? () => tx.maxRetries = tx.maxRetries - 1
                            : null,
                      ),
                      IconButton(
                        icon: const Icon(Icons.add),
                        onPressed: tx.maxRetries < 5
                            ? () => tx.maxRetries = tx.maxRetries + 1
                            : null,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          _Section(
            title: 'About',
            children: const [
              _InfoTile('Version', '1.0.0'),
              _InfoTile('Protocol', 'TextBridge Phase 3'),
            ],
          ),
        ],
      ),
    );
  }
}

class _Section extends StatelessWidget {
  final String title;
  final List<Widget> children;
  const _Section({required this.title, required this.children});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
          child: Text(
            title,
            style: Theme.of(context)
                .textTheme
                .titleSmall
                ?.copyWith(color: Theme.of(context).colorScheme.primary),
          ),
        ),
        ...children,
        const Divider(),
      ],
    );
  }
}

class _DelaySlider extends StatelessWidget {
  final String label;
  final String description;
  final int value;
  final int min;
  final int max;
  final ValueChanged<int> onChanged;

  const _DelaySlider({
    required this.label,
    required this.description,
    required this.value,
    required this.min,
    required this.max,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      title: Text('$label: ${value}ms'),
      subtitle: Text(description),
      trailing: SizedBox(
        width: 160,
        child: Slider(
          value: value.toDouble(),
          min: min.toDouble(),
          max: max.toDouble(),
          divisions: max - min,
          onChanged: (v) => onChanged(v.round()),
        ),
      ),
    );
  }
}

class _InfoTile extends StatelessWidget {
  final String label;
  final String value;
  const _InfoTile(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return ListTile(
      title: Text(label),
      trailing: Text(value, style: Theme.of(context).textTheme.bodyMedium),
    );
  }
}
