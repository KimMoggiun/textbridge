import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/ble_service.dart';
import '../services/compression_service.dart';
import '../services/keycode_service.dart';
import '../services/settings_service.dart';
import '../services/transmission_service.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('설정')),
      body: ListView(
        children: [
          Consumer<BleService>(
            builder: (_, ble, child) => _Section(
              title: '연결',
              children: [
                _InfoTile('기기', ble.deviceName.isEmpty ? '-' : ble.deviceName),
                _InfoTile('MTU', '${ble.mtu}'),
                _InfoTile('청크 크기', '${chunkSizeFromMtu(ble.mtu)} 키코드'),
              ],
            ),
          ),
          Consumer<SettingsService>(
            builder: (_, settings, child) => _Section(
              title: '키 딜레이',
              children: [
                _DelaySlider(
                  label: '키 누름',
                  description: '각 키를 누르고 있는 시간',
                  value: settings.pressDelay,
                  min: 1,
                  max: 20,
                  onChanged: (v) => settings.setPressDelay(v),
                ),
                _DelaySlider(
                  label: '키 해제',
                  description: '키 해제 후 다음 키까지 간격',
                  value: settings.releaseDelay,
                  min: 1,
                  max: 20,
                  onChanged: (v) => settings.setReleaseDelay(v),
                ),
                _DelaySlider(
                  label: '조합 딜레이',
                  description: 'Shift/Ctrl 조합 내부 간격',
                  value: settings.comboDelay,
                  min: 1,
                  max: 20,
                  onChanged: (v) => settings.setComboDelay(v),
                ),
                _DelaySlider(
                  label: '워밍업',
                  description: '첫 청크 전 USB 호스트 동기화',
                  value: settings.warmupDelay,
                  min: 1,
                  max: 100,
                  onChanged: (v) => settings.setWarmupDelay(v),
                ),
              ],
            ),
          ),
          Consumer2<SettingsService, TransmissionService>(
            builder: (_, settings, tx, child) => _Section(
              title: '전송',
              children: [
                SwitchListTile(
                  title: const Text('압축 모드'),
                  subtitle: Text(
                    settings.transmissionMode == TransmissionMode.compressed
                        ? '텍스트를 zlib 압축 후 hex로 전송 (디코더 필요)'
                        : 'ASCII 문자를 직접 전송 (디코더 설치용)',
                  ),
                  value: settings.transmissionMode == TransmissionMode.compressed,
                  onChanged: (v) => settings.setTransmissionMode(
                    v ? TransmissionMode.compressed : TransmissionMode.direct,
                  ),
                ),
                ListTile(
                  leading: const Icon(Icons.code),
                  title: const Text('H.java 디코더 삽입'),
                  subtitle: const Text('Direct 모드로 PC에 디코더를 전송'),
                  onTap: () => Navigator.pop(context, CompressionService.decoderJava),
                ),
                ListTile(
                  title: const Text('최대 재시도'),
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
            title: '정보',
            children: const [
              _InfoTile('버전', '1.0.0'),
              _InfoTile('프로토콜', 'TextBridge Phase 3'),
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
