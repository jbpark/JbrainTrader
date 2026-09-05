import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/models.dart';

class ApiService {
  String baseUrl;

  ApiService(this.baseUrl);

  Uri _uri(String path) => Uri.parse('$baseUrl$path');

  // 전체 상태 조회
  Future<Map<String, dynamic>> getStatus() async {
    final res = await http.get(_uri('/status')).timeout(const Duration(seconds: 10));
    if (res.statusCode == 200) {
      return jsonDecode(utf8.decode(res.bodyBytes));
    }
    throw Exception('상태 조회 실패: ${res.statusCode}');
  }

  // 서버에 빌드된 APK 정보 조회. {exists, size, mtime}
  Future<Map<String, dynamic>> getApkInfo() async {
    final res = await http.get(_uri('/apk/info')).timeout(const Duration(seconds: 10));
    if (res.statusCode == 200) {
      return jsonDecode(utf8.decode(res.bodyBytes));
    }
    throw Exception('APK 정보 조회 실패: ${res.statusCode}');
  }

  // ── AI 추천 종목 (웹 서비스와 동일 API — 자동 동기화) ──
  Future<List<dynamic>> getAiPicks() async {
    final res = await http.get(_uri('/ai-picks')).timeout(const Duration(seconds: 10));
    if (res.statusCode == 200) {
      return jsonDecode(utf8.decode(res.bodyBytes));
    }
    throw Exception('AI 추천 프로파일 조회 실패: ${res.statusCode}');
  }

  /// AI 종목이 선별한 종목 목록 (AI 매매 대상 종목 선택용)
  Future<List<dynamic>> getAiPickStocks() async {
    final res = await http.get(_uri('/ai-picks/stocks')).timeout(const Duration(seconds: 10));
    if (res.statusCode == 200) {
      return jsonDecode(utf8.decode(res.bodyBytes));
    }
    throw Exception('AI 종목 목록 조회 실패: ${res.statusCode}');
  }

