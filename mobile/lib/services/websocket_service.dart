import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

class WebSocketService {
  final String baseUrl;
  WebSocketChannel? _channel;
  Timer? _reconnectTimer;
  int _retryCount = 0;
  bool _disposed = false;
  final _controller = StreamController<Map<String, dynamic>>.broadcast();

  Stream<Map<String, dynamic>> get stream => _controller.stream;
  bool get isConnected => _channel != null;

  WebSocketService({required this.baseUrl});

  void connect() {
    if (_disposed) return;
    final wsUrl = baseUrl.replaceFirst('http', 'ws');
    try {
      _channel = WebSocketChannel.connect(Uri.parse('$wsUrl/ws'));
      _retryCount = 0;
      _channel!.stream.listen(
        (data) {
          try {
            final json = jsonDecode(data as String) as Map<String, dynamic>;
            _controller.add(json);
          } catch (_) {}
        },
        onError: (_) => _scheduleReconnect(),
        onDone: () => _scheduleReconnect(),
      );
    } catch (_) {
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    _channel = null;
    if (_disposed) return;
    final delay = Duration(seconds: (2 << _retryCount).clamp(2, 60));
    _retryCount++;
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(delay, connect);
  }

  void dispose() {
    _disposed = true;
    _reconnectTimer?.cancel();
    _channel?.sink.close();
    _controller.close();
  }
}
