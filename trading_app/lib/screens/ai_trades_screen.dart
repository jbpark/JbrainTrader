import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../providers/trading_provider.dart';
import '../widgets/market_tab_bar.dart';

// ── 가격대별 매매 전략 그래프 계산 (테스트 가능하도록 최상위로 분리) ──

double? chartToNum(dynamic v) {
  if (v == null) return null;
  if (v is num) return v.toDouble();
  final m = RegExp(r'-?\d+(\.\d+)?').firstMatch(v.toString().replaceAll(',', ''));
  return m == null ? null : double.tryParse(m.group(0)!);
}

/// "105,000 ~ 113,000" -> [105000, 113000] / "270,000" -> [270000, 270000]
List<double>? parsePriceRange(dynamic v) {
  if (v == null) return null;
  final ms = RegExp(r'\d+(\.\d+)?').allMatches(v.toString().replaceAll(',', ''));
  if (ms.isEmpty) return null;
  final arr = ms.map((m) => double.parse(m.group(0)!)).toList();
  return [arr.reduce(math.min), arr.reduce(math.max)];
}

/// 전략에서 그래프에 필요한 가격 레벨 계산 (필수 값 없으면 null)
Map<String, dynamic>? buildChartLevels(Map<String, dynamic> s) {
  final cur = chartToNum(s['current_price']);
  final target = chartToNum(s['target_price']);
  final stop = chartToNum(s['stop_loss']);
  if (cur == null || target == null || stop == null || cur == 0) return null;
  final entry = parsePriceRange(s['entry_price']);

  final all = <double>[cur, target, stop, ...(entry ?? [])];
  var lo = all.reduce(math.min), hi = all.reduce(math.max);
  final pad = (hi - lo) * 0.12 == 0 ? math.max(hi * 0.02, 1) : (hi - lo) * 0.12;
  lo -= pad;
  hi += pad;

  String pct(double p) {
    final d = (p - cur) / cur * 100;
    return '${d >= 0 ? '+' : ''}${d.toStringAsFixed(1)}%';
  }

  final levels = <Map<String, dynamic>>[
    {'price': target, 'label': '목표가', 'diff': pct(target), 'color': const Color(0xFF00D084)},
  ];
  if (entry != null) {
    levels.add({'price': entry[1], 'label': '진입 상단', 'diff': pct(entry[1]), 'color': const Color(0xFF00A8CC)});
    if (entry[0] != entry[1]) {
      levels.add({'price': entry[0], 'label': '진입 하단', 'diff': pct(entry[0]), 'color': const Color(0xFF00A8CC)});
    }
  }
  levels.add({'price': cur, 'label': '현재가', 'diff': '', 'color': Colors.white});
  levels.add({'price': stop, 'label': '손절가', 'diff': pct(stop), 'color': Colors.redAccent});

  // 손익비 = (목표가 - 진입 중앙값) / (진입 중앙값 - 손절가)
  final entryMid = entry != null ? (entry[0] + entry[1]) / 2 : cur;
  final risk = entryMid - stop, reward = target - entryMid;
  double? rr;
  if (risk > 0 && reward > 0) rr = reward / risk;

  return {
    'levels': levels,
    'min': lo,
    'max': hi,
    'entryTop': entry?[1],
    'entryBottom': entry?[0],
    'rr': rr,
  };
}

/// AI 매매 — 종목을 선택해 매매 전략을 AI에게 묻는 화면 (웹과 동일 API, 자동 동기화)
class AiTradesScreen extends StatefulWidget {
  const AiTradesScreen({super.key});

  @override
  State<AiTradesScreen> createState() => _AiTradesScreenState();
}

class _AiTradesScreenState extends State<AiTradesScreen> {
  List<dynamic> _profiles = [];
  bool _loading = false;
  String _market = 'DOMESTIC'; // 국내/해외 탭

