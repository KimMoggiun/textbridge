import 'dart:async';
import 'dart:collection';

import 'package:flutter/foundation.dart';

import '../models/connection_state.dart';
import '../models/protocol.dart';
import '../services/ble_service.dart';
import '../services/keycode_service.dart';
import '../services/settings_service.dart';

/// Transmission progress callback data.
class TransmissionProgress {
  final int sentChunks;
  final int totalChunks;
  final int sentKeycodes;
  final int totalKeycodes;

  const TransmissionProgress({
    required this.sentChunks,
    required this.totalChunks,
    required this.sentKeycodes,
    required this.totalKeycodes,
  });

  double get fraction => totalChunks > 0 ? sentChunks / totalChunks : 0;
}

/// High-level text transmission with flow control.
/// Handles START/KEYCODE/DONE sequence, ACK waiting, and retransmission.
class TransmissionService extends ChangeNotifier {
  final BleService _ble;
  SettingsService? _settings;
  StreamSubscription? _responseSub;

  TransmissionProgress _progress = const TransmissionProgress(
    sentChunks: 0,
    totalChunks: 0,
    sentKeycodes: 0,
    totalKeycodes: 0,
  );
  TransmissionProgress get progress => _progress;

  bool _isTransmitting = false;
  bool get isTransmitting => _isTransmitting;

  bool _abortRequested = false;
  String? _lastError;
  String? get lastError => _lastError;

  int? _failedAtKeycode;
  int? get failedAtKeycode => _failedAtKeycode;

  int _maxRetries = 3;
  int get maxRetries => _maxRetries;
  set maxRetries(int v) {
    _maxRetries = v.clamp(1, 5);
    notifyListeners();
  }

  TransmissionService(this._ble, [this._settings]);