  Future<Map<String, dynamic>> getAiPickModels() async {
    final res = await http.get(_uri('/ai-picks/models')).timeout(const Duration(seconds: 10));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  Future<Map<String, dynamic>> createAiPick(String name, String prompt, String model,
      {String? market}) async {
    final res = await http.post(
      _uri('/ai-picks'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'name': name, 'prompt': prompt, 'model': model,
        if (market != null) 'market': market}),
    ).timeout(const Duration(seconds: 10));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  Future<Map<String, dynamic>> updateAiPick(int id, String name, String prompt, String model,
      {String? market}) async {
    final res = await http.put(
      _uri('/ai-picks/$id'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'name': name, 'prompt': prompt, 'model': model,
        if (market != null) 'market': market}),
    ).timeout(const Duration(seconds: 10));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  Future<Map<String, dynamic>> deleteAiPick(int id) async {
    final res = await http.delete(_uri('/ai-picks/$id')).timeout(const Duration(seconds: 10));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  Future<Map<String, dynamic>> runAiPick(int id) async {
    final res = await http.post(_uri('/ai-picks/$id/run')).timeout(const Duration(seconds: 10));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  Future<Map<String, dynamic>> getAiPickResult(int id) async {
    final res = await http.get(_uri('/ai-picks/$id/result')).timeout(const Duration(seconds: 10));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  /// 선별 종목의 재무제표·투자지표 상세 비교 실행
  Future<Map<String, dynamic>> runAiPickCompare(int id) async {
    final res = await http.post(_uri('/ai-picks/$id/compare')).timeout(const Duration(seconds: 10));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  Future<Map<String, dynamic>> getAiPickComparison(int id) async {
    final res = await http.get(_uri('/ai-picks/$id/comparison')).timeout(const Duration(seconds: 15));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  /// 상세 비교 결과를 구글 시트에 업로드 (탭 이름 = 프로파일명)
  Future<Map<String, dynamic>> exportAiPickComparisonToGSheet(int id) async {
    final res = await http
        .post(_uri('/ai-picks/$id/comparison/export-gsheet'))
        .timeout(const Duration(seconds: 120));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  // ── AI 매매 (종목별 매매 전략, 웹과 동일 API) ──
  Future<List<dynamic>> getAiTrades() async {
    final res = await http.get(_uri('/ai-trades')).timeout(const Duration(seconds: 10));
    if (res.statusCode == 200) {
      return jsonDecode(utf8.decode(res.bodyBytes));
    }
    throw Exception('AI 매매 프로파일 조회 실패: ${res.statusCode}');
  }

  Future<Map<String, dynamic>> createAiTrade(String name, String prompt, String model,
      {String? market}) async {
    final res = await http.post(
      _uri('/ai-trades'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'name': name, 'prompt': prompt, 'model': model,
        if (market != null) 'market': market}),
    ).timeout(const Duration(seconds: 10));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  Future<Map<String, dynamic>> updateAiTrade(int id, String name, String prompt, String model,
      {String? market}) async {
    final res = await http.put(
      _uri('/ai-trades/$id'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'name': name, 'prompt': prompt, 'model': model,
        if (market != null) 'market': market}),
    ).timeout(const Duration(seconds: 10));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  Future<Map<String, dynamic>> deleteAiTrade(int id) async {
    final res = await http.delete(_uri('/ai-trades/$id')).timeout(const Duration(seconds: 10));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  Future<Map<String, dynamic>> runAiTrade(int id, String ticker, String tickerName) async {
    final res = await http.post(
      _uri('/ai-trades/$id/run'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'ticker': ticker, 'ticker_name': tickerName}),
    ).timeout(const Duration(seconds: 10));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  Future<Map<String, dynamic>> getAiTradeResult(int id) async {
    final res = await http.get(_uri('/ai-trades/$id/result')).timeout(const Duration(seconds: 10));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  // ── AI 캘린더 (날짜별 주요 일정 + 일정 기반 매매 타이밍, 웹과 동일 API) ──
  Future<List<dynamic>> getAiCalendars() async {
    final res = await http.get(_uri('/ai-calendar')).timeout(const Duration(seconds: 10));
    if (res.statusCode == 200) {
      return jsonDecode(utf8.decode(res.bodyBytes));
    }
    throw Exception('AI 캘린더 프로파일 조회 실패: ${res.statusCode}');
  }

  Future<Map<String, dynamic>> createAiCalendar(String name, String prompt, String model,
      {String? market}) async {
    final res = await http.post(
      _uri('/ai-calendar'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'name': name, 'prompt': prompt, 'model': model,
        if (market != null) 'market': market}),
    ).timeout(const Duration(seconds: 10));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  Future<Map<String, dynamic>> updateAiCalendar(
      int id, String name, String prompt, String model,
      {String? market}) async {
    final res = await http.put(
      _uri('/ai-calendar/$id'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'name': name, 'prompt': prompt, 'model': model,
        if (market != null) 'market': market}),
    ).timeout(const Duration(seconds: 10));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  Future<Map<String, dynamic>> deleteAiCalendar(int id) async {
    final res = await http.delete(_uri('/ai-calendar/$id')).timeout(const Duration(seconds: 10));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  Future<Map<String, dynamic>> runAiCalendar(int id) async {
    final res = await http.post(_uri('/ai-calendar/$id/run')).timeout(const Duration(seconds: 10));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  Future<Map<String, dynamic>> getAiCalendarResult(int id) async {
    final res = await http.get(_uri('/ai-calendar/$id/result')).timeout(const Duration(seconds: 15));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  /// 여러 종목을 한 프로파일로 순차 분석 (보유 종목 전체 분석)
  Future<Map<String, dynamic>> runAiTradeBatch(
      int id, List<Map<String, String>> items) async {
    final res = await http.post(
      _uri('/ai-trades/$id/run-batch'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'items': items}),
    ).timeout(const Duration(seconds: 20));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  Future<Map<String, dynamic>> getAiTradeBatchStatus(int id) async {
    final res = await http
        .get(_uri('/ai-trades/$id/batch-status'))
        .timeout(const Duration(seconds: 10));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  /// 현재 보유 종목을 구글 시트 '보유종목' 탭에 업로드
  /// 보유 종목/잔고 새로고침 — 증권사에서 현재가를 다시 불러온다 (수 초 뒤 status에 반영)
  Future<Map<String, dynamic>> refreshAccount() async {
    final res = await http
        .post(_uri('/account/refresh'))
        .timeout(const Duration(seconds: 15));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  Future<Map<String, dynamic>> exportHoldingsToGSheet() async {
    final res = await http
        .post(_uri('/holdings/export-gsheet'))
        .timeout(const Duration(seconds: 120));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  /// 완료된 매매 전략을 종목코드별로 조회 (보유 종목에서 해당 종목 전략 표시용)
  Future<Map<String, dynamic>> getAiTradeStrategies() async {
    final res = await http
        .get(_uri('/ai-trades/strategies'))
        .timeout(const Duration(seconds: 15));
    return jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
  }

  /// 매매 전략을 구글 시트에 업로드 (탭 이름 = 프로파일명, 같은 종목이면 갱신)
  Future<Map<String, dynamic>> exportAiTradeToGSheet(int id) async {
    final res = await http
        .post(_uri('/ai-trades/$id/export-gsheet'))
        .timeout(const Duration(seconds: 120));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  /// AI Notice — 메신저로 발송된 AI 알림 목록 (전략감시/브리핑/복기)
  Future<List<dynamic>> getAiNotices({String? category, int limit = 100}) async {
    final params = <String, String>{'limit': '$limit'};
    if (category != null && category.isNotEmpty) params['category'] = category;
    final uri = _uri('/ai-notices').replace(queryParameters: params);
    final res = await http.get(uri).timeout(const Duration(seconds: 15));
    final data = jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
    return (data['notices'] as List<dynamic>?) ?? [];
  }

  // 연결 테스트
  Future<bool> testConnection() async {
    try {
      final res = await http.get(_uri('/status')).timeout(const Duration(seconds: 5));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  // 로그인
  Future<Map<String, dynamic>> login(String mode, String assetType) async {
    final res = await http.post(
      _uri('/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'mode': mode, 'asset_type': assetType}),
    ).timeout(const Duration(seconds: 10));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  /// 계좌 설정 일부 변경 (예: {'acc_no': ...} 또는 {'market': 'OVERSEAS'})
  /// — 웹 계정 탭의 계좌 변경/국내·해외 전환과 동일한 API
  Future<Map<String, dynamic>> updateAccountFields(Map<String, dynamic> fields) async {
    final res = await http.post(
      _uri('/account'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(fields),
    ).timeout(const Duration(seconds: 15));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  // 계좌 정보 업데이트
  Future<void> updateAccount(AccountInfo info) async {
    await http.post(
      _uri('/account'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'name': info.name,
        'acc_no': info.accNo,
        'balance': info.balance,
      }),
    );
  }

  // 종목 추가
  Future<Map<String, dynamic>> addTicker(String ticker, String rule) async {
    final res = await http.post(
      _uri('/tickers'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'ticker': ticker, 'rule': rule}),
    );
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  // 종목 삭제
  Future<void> removeTicker(String ticker) async {
    await http.delete(_uri('/tickers/$ticker'));
  }

  // 전략 변경
  Future<void> setRule(String ticker, String rule) async {
    await http.post(
      _uri('/tickers/$ticker/rule'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'rule': rule}),
    );
  }

  // 일시정지
  Future<void> pauseTicker(String ticker) async {
    await http.post(_uri('/tickers/$ticker/pause'));
  }

  // 재개
  Future<void> resumeTicker(String ticker) async {
    await http.post(_uri('/tickers/$ticker/resume'));
  }

  // 종목 검색
  Future<List<Map<String, dynamic>>> searchTickers(String query) async {
    try {
      final uri = Uri.parse('$baseUrl/collector/search').replace(
        queryParameters: {'q': query, 'source': 'KRX'},
      );
      final res = await http.get(uri).timeout(const Duration(seconds: 5));
      if (res.statusCode == 200) {
        final data = jsonDecode(utf8.decode(res.bodyBytes));
        return List<Map<String, dynamic>>.from(data);
      }
    } catch (_) {}
    return [];
  }

  // 전략 목록 조회
  Future<List<String>> getStrategies() async {
    try {
      final res = await http.get(_uri('/strategies')).timeout(const Duration(seconds: 5));
      if (res.statusCode == 200) {
        final data = jsonDecode(utf8.decode(res.bodyBytes));
        // 백엔드는 [{name, content, ...}, ...] 형태의 배열을 반환
        if (data is List && data.isNotEmpty) {
          final names = data
              .map((e) => (e['name'] ?? '').toString())
              .where((n) => n.isNotEmpty)
              .toList();
          if (names.isNotEmpty) {
            // NONE이 없으면 끝에 추가
            if (!names.contains('NONE')) names.add('NONE');
            return names;
          }
        }
        // 이전 형식 호환 ({strategies: [...]})
        if (data is Map && data['strategies'] is List) {
          return List<String>.from(data['strategies']);
        }
      }
    } catch (_) {}
    return ['DEFAULT', 'SCALPING_1', 'SCALPING_2', 'NONE'];
  }

  // 시뮬레이션 시작
  Future<void> startSimulation(String ticker, Map<String, dynamic> config) async {
    await http.post(
      _uri('/simulation/start'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'ticker': ticker, 'config': config}),
    );
  }

  // 시뮬레이션 중지
  Future<void> stopSimulation(String ticker) async {
    await http.post(
      _uri('/simulation/stop'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'ticker': ticker}),
    );
  }

  // 백테스트 분석
  Future<Map<String, dynamic>> analyze(String ticker, Map<String, dynamic> config) async {
    final res = await http.post(
      _uri('/simulation/analyze'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'ticker': ticker, 'config': config}),
    ).timeout(const Duration(seconds: 120));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  // 매매 내역 조회
  Future<List<Map<String, dynamic>>> getTrades(String date, {String? accNo}) async {
    final query = {'date': date};
    if (accNo != null) query['acc_no'] = accNo;
    
    // queryParameters를 Uri.parse에 직접 붙이는 대신 Uri의 생성자나 replace 메서드 활용
    final baseUri = _uri('/trades');
    final uri = Uri(
      scheme: baseUri.scheme,
      host: baseUri.host,
      port: baseUri.port,
      path: baseUri.path,
      queryParameters: query,
    );
    
    final res = await http.get(uri).timeout(const Duration(seconds: 10));
    if (res.statusCode == 200) {
      return List<Map<String, dynamic>>.from(jsonDecode(utf8.decode(res.bodyBytes)));
    }
    return [];
  }

  // 매매 내역 동기화
  Future<Map<String, dynamic>> syncTrades(String date, String accNo) async {
    final res = await http.post(
      _uri('/trades/sync'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'date': date, 'acc_no': accNo}),
    ).timeout(const Duration(seconds: 30));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  /// 매매일지를 구글 시트에 업로드 (월별 탭 + 일별요약, 웹과 동일 API)
  Future<Map<String, dynamic>> exportTradesToGSheet(String date, String accNo) async {
    final res = await http.post(
      _uri('/trades/export-gsheet'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'date': date, 'acc_no': accNo}),
    ).timeout(const Duration(seconds: 120));
    return jsonDecode(utf8.decode(res.bodyBytes));
  }
}
