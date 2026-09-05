import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/models.dart';
import '../services/api_service.dart';
import '../services/websocket_service.dart';

class TradingProvider extends ChangeNotifier {
  String _serverHost = '192.168.0.1';
  int _serverPort = 5000;
  bool _isConnected = false;
  bool _isLoading = false;

  AccountInfo? _account;
  List<TickerInfo> _tickers = [];
  List<Map<String, dynamic>> _holdings = [];
  List<String> _logs = [];
  String _engineStatus = 'DISCONNECTED';

  final WebSocketService _wsService = WebSocketService();
  ApiService? _apiService;
  Timer? _pollingTimer;

  // Getters
  String get serverHost => _serverHost;
  int get serverPort => _serverPort;
  String get baseUrl => 'http://$_serverHost:$_serverPort';
  bool get isConnected => _isConnected;
  bool get isLoading => _isLoading;
  AccountInfo? get account => _account;
  List<TickerInfo> get tickers => _tickers;
  List<Map<String, dynamic>> get holdings => _holdings;
  List<String> get logs => _logs;
  String get engineStatus => _engineStatus;
  WebSocketService get wsService => _wsService;

  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _serverHost = prefs.getString('server_host') ?? '192.168.0.1';
    _serverPort = prefs.getInt('server_port') ?? 5000;
    _apiService = ApiService(baseUrl);
    notifyListeners();
    await fetchStatus();
    _startPolling();
  }

  Future<void> saveServerSettings(String host, int port) async {
    _serverHost = host;
    _serverPort = port;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('server_host', host);
    await prefs.setInt('server_port', port);
    _apiService = ApiService(baseUrl);
    notifyListeners();
    await fetchStatus();
  }

  Future<bool> testConnection() async {
    _apiService ??= ApiService(baseUrl);
    return await _apiService!.testConnection();
  }

  void _startPolling() {
    _pollingTimer?.cancel();
    _pollingTimer = Timer.periodic(const Duration(seconds: 3), (_) => fetchStatus());
  }

  Future<void> fetchStatus() async {
    _apiService ??= ApiService(baseUrl);
    try {
      final data = await _apiService!.getStatus();
      _isConnected = true;
      _engineStatus = data['status'] ?? 'UNKNOWN';
      if (data['account'] != null) {
        _account = AccountInfo.fromJson(data['account']);
        // 보유종목 (ticker/name/qty/buy_price/current_price/profit)
        final hl = data['account']['holdings'] as List<dynamic>? ?? [];
        _holdings = hl.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
      }
      final tickersMap = data['tickers'] as Map<String, dynamic>? ?? {};
      _tickers = tickersMap.entries
          .map((e) => TickerInfo.fromJson(e.key, e.value))
          .toList();
      // PC 웹(Vue)과 동일하게 종목명 기준 가나다순 정렬
      _tickers.sort((a, b) {
        final nameA = a.name.isEmpty ? a.ticker : a.name;
        final nameB = b.name.isEmpty ? b.ticker : b.name;
        return nameA.compareTo(nameB);
      });
      final logsList = data['logs'] as List<dynamic>? ?? [];
      _logs = logsList.reversed.map((e) => e.toString()).toList();
    } catch (e) {
      _isConnected = false;
      _engineStatus = 'DISCONNECTED';
    }
    notifyListeners();
  }

  Future<void> login(String mode) async {
    _isLoading = true;
    notifyListeners();
    try {
      await _apiService?.login(mode, 'STOCK');
      await fetchStatus();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> addTicker(String ticker, String rule) async {
    await _apiService?.addTicker(ticker, rule);
    await fetchStatus();
  }

  Future<void> removeTicker(String ticker) async {
    await _apiService?.removeTicker(ticker);
    await fetchStatus();
  }

  Future<void> setRule(String ticker, String rule) async {
    await _apiService?.setRule(ticker, rule);
    await fetchStatus();
  }

  Future<void> togglePause(TickerInfo ticker) async {
    if (ticker.paused) {
      await _apiService?.resumeTicker(ticker.ticker);
    } else {
      await _apiService?.pauseTicker(ticker.ticker);
    }
    await fetchStatus();
  }

  Future<List<Map<String, dynamic>>> searchTickers(String query) async {
    return await _apiService?.searchTickers(query) ?? [];
  }

  Future<List<String>> getStrategies() async {
    return await _apiService?.getStrategies() ?? ['DEFAULT', 'NONE'];
  }

  Future<void> startSimulation(String ticker, Map<String, dynamic> config) async {
    await _apiService?.startSimulation(ticker, config);
    await fetchStatus();
  }

  Future<void> stopSimulation(String ticker) async {
    await _apiService?.stopSimulation(ticker);
    await fetchStatus();
  }

  Future<Map<String, dynamic>?> analyze(String ticker, Map<String, dynamic> config) async {
    return await _apiService?.analyze(ticker, config);
  }

  Future<List<Map<String, dynamic>>> getTrades(String date) async {
    return await _apiService?.getTrades(date, accNo: _account?.accNo) ?? [];
  }

  Future<Map<String, dynamic>> syncTrades(String date) async {
    if (_account?.accNo == null) return {'status': 'ERROR', 'msg': '계좌 정보가 없습니다.'};
    return await _apiService?.syncTrades(date, _account!.accNo) ?? {'status': 'ERROR', 'msg': 'API 서비스 오픈 실패'};
  }

  /// 계좌 변경 — 변경 후 서버가 잔고/보유종목을 다시 조회하므로 status 폴링으로 반영됨
  Future<void> changeAccount(String accNo) async {
    await _apiService?.updateAccountFields({'acc_no': accNo});
    await fetchStatus();
  }

  /// 국내/해외 시장 전환
  Future<void> changeMarket(String market) async {
    await _apiService?.updateAccountFields({'market': market});
    await fetchStatus();
  }

  /// 계좌별 시장 고정 설정 (국내전용/해외전용). market이 null이면 해제(수동 모드)
  Future<void> setAccountMarketPref(String accNo, String? market) async {
    await _apiService?.updateAccountFields({
      'acc_market_prefs': {accNo: market},
    });
    await fetchStatus();
  }

  Future<Map<String, dynamic>> exportTradesToGSheet(String date) async {
    if (_account?.accNo == null) return {'status': 'ERROR', 'message': '계좌 정보가 없습니다.'};
    return await _apiService?.exportTradesToGSheet(date, _account!.accNo) ??
        {'status': 'ERROR', 'message': 'API 서비스 오픈 실패'};
  }

  Future<Map<String, dynamic>> getApkInfo() async {
    _apiService ??= ApiService(baseUrl);
    return await _apiService!.getApkInfo();
  }

  // ── AI 추천 종목 ──
  ApiService get api {
    _apiService ??= ApiService(baseUrl);
    return _apiService!;
  }

  void connectWebSocket(String ticker) {
    _wsService.connect(_serverHost);
    _wsService.subscribe(ticker);
  }

  @override
  void dispose() {
    _pollingTimer?.cancel();
    _wsService.dispose();
    super.dispose();
  }
}