  List<Map<String, dynamic>> get _filtered => _profiles
      .whereType<Map>()
      .map((e) => Map<String, dynamic>.from(e))
      .where((p) => MarketUtil.of(p) == _market)
      .toList();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadProfiles());
  }

  Future<void> _loadProfiles() async {
    setState(() => _loading = true);
    try {
      final res = await context.read<TradingProvider>().api.getAiTrades();
      if (mounted) setState(() => _profiles = res);
    } catch (e) {
      if (mounted) _toast('프로파일 조회 실패: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _toast(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), behavior: SnackBarBehavior.floating),
    );
  }

  Future<void> _deleteProfile(Map<String, dynamic> p) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        backgroundColor: const Color(0xFF161B22),
        title: const Text('프로파일 삭제', style: TextStyle(color: Colors.white)),
        content: Text("'${p['name']}' 프로파일을 삭제할까요?\n웹 서비스에도 함께 반영됩니다.",
            style: const TextStyle(color: Colors.white70)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('취소')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Colors.redAccent),
            onPressed: () => Navigator.pop(c, true),
            child: const Text('삭제'),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    await context.read<TradingProvider>().api.deleteAiTrade(p['id']);
    _toast('삭제되었습니다.');
    _loadProfiles();
  }

  void _openEditor([Map<String, dynamic>? profile]) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
          builder: (_) => AiTradeEditorScreen(profile: profile, market: _market)),
    );
    _loadProfiles();
  }

  Color _statusColor(String? s) => switch (s) {
        'done' => const Color(0xFF00D084),
        'running' => Colors.amber,
        'error' => Colors.redAccent,
        _ => Colors.grey,
      };

  String _statusLabel(String? s) => switch (s) {
        'done' => '완료',
        'running' => '실행 중',
        'error' => '오류',
        _ => '미실행',
      };

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      appBar: AppBar(
        backgroundColor: const Color(0xFF161B22),
        title: const Text('🤖 AI 매매', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          // 목록을 가리지 않도록 상단에 둔다 (기존 FAB 대체)
          TextButton.icon(
            onPressed: () => _openEditor(),
            icon: const Icon(Icons.add, size: 18),
            label: const Text('새 프로파일'),
            style: TextButton.styleFrom(
              foregroundColor: const Color(0xFF4FC3F7),
              textStyle: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
            ),
          ),
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loadProfiles),
        ],
      ),
      body: Column(children: [
        MarketTabBar(market: _market, onChanged: (m) => setState(() => _market = m)),
        Expanded(child: _loading && _profiles.isEmpty
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadProfiles,
              child: _filtered.isEmpty
                  ? ListView(children: [
                      const SizedBox(height: 200),
                      Center(
                        child: Text('${_market == 'OVERSEAS' ? '해외' : '국내'} 프로파일이 없습니다.\n새 프로파일을 만들어 보세요.',
                            textAlign: TextAlign.center, style: const TextStyle(color: Colors.grey)),
                      ),
                    ])
                  : ListView.builder(
                      padding: const EdgeInsets.fromLTRB(12, 12, 12, 90),
                      itemCount: _filtered.length,
                      itemBuilder: (context, i) {
                        final p = _filtered[i];
                        final target = p['last_ticker_name'] ?? p['last_ticker'];
                        return Card(
                          color: const Color(0xFF161B22),
                          margin: const EdgeInsets.only(bottom: 10),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                          child: ListTile(
                            onTap: () => _openEditor(p),
                            title: Text(p['name'] ?? '',
                                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                            subtitle: Padding(
                              padding: const EdgeInsets.only(top: 6),
                              child: Row(children: [
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: _statusColor(p['last_status']).withValues(alpha: 0.15),
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                  child: Text(_statusLabel(p['last_status']),
                                      style: TextStyle(fontSize: 11, color: _statusColor(p['last_status']))),
                                ),
                                const SizedBox(width: 8),
                                if (target != null)
                                  Expanded(
                                    child: Text('$target',
                                        style: const TextStyle(fontSize: 11, color: Colors.grey),
                                        overflow: TextOverflow.ellipsis),
                                  ),
                              ]),
                            ),
                            trailing: IconButton(
                              icon: const Icon(Icons.delete_outline, color: Colors.redAccent, size: 20),
                              onPressed: () => _deleteProfile(p),
                            ),
                          ),
                        );
                      },
                    ),
            ),
        ),
      ]),
    );
  }
}

/// 프로파일 편집 + 종목 선택 + 전략 요청 + 결과 화면
class AiTradeEditorScreen extends StatefulWidget {
  final Map<String, dynamic>? profile;
  final String market; // 새 프로파일 생성 시 사용할 시장 구분
  const AiTradeEditorScreen({super.key, this.profile, this.market = 'DOMESTIC'});

  @override
  State<AiTradeEditorScreen> createState() => _AiTradeEditorScreenState();
}

class _AiTradeEditorScreenState extends State<AiTradeEditorScreen> {
  static const _fallbackModels = [
    {'id': 'claude-fable-5', 'label': 'Fable 5 (최고 성능)'},
    {'id': 'claude-opus-5', 'label': 'Opus 5'},
    {'id': 'claude-sonnet-5', 'label': 'Sonnet 5'},
    {'id': 'claude-haiku-4-5', 'label': 'Haiku 4.5 (빠름/저비용)'},
  ];