  /// Send text through the TextBridge protocol.
  /// Returns true if all chunks were acknowledged.
  Future<bool> sendText(String text) async {
    if (_isTransmitting) return false;
    if (!_ble.state.isConnected) return false;

    final result = textToKeycodes(
      text,
      targetOS: _settings?.targetOS ?? TargetOS.windows,
    );
    final keycodes = result.keycodes;
    if (keycodes.isEmpty) {
      _lastError = 'No mappable characters';
      notifyListeners();
      return false;
    }

    final chunkSize = chunkSizeFromMtu(_ble.mtu);
    final chunks = chunkKeycodes(keycodes, chunkSize);

    _isTransmitting = true;
    _abortRequested = false;
    _lastError = null;
    _failedAtKeycode = null;
    _ble.setState(TbConnectionState.transmitting);
    _progress = TransmissionProgress(
      sentChunks: 0,
      totalChunks: chunks.length,
      sentKeycodes: 0,
      totalKeycodes: keycodes.length,
    );
    notifyListeners();

    // Set up response queue (list-based to avoid subscription gaps)
    final responseQueue = Queue<Uint8List>();
    Completer<void>? responseWaiter;
    _responseSub = _ble.responses.listen((data) {
      debugPrint('[TB-Q] enqueue: ${data.map((b) => "0x${b.toRadixString(16)}").toList()}');
      responseQueue.add(data);
      if (responseWaiter != null && !responseWaiter!.isCompleted) {
        responseWaiter!.complete();
      }
    });

    try {
      // 0. Send delay configuration to firmware
      if (_settings != null) {
        await _ble.write(makeSetDelay(
          pressDelay: _settings!.pressDelay,
          releaseDelay: _settings!.releaseDelay,
          comboDelay: _settings!.comboDelay,
          togglePress: _settings!.togglePress,
          toggleDelay: _settings!.toggleDelay,
          warmupDelay: _settings!.warmupDelay,
        ));
        final delayResp = await _dequeue(responseQueue, () => responseWaiter, (c) => responseWaiter = c, const Duration(seconds: 2));
        debugPrint('[TB] SET_DELAY resp: ${delayResp != null ? delayResp.map((b) => "0x${b.toRadixString(16)}").toList() : "TIMEOUT"}');
      }

      // 1. Send START
      debugPrint('[TB] Sending START, chunks=${chunks.length}');
      await _ble.write(makeStart(0, chunks.length));
      final ready = await _dequeue(responseQueue, () => responseWaiter, (c) => responseWaiter = c, const Duration(seconds: 5));
      debugPrint('[TB] START resp: ${ready != null ? ready.map((b) => "0x${b.toRadixString(16)}").toList() : "TIMEOUT"}');
      if (ready == null || ready[0] != respReady) {
        _lastError = 'READY timeout';
        return false;
      }

      // 2. Send KEYCODE chunks
      var sentKeycodes = 0;
      for (var i = 0; i < chunks.length; i++) {
        if (_abortRequested) {
          await _ble.write(makeAbort((i + 1) % 256));
          _lastError = 'Aborted by user';
          _failedAtKeycode = sentKeycodes;
          return false;
        }

        final chunk = chunks[i];
        var success = false;

        // Dynamic ACK timeout: warmup (first chunk only) + injection time + buffer
        final pressMs = _settings?.pressDelay ?? 5;
        final releaseMs = _settings?.releaseDelay ?? 5;
        final comboMs = _settings?.comboDelay ?? 2;
        final togglePressMs = _settings?.togglePress ?? 20;
        final toggleDelayMs = _settings?.toggleDelay ?? 100;
        final warmupMs = (i == 0) ? (_settings?.warmupDelay ?? 50) : 0;
        // Toggle chunks (1 pair) use toggle_press+toggle_delay instead of press+release
        final isToggleChunk = chunk.pairs.length == 1 &&
            (chunk.pairs[0] == const KeycodePair(0x90, 0x00) ||
             chunk.pairs[0] == const KeycodePair(0x2C, 0x01));
        final injectionMs = isToggleChunk
            ? togglePressMs + toggleDelayMs + 2 * comboMs
            : chunk.pairs.length * (pressMs + releaseMs + 2 * comboMs);
        final ackTimeoutMs = warmupMs + injectionMs + 500; // buffer for BLE round-trip

        for (var retry = 0; retry <= _maxRetries; retry++) {
          if (retry > 0) {
            await Future.delayed(const Duration(milliseconds: 100));
          }
          await _ble.write(chunk.toBytes());
          final resp = await _dequeue(responseQueue, () => responseWaiter, (c) => responseWaiter = c, Duration(milliseconds: ackTimeoutMs));

          if (resp == null) {
            if (retry == _maxRetries) {
              _lastError = 'ACK timeout (chunk ${i + 1}/${chunks.length})';
              _failedAtKeycode = sentKeycodes;
              return false;
            }
            continue;
          }

          if (resp[0] == respAck) {
            success = true;
            break;
          } else if (resp[0] == respNack) {
            // NACK: retry
            continue;
          } else if (resp[0] == respError) {
            _lastError = 'ERROR from keyboard (chunk ${i + 1})';
            _failedAtKeycode = sentKeycodes;
            return false;
          }
        }

        if (!success) {
          _lastError = 'Max retries exceeded (chunk ${i + 1})';
          _failedAtKeycode = sentKeycodes;
          return false;
        }

        sentKeycodes += chunk.pairs.length;
        _progress = TransmissionProgress(
          sentChunks: i + 1,
          totalChunks: chunks.length,
          sentKeycodes: sentKeycodes,
          totalKeycodes: keycodes.length,
        );
        notifyListeners();
      }

      // 3. Send DONE
      final doneSeq = (chunks.length + 1) % 256;
      await _ble.write(makeDone(doneSeq));
      await _dequeue(responseQueue, () => responseWaiter, (c) => responseWaiter = c, const Duration(seconds: 5));

      return true;
    } catch (e) {
      _lastError = e.toString();
      return false;
    } finally {
      _isTransmitting = false;
      _responseSub?.cancel();
      _responseSub = null;
      if (_ble.state == TbConnectionState.transmitting) {
        _ble.setState(TbConnectionState.connected);
      }
      notifyListeners();
    }
  }

  /// Request abort of current transmission.
  void abort() {
    _abortRequested = true;
  }

  /// Dequeue next response from the list-based queue.
  /// Uses a shared Completer that the BLE listener signals when data arrives.
  Future<Uint8List?> _dequeue(
    Queue<Uint8List> queue,
    Completer<void>? Function() getWaiter,
    void Function(Completer<void>?) setWaiter,
    Duration timeout,
  ) async {
    final deadline = DateTime.now().add(timeout);
    while (DateTime.now().isBefore(deadline)) {
      if (queue.isNotEmpty) {
        return queue.removeFirst();
      }
      final remaining = deadline.difference(DateTime.now());
      if (remaining.isNegative) break;
      final waiter = Completer<void>();
      setWaiter(waiter);
      try {
        await waiter.future.timeout(remaining);
      } on TimeoutException {
        break;
      }
    }
    // Check one more time after wakeup
    if (queue.isNotEmpty) {
      return queue.removeFirst();
    }
    return null;
  }

  @override
  void dispose() {
    _responseSub?.cancel();
    super.dispose();
  }
}
