import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../models/models.dart';

class WebSocketService {
  WebSocketChannel? _channel;
  String? _host;
  String? _subscribedTicker;
  final StreamController<TickData> _tickController = StreamController.broadcast();
  final StreamController<String> _logController = StreamController.broadcast();

  Stream<TickData> get tickStream => _tickController.stream;
  Stream<String> get logStream => _logController.stream;

  bool get isConnected => _channel != null;

  void connect(String host, {int port = 8765}) {
    disconnect();
    _host = host;
    try {
      _channel = WebSocketChannel.connect(
        Uri.parse('ws://$host:$port'),
      );
      _channel!.stream.listen(
        _onMessage,
        onError: _onError,
        onDone: _onDone,
      );
      _logController.add('WebSocket 연결됨: ws://$host:$port');
    } catch (e) {
      _logController.add('WebSocket 연결 오류: $e');
    }
  }

  void subscribe(String ticker) {
    if (_channel == null) return;
    _subscribedTicker = ticker;
    _channel!.sink.add(jsonEncode({'type': 'subscribe', 'ticker': ticker}));
    _logController.add('구독 시작: $ticker');
  }

  void _onMessage(dynamic message) {
    try {
      final data = jsonDecode(message as String);
      final type = data['type'];
      if (type == 'update') {
        final tick = TickData.fromJson(data['data']);
        _tickController.add(tick);
      } else if (type == 'history') {
        final list = data['data'] as List<dynamic>;
        for (final item in list) {
          _tickController.add(TickData.fromJson(item));
        }
      } else if (type == 'analysis_progress') {
        _logController.add('[분석] ${data['data']}');
      }
    } catch (e) {
      // 무시
    }
  }

  void _onError(dynamic error) {
    _logController.add('WebSocket 오류: $error');
  }

  void _onDone() {
    _logController.add('WebSocket 연결 종료');
    _channel = null;
  }

  void disconnect() {
    _channel?.sink.close();
    _channel = null;
    _subscribedTicker = null;
  }

  void dispose() {
    disconnect();
    _tickController.close();
    _logController.close();
  }
}