  late TextEditingController _nameCtrl;
  late TextEditingController _promptCtrl;
  late TextEditingController _manualTickerCtrl;
  int? _profileId;
  List<Map<String, dynamic>> _models = List<Map<String, dynamic>>.from(_fallbackModels);
  List<Map<String, dynamic>> _pickStocks = [];  // AI 종목 선별 결과 (수익률 내림차순)
  String _model = 'claude-opus-5';
  int? _selectedProfileId;  // 선택한 AI 종목 프로파일
  String? _selectedTicker;
  String? _pendingTicker;   // 복원 대상 (종목 목록 로드 후 적용)
  Map<String, dynamic>? _result;
  bool _running = false;
  bool _saving = false;
  bool _showChart = false;   // 가격대 전략 그래프 표시 여부
  bool _exportingSheet = false;
  String? _gsheetUrl;
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    _profileId = widget.profile?['id'];
    _nameCtrl = TextEditingController(text: widget.profile?['name'] ?? '');
    _promptCtrl = TextEditingController(text: widget.profile?['prompt'] ?? '');
    _model = widget.profile?['model'] ?? 'claude-opus-5';
    // 이전 실행 종목은 AI 종목 목록 로드 후 복원 (목록에 있으면 드롭다운, 없으면 직접 입력)
    _pendingTicker = widget.profile?['last_ticker'] as String?;
    _manualTickerCtrl = TextEditingController(text: _pendingTicker ?? '');
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadModels();
      _loadPickStocks();
      if (_profileId != null) _loadResult();
    });
  }

  Future<void> _loadPickStocks() async {
    try {
      final res = await context.read<TradingProvider>().api.getAiPickStocks();
      if (!mounted) return;
      setState(() {
        _pickStocks = res.cast<Map<String, dynamic>>();
        // 이전 실행 종목이 목록에 있으면 그룹까지 함께 복원
        if (_pendingTicker != null) {
          var restored = false;
          for (final s in _pickStocks) {
            if (s['ticker'] == _pendingTicker) {
              _selectedProfileId = s['profile_id'] as int?;
              _selectedTicker = _pendingTicker;
              _manualTickerCtrl.text = '';
              restored = true;
              break;
            }
          }
          // AI 종목에 없으면 보유종목에서 찾아 복원
          if (!restored) {
            for (final h in _holdings) {
              if ('${h['ticker']}' == _pendingTicker) {
                _selectedProfileId = holdingsGroupId;
                _selectedTicker = _pendingTicker;
                _manualTickerCtrl.text = '';
                break;
              }
            }
          }
        }
        _pendingTicker = null;
      });
    } catch (_) {}
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _nameCtrl.dispose();
    _promptCtrl.dispose();
    _manualTickerCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadModels() async {
    try {
      final res = await context.read<TradingProvider>().api.getAiPickModels();
      final list = (res['models'] as List?)?.cast<Map<String, dynamic>>();
      if (list != null && list.isNotEmpty && mounted) {
        final serverDefault = (res['default'] ?? list.first['id']) as String;
        setState(() {
          _models = list;
          if (widget.profile == null || !_models.any((m) => m['id'] == _model)) {
            _model = serverDefault;
          }
        });
      }
    } catch (_) {}
  }

  /// 보유종목 그룹 식별자 (AI 종목 프로파일 id와 겹치지 않는 값)
  static const int holdingsGroupId = -1;

  bool get _isHoldingsGroup => _selectedProfileId == holdingsGroupId;

  List<Map<String, dynamic>> get _holdings =>
      context.read<TradingProvider>().holdings;

  /// 수수료·세금이 반영된 평가손익 기준 수익률 (서버 ratio와 동일 기준)
  static double _holdingRate(Map<String, dynamic> h) {
    final cost = ((h['buy_price'] as num?)?.toDouble() ?? 0) *
        ((h['qty'] as num?)?.toDouble() ?? 0);
    if (cost > 0) return ((h['profit'] as num?)?.toDouble() ?? 0) / cost * 100;
    return (h['ratio'] as num?)?.toDouble() ?? 0;
  }

  /// 보유종목을 종목 목록 형태로 변환 (수익률을 upside 자리에 표시)
  List<Map<String, dynamic>> get _holdingStocks => _holdings.map((h) {
        final rate = _holdingRate(h);
        return {
          'ticker': '${h['ticker']}',
          'name': h['name'] ?? h['ticker'],
          'upside': '${rate >= 0 ? '+' : ''}${rate.toStringAsFixed(1)}%',
        };
      }).toList();

  /// 선택한 종목의 보유 정보 (보유 중이 아니면 null)
  Map<String, dynamic>? get _selectedHolding {
    final t = _effectiveTicker;
    if (t.isEmpty) return null;
    for (final h in _holdings) {
      if ('${h['ticker']}' == t) return h;
    }
    return null;
  }

  /// AI 종목 프로파일 목록 (id / name / 종목 수)
  List<Map<String, dynamic>> get _pickProfiles {
    final seen = <int, Map<String, dynamic>>{};
    for (final s in _pickStocks) {
      final id = s['profile_id'] as int?;
      if (id == null) continue;
      final g = seen.putIfAbsent(
          id, () => {'id': id, 'name': s['profile_name'] ?? '', 'count': 0});
      g['count'] = (g['count'] as int) + 1;
    }
    return seen.values.toList();
  }

  /// 선택한 그룹의 종목 (AI 종목은 서버에서 수익률 내림차순 정렬됨)
  List<Map<String, dynamic>> get _profileStocks => _isHoldingsGroup
      ? _holdingStocks
      : _pickStocks.where((s) => s['profile_id'] == _selectedProfileId).toList();

  String get _effectiveTicker =>
      _selectedTicker ?? _manualTickerCtrl.text.trim();

  String get _effectiveTickerName {
    if (_selectedTicker != null) {
      for (final s in _pickStocks) {
        if (s['ticker'] == _selectedTicker) return (s['name'] ?? '') as String;
      }
      for (final h in _holdings) {
        if ('${h['ticker']}' == _selectedTicker) return '${h['name'] ?? ''}';
      }
      return '';
    }
    final v = _manualTickerCtrl.text.trim();
    // 6자리 숫자면 종목코드, 아니면 종목명으로 간주
    return RegExp(r'^\d{6}$').hasMatch(v) ? '' : v;
  }

  void _toast(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), behavior: SnackBarBehavior.floating),
    );
  }

  Future<void> _loadResult() async {
    if (_profileId == null) return;
    try {
      final res = await context.read<TradingProvider>().api.getAiTradeResult(_profileId!);
      if (!mounted) return;
      if (res['status'] == 'NONE') {
        setState(() { _result = null; _running = false; });
        return;
      }
      setState(() {
        _result = res;
        _running = res['status'] == 'running';
      });
      if (_running) {
        _startPolling();
      } else {
        _pollTimer?.cancel();
      }
    } catch (_) {}
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 3), (_) => _loadResult());
  }

  Future<bool> _save({bool silent = false}) async {
    final name = _nameCtrl.text.trim();
    final prompt = _promptCtrl.text.trim();
    if (name.isEmpty || prompt.isEmpty) {
      _toast('이름과 프롬프트를 모두 입력하세요.');
      return false;
    }
    setState(() => _saving = true);
    try {
      final api = context.read<TradingProvider>().api;
      // 시장 구분: 기존 프로파일은 저장된 값, 새 프로파일은 현재 탭의 값
      final market = widget.profile?['market'] as String? ?? widget.market;
      final res = _profileId == null
          ? await api.createAiTrade(name, prompt, _model, market: market)
          : await api.updateAiTrade(_profileId!, name, prompt, _model, market: market);
      if (res['status'] != 'SUCCESS') {
        _toast('저장 실패: ${res['message']}');
        return false;
      }
      _profileId ??= res['id'];
      if (!silent) _toast('저장되었습니다. (웹과 동기화됨)');
      return true;
    } catch (e) {
      _toast('저장 오류: $e');
      return false;
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _run() async {
    if (_effectiveTicker.isEmpty) {
      _toast('대상 종목을 선택하거나 직접 입력하세요.');
      return;
    }
    final ticker = _effectiveTicker;
    final tickerName = _effectiveTickerName;
    if (!await _save(silent: true)) return;
    if (!mounted) return;
    try {
      final res = await context.read<TradingProvider>().api
          .runAiTrade(_profileId!, ticker, tickerName);
      if (res['status'] == 'ERROR') {
        _toast('실행 실패: ${res['message']}');
        return;
      }
      setState(() {
        _running = true;
        _showChart = false;
        _gsheetUrl = null;
        _result = {'status': 'running', 'ticker': ticker, 'ticker_name': tickerName};
      });
      _startPolling();
    } catch (e) {
      _toast('실행 오류: $e');
    }
  }

  /// 매매 전략을 구글 시트에 업로드 (탭 = 프로파일명, 같은 종목이면 해당 행 갱신)
  Future<void> _exportStrategy() async {
    if (_profileId == null || _exportingSheet) return;
    setState(() => _exportingSheet = true);
    try {
      final res = await context
          .read<TradingProvider>()
          .api
          .exportAiTradeToGSheet(_profileId!);
      if (!mounted) return;
      if (res['status'] == 'SUCCESS') {
        setState(() => _gsheetUrl = res['url'] as String?);
        final action = res['updated'] == true ? '갱신' : '추가';
        _toast("구글 시트 '${res['sheet']}' 탭에 "
            "${res['ticker_name'] ?? res['ticker']} 전략을 $action했습니다.");
      } else {
        _toast('업로드 실패: ${res['message'] ?? '알 수 없는 오류'}');
      }
    } catch (e) {
      _toast('업로드 오류: $e');
    } finally {
      if (mounted) setState(() => _exportingSheet = false);
    }
  }

  Future<void> _openGSheet() async {
    final url = _gsheetUrl;
    if (url == null) return;
    try {
      await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
    } catch (e) {
      _toast('시트를 열 수 없습니다: $e');
    }
  }

  String _won(dynamic v) {
    final n = (v is num) ? v.toInt() : 0;
    return '${n.toString().replaceAllMapped(RegExp(r'(\d)(?=(\d{3})+(?!\d))'), (m) => '${m[1]},')}원';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      appBar: AppBar(
        backgroundColor: const Color(0xFF161B22),
        title: Text(_profileId == null ? '새 프로파일' : '프로파일 편집',
            style: const TextStyle(fontWeight: FontWeight.bold)),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _nameCtrl,
            decoration: const InputDecoration(
              labelText: '프로파일 명칭',
              hintText: '예: 단기_스윙전략',
              border: OutlineInputBorder(),
            ),
            style: const TextStyle(color: Colors.white),
          ),
          const SizedBox(height: 12),

          // 1단계: 종목 그룹 선택 (보유종목 / AI 종목 프로파일)
          DropdownButtonFormField<int?>(
            initialValue: (_isHoldingsGroup && _holdings.isNotEmpty) ||
                    _pickProfiles.any((g) => g['id'] == _selectedProfileId)
                ? _selectedProfileId
                : null,
            dropdownColor: const Color(0xFF161B22),
            isExpanded: true,
            decoration: const InputDecoration(
              labelText: '종목 그룹',
              border: OutlineInputBorder(),
            ),
            style: const TextStyle(color: Colors.white, fontSize: 14),
            items: [
              const DropdownMenuItem<int?>(value: null, child: Text('— 직접 입력 —')),
              if (_holdings.isNotEmpty)
                DropdownMenuItem<int?>(
                  value: holdingsGroupId,
                  child: Text('💼 보유종목 (${_holdings.length}종목)',
                      overflow: TextOverflow.ellipsis),
                ),
              for (final g in _pickProfiles)
                DropdownMenuItem<int?>(
                  value: g['id'] as int,
                  child: Text('${g['name']} (${g['count']}종목)', overflow: TextOverflow.ellipsis),
                ),
            ],
            onChanged: (v) => setState(() {
              _selectedProfileId = v;
              _selectedTicker = null;   // 그룹 변경 시 종목 초기화
            }),
          ),
          if (_pickStocks.isEmpty)
            const Padding(
              padding: EdgeInsets.only(top: 6),
              child: Text('⚠️ AI 종목에서 선별된 종목이 없습니다. AI 종목 탭에서 먼저 실행하거나 직접 입력하세요.',
                  style: TextStyle(color: Colors.amber, fontSize: 11.5)),
            ),

          // 2단계: 해당 프로파일의 종목 (수익률 높은 순)
          if (_selectedProfileId != null) ...[
            const SizedBox(height: 10),
            DropdownButtonFormField<String?>(
              initialValue:
                  _profileStocks.any((s) => s['ticker'] == _selectedTicker) ? _selectedTicker : null,
              dropdownColor: const Color(0xFF161B22),
              isExpanded: true,
              decoration: InputDecoration(
                labelText: _isHoldingsGroup ? '대상 종목 (보유종목)' : '대상 종목 (수익률 높은 순)',
                border: const OutlineInputBorder(),
              ),
              style: const TextStyle(color: Colors.white, fontSize: 14),
              items: [
                const DropdownMenuItem<String?>(value: null, child: Text('— 종목 선택 —')),
                for (var i = 0; i < _profileStocks.length; i++)
                  DropdownMenuItem<String?>(
                    value: _profileStocks[i]['ticker'] as String,
                    child: Text(
                      '${!_isHoldingsGroup && i == 0 ? '🥇 ' : ''}${_profileStocks[i]['name']} (${_profileStocks[i]['ticker']})'
                      '${(_profileStocks[i]['upside'] ?? '').toString().isNotEmpty ? ' · ${_profileStocks[i]['upside']}' : ''}',
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
              ],
              onChanged: (v) => setState(() => _selectedTicker = v),
            ),
          ],
          // 선택한 종목을 보유 중이면 현재 보유 현황 표시
          if (_selectedHolding != null) ...[
            const SizedBox(height: 10),
            _holdingCard(_selectedHolding!),
          ],
          if (_selectedProfileId == null) ...[
            const SizedBox(height: 10),
            TextField(
              controller: _manualTickerCtrl,
              decoration: const InputDecoration(
                labelText: '종목 직접 입력',
                hintText: '종목명 또는 6자리 코드',
                border: OutlineInputBorder(),
              ),
              style: const TextStyle(color: Colors.white),
              onChanged: (_) => setState(() {}),
            ),
          ],
          const SizedBox(height: 12),

          DropdownButtonFormField<String>(
            initialValue: _models.any((m) => m['id'] == _model) ? _model : null,
            dropdownColor: const Color(0xFF161B22),
            decoration: const InputDecoration(
              labelText: '실행 AI 모델',
              border: OutlineInputBorder(),
            ),
            style: const TextStyle(color: Colors.white, fontSize: 14),
            items: [
              for (final m in _models)
                DropdownMenuItem(value: m['id'] as String, child: Text(m['label'] as String)),
            ],
            onChanged: (v) => setState(() => _model = v ?? _model),
          ),
          const SizedBox(height: 12),

          TextField(
            controller: _promptCtrl,
            maxLines: 6,
            decoration: const InputDecoration(
              labelText: '매매 전략 프롬프트',
              hintText: '선택한 종목을 어떻게 매매할지 AI에게 물어볼 내용을 입력하세요',
              border: OutlineInputBorder(),
              alignLabelWithHint: true,
            ),
            style: const TextStyle(color: Color(0xFF7EE8FA), fontSize: 14, height: 1.5),
          ),
          const SizedBox(height: 14),

          Row(children: [
            Expanded(
              child: OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white70,
                  side: const BorderSide(color: Colors.white30),
                  padding: const EdgeInsets.symmetric(vertical: 12),
                ),
                onPressed: _saving ? null : () => _save(),
                icon: const Icon(Icons.save, size: 18),
                label: const Text('저장'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF00A8CC),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                ),
                onPressed: _running ? null : _run,
                icon: _running
                    ? const SizedBox(width: 14, height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white70))
                    : const Icon(Icons.play_arrow, size: 20),
                label: Text(_running ? '분석 중...' : '전략 요청',
                    style: const TextStyle(fontWeight: FontWeight.bold)),
              ),
            ),
          ]),
          const SizedBox(height: 20),
          if (_result != null) _buildResult(),
        ],
      ),
    );
  }

  Widget _buildResult() {
    final status = _result!['status'];
    final s = _result!['strategy'] as Map<String, dynamic>?;
    final target = _result!['ticker_name'] ?? _result!['ticker'] ?? '';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Expanded(
              child: Text('📈 매매 전략 — $target',
                  style: const TextStyle(
                      color: Color(0xFF00D084), fontWeight: FontWeight.bold, fontSize: 15),
                  overflow: TextOverflow.ellipsis),
            ),
            if (_result!['finished_at'] != null)
              Text('${_result!['finished_at']}',
                  style: const TextStyle(color: Colors.grey, fontSize: 11)),
          ],
        ),
        const SizedBox(height: 10),
        if (status == 'running')
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 24),
            child: Center(
              child: Column(children: [
                CircularProgressIndicator(),
                SizedBox(height: 12),
                Text('AI가 매매 전략을 분석하는 중입니다... (최대 15분)',
                    style: TextStyle(color: Colors.grey, fontSize: 13)),
              ]),
            ),
          )
        else if (status == 'error')
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.redAccent.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: Colors.redAccent.withValues(alpha: 0.4)),
            ),
            child: Text('⚠️ ${_result!['error']}',
                style: const TextStyle(color: Colors.redAccent, fontSize: 13)),
          )
        else if (status == 'done' && s != null) ...[
          Card(
            color: const Color(0xFF161B22),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    Expanded(
                      child: Text('${s['name']} (${s['ticker']})',
                          style: const TextStyle(
                              color: Colors.white, fontWeight: FontWeight.bold, fontSize: 15),
                          overflow: TextOverflow.ellipsis),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: _riskColor(s['risk_level']).withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text('리스크 ${s['risk_level']}',
                          style: TextStyle(fontSize: 11, color: _riskColor(s['risk_level']))),
                    ),
                  ]),
                  if ((s['summary'] ?? '').toString().isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Text(s['summary'],
                        style: const TextStyle(color: Colors.white70, fontSize: 13, height: 1.5)),
                  ],
                  // 가격대별 매매 전략 그래프
                  if (buildChartLevels(s) != null) ...[
                    const SizedBox(height: 10),
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton.icon(
                        style: OutlinedButton.styleFrom(
                          foregroundColor: const Color(0xFF00D084),
                          side: const BorderSide(color: Color(0xFF00D084)),
                          padding: const EdgeInsets.symmetric(vertical: 10),
                        ),
                        onPressed: () => setState(() => _showChart = !_showChart),
                        icon: const Icon(Icons.show_chart, size: 18),
                        label: Text(_showChart ? '📈 그래프 닫기' : '📈 그래프',
                            style: const TextStyle(fontWeight: FontWeight.bold)),
                      ),
                    ),
                    if (_showChart) ...[
                      const SizedBox(height: 10),
                      _priceChart(buildChartLevels(s)!),
                    ],
                  ],
                  // 구글 시트 업로드 (탭 = 프로파일명, 같은 종목이면 갱신)
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 4,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      OutlinedButton.icon(
                        onPressed: _exportingSheet ? null : _exportStrategy,
                        icon: _exportingSheet
                            ? const SizedBox(
                                width: 14, height: 14,
                                child: CircularProgressIndicator(strokeWidth: 2))
                            : const Text('📗', style: TextStyle(fontSize: 14)),
                        label: Text(_exportingSheet ? '업로드 중...' : '구글 시트 업로드'),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: const Color(0xFF34A853),
                          side: const BorderSide(color: Color(0xFF34A853)),
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                          textStyle: const TextStyle(fontSize: 12.5),
                        ),
                      ),
                      if (_gsheetUrl != null)
                        TextButton(
                          onPressed: _openGSheet,
                          style: TextButton.styleFrom(
                            foregroundColor: const Color(0xFF4FC3F7),
                            padding: const EdgeInsets.symmetric(horizontal: 8),
                            textStyle: const TextStyle(fontSize: 12.5),
                          ),
                          child: const Text('시트 열기 ↗'),
                        ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  _metricRow('현재가', _won(s['current_price'])),
                  _metricRow('진입 가격대', '${s['entry_price']}', color: const Color(0xFF4FC3F7)),
                  _metricRow('목표가', _won(s['target_price']), color: const Color(0xFF00D084)),
                  _metricRow('손절가', _won(s['stop_loss']), color: Colors.redAccent),
                  _metricRow('기대 수익', '${s['expected_return']}', color: const Color(0xFF00D084)),
                  _metricRow('투자 비중', '${s['position_size']}'),
                  _metricRow('보유 기간', '${s['holding_period']}'),
                ],
              ),
            ),
          ),
          _condCard('✅ 매수 조건', s['buy_conditions'], const Color(0xFF00D084)),
          _condCard('🎯 매도 조건', s['sell_conditions'], const Color(0xFF4FC3F7)),
          _condCard('⚠️ 리스크 요인', s['risks'], Colors.redAccent),
          if ((s['reason'] ?? '').toString().isNotEmpty)
            Card(
              color: const Color(0xFF161B22),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('근거',
                        style: TextStyle(color: Color(0xFF00D084), fontWeight: FontWeight.bold, fontSize: 13)),
                    const SizedBox(height: 6),
                    Text(s['reason'],
                        style: const TextStyle(color: Colors.grey, fontSize: 12.5, height: 1.5)),
                  ],
                ),
              ),
            ),
          const Padding(
            padding: EdgeInsets.only(top: 8),
            child: Text('※ AI가 생성한 참고용 정보입니다. 투자 판단과 책임은 본인에게 있습니다.',
                style: TextStyle(color: Colors.grey, fontSize: 11)),
          ),
        ],
      ],
    );
  }

  /// 현재 보유 현황 카드
  Widget _holdingCard(Map<String, dynamic> h) {
    final qty = (h['qty'] as num?)?.toInt() ?? 0;
    final buy = (h['buy_price'] as num?)?.toDouble() ?? 0;
    final cur = (h['current_price'] as num?)?.toDouble() ?? 0;
    final cost = buy * qty;
    final profit = (h['profit'] as num?)?.toDouble() ?? 0;  // 수수료·세금 반영
    final rate = _holdingRate(h);
    final color = profit > 0
        ? const Color(0xFF00D084)
        : (profit < 0 ? Colors.redAccent : Colors.white);

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.amber.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.amber.withValues(alpha: 0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const Text('💼 현재 보유 중',
                style: TextStyle(color: Colors.amber, fontWeight: FontWeight.bold, fontSize: 13)),
            const SizedBox(width: 8),
            Expanded(
              child: Text('${h['name']} (${h['ticker']})',
                  style: const TextStyle(color: Colors.grey, fontSize: 12),
                  overflow: TextOverflow.ellipsis),
            ),
          ]),
          const SizedBox(height: 10),
          _metricRow('보유수량', '${_comma(qty)}주'),
          _metricRow('매입단가', _won(buy)),
          _metricRow('현재가', _won(cur)),
          _metricRow('매입금액', _won(cost)),
          _metricRow('평가손익', '${profit >= 0 ? '+' : ''}${_comma(profit.round())}원', color: color),
          _metricRow('수익률', '${rate >= 0 ? '+' : ''}${rate.toStringAsFixed(2)}%', color: color),
        ],
      ),
    );
  }

  String _comma(int n) => n.toString().replaceAllMapped(
      RegExp(r'(\d)(?=(\d{3})+$)'), (m) => '${m[1]},');

  Widget _priceChart(Map<String, dynamic> data) {
    final rr = data['rr'] as double?;
    final rrColor = rr == null
        ? Colors.grey
        : (rr >= 2 ? const Color(0xFF00D084) : (rr >= 1 ? Colors.amber : Colors.redAccent));
    return Container(
      padding: const EdgeInsets.fromLTRB(8, 12, 8, 8),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.25),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
      ),
      child: Column(
        children: [
          SizedBox(
            height: 240,
            width: double.infinity,
            child: CustomPaint(painter: PriceLevelPainter(data)),
          ),
          const SizedBox(height: 8),
          const Divider(height: 1, color: Colors.white12),
          const SizedBox(height: 8),
          Row(
            children: [
              const Expanded(
                child: Wrap(spacing: 12, runSpacing: 4, children: [
                  _LegendDot(color: Color(0xFF00D084), label: '목표가'),
                  _LegendDot(color: Color(0xFF00A8CC), label: '진입 가격대'),
                  _LegendDot(color: Colors.white, label: '현재가'),
                  _LegendDot(color: Colors.redAccent, label: '손절가'),
                ]),
              ),
              if (rr != null)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                  decoration: BoxDecoration(
                    color: rrColor.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text('손익비 ${rr.toStringAsFixed(1)} : 1',
                      style: TextStyle(color: rrColor, fontSize: 11, fontWeight: FontWeight.bold)),
                ),
            ],
          ),
        ],
      ),
    );
  }

  Color _riskColor(dynamic lv) => switch (lv) {
        '낮음' => const Color(0xFF00D084),
        '높음' => Colors.redAccent,
        _ => Colors.amber,
      };

  Widget _metricRow(String label, String value, {Color? color}) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label, style: const TextStyle(color: Colors.grey, fontSize: 12.5)),
            Flexible(
              child: Text(value,
                  textAlign: TextAlign.right,
                  style: TextStyle(
                      color: color ?? Colors.white, fontSize: 13, fontWeight: FontWeight.w600)),
            ),
          ],
        ),
      );

  Widget _condCard(String title, dynamic items, Color color) {
    final list = (items as List?) ?? [];
    if (list.isEmpty) return const SizedBox.shrink();
    return Card(
      color: const Color(0xFF161B22),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 13)),
            const SizedBox(height: 8),
            for (final c in list)
              Padding(
                padding: const EdgeInsets.only(bottom: 5),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('• ', style: TextStyle(color: color, fontSize: 12.5)),
                  Expanded(
                    child: Text('$c',
                        style: const TextStyle(color: Colors.grey, fontSize: 12.5, height: 1.5)),
                  ),
                ]),
              ),
          ],
        ),
      ),
    );
  }
}

/// 범례 항목 (색상 막대 + 라벨)
class _LegendDot extends StatelessWidget {
  final Color color;
  final String label;
  const _LegendDot({required this.color, required this.label});

  @override
  Widget build(BuildContext context) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 12,
            height: 3,
            decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(2)),
          ),
          const SizedBox(width: 5),
          Text(label, style: const TextStyle(color: Colors.grey, fontSize: 11)),
        ],
      );
}

/// 가격 레벨(목표가/진입대/현재가/손절가)을 세로 축에 그리는 페인터
class PriceLevelPainter extends CustomPainter {
  final Map<String, dynamic> data;
  PriceLevelPainter(this.data);

  static const _padL = 66.0;   // 좌측 가격 라벨 영역
  static const _padR = 96.0;   // 우측 레벨명 영역
  static const _padV = 18.0;

  @override
  void paint(Canvas canvas, Size size) {
    final levels = (data['levels'] as List).cast<Map<String, dynamic>>();
    final minP = data['min'] as double, maxP = data['max'] as double;
    if (maxP <= minP) return;

    final plotH = size.height - _padV * 2;
    final plotW = size.width - _padL - _padR;
    double y(double p) => _padV + (maxP - p) / (maxP - minP) * plotH;

    // 진입 가격대 밴드
    final entryTop = data['entryTop'] as double?;
    final entryBottom = data['entryBottom'] as double?;
    if (entryTop != null && entryBottom != null) {
      final top = y(entryTop);
      final h = math.max(y(entryBottom) - top, 2.0);
      final rect = Rect.fromLTWH(_padL, top, plotW, h);
      canvas.drawRect(rect, Paint()..color = const Color(0xFF00A8CC).withValues(alpha: 0.13));
      canvas.drawRect(
          rect,
          Paint()
            ..color = const Color(0xFF00A8CC).withValues(alpha: 0.5)
            ..style = PaintingStyle.stroke
            ..strokeWidth = 1);
    }

    for (final lv in levels) {
      final price = lv['price'] as double;
      final color = lv['color'] as Color;
      final isCurrent = lv['label'] == '현재가';
      final ly = y(price);

      final paint = Paint()
        ..color = color
        ..strokeWidth = isCurrent ? 2 : 1.6;
      if (isCurrent) {
        // 현재가는 점선
        const dash = 6.0, gap = 4.0;
        for (var x = _padL; x < size.width - _padR; x += dash + gap) {
          canvas.drawLine(
              Offset(x, ly), Offset(math.min(x + dash, size.width - _padR), ly), paint);
        }
      } else {
        canvas.drawLine(Offset(_padL, ly), Offset(size.width - _padR, ly), paint);
      }

      // 좌측: 가격
      _text(canvas, _fmt(price), Offset(_padL - 6, ly), color, 11,
          align: TextAlign.right, anchorRight: true, bold: true);
      // 우측: 레벨명 + 등락률
      final diff = (lv['diff'] ?? '') as String;
      _text(canvas, diff.isEmpty ? '${lv['label']}' : '${lv['label']} $diff',
          Offset(size.width - _padR + 6, ly), color, 10.5);
    }
  }

  void _text(Canvas canvas, String s, Offset at, Color color, double size,
      {TextAlign align = TextAlign.left, bool anchorRight = false, bool bold = false}) {
    final tp = TextPainter(
      text: TextSpan(
          text: s,
          style: TextStyle(
              color: color, fontSize: size, fontWeight: bold ? FontWeight.bold : FontWeight.normal)),
      textAlign: align,
      textDirection: TextDirection.ltr,
    )..layout();
    final dx = anchorRight ? at.dx - tp.width : at.dx;
    tp.paint(canvas, Offset(dx, at.dy - tp.height / 2));
  }

  static String _fmt(double v) => v
      .toInt()
      .toString()
      .replaceAllMapped(RegExp(r'(\d)(?=(\d{3})+$)'), (m) => '${m[1]},');

  @override
  bool shouldRepaint(covariant PriceLevelPainter old) => old.data != data;
}
