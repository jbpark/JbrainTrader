import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../providers/trading_provider.dart';
import '../widgets/market_tab_bar.dart';

/// AI 캘린더 — 날짜별 주요 일정과 관련 종목, 일정 기반 매매 타이밍
/// (웹 AI 캘린더 탭과 동일 API 사용, 자동 동기화)
class AiCalendarScreen extends StatefulWidget {
  const AiCalendarScreen({super.key});

  @override
  State<AiCalendarScreen> createState() => _AiCalendarScreenState();
}

class _AiCalendarScreenState extends State<AiCalendarScreen> {
  List<Map<String, dynamic>> _profiles = [];
  bool _loading = true;
  String _market = 'DOMESTIC'; // 국내/해외 탭

  List<Map<String, dynamic>> get _filtered =>
      _profiles.where((p) => MarketUtil.of(p) == _market).toList();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadProfiles());
  }

  Future<void> _loadProfiles() async {
    try {
      final list = await context.read<TradingProvider>().api.getAiCalendars();
      if (!mounted) return;
      setState(() {
        _profiles = list.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _loading = false);
      _toast('프로파일 조회 실패: $e');
    }
  }

  void _toast(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), behavior: SnackBarBehavior.floating),
    );
  }

  Future<void> _openDetail([Map<String, dynamic>? profile]) async {
    await Navigator.push(context, MaterialPageRoute(
      builder: (_) => AiCalendarDetailScreen(profile: profile, market: _market),
    ));
    _loadProfiles();
  }

  Future<void> _confirmDelete(Map<String, dynamic> p) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF161B22),
        title: const Text('프로파일 삭제', style: TextStyle(color: Colors.white)),
        content: Text("'${p['name']}' 프로파일을 삭제할까요?",
            style: const TextStyle(color: Colors.white70)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false),
              child: const Text('취소', style: TextStyle(color: Colors.grey))),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Colors.redAccent),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('삭제'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    await context.read<TradingProvider>().api.deleteAiCalendar(p['id'] as int);
    _toast('삭제되었습니다.');
    _loadProfiles();
  }

  static String _statusLabel(dynamic s) => switch ('$s') {
        'done' => '완료',
        'running' => '실행 중',
        'error' => '오류',
        _ => '미실행',
      };

  static Color _statusColor(dynamic s) => switch ('$s') {
        'done' => const Color(0xFF00D084),
        'running' => Colors.amber,
        'error' => Colors.redAccent,
        _ => Colors.grey,
      };

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      appBar: AppBar(
        backgroundColor: const Color(0xFF161B22),
        title: const Text('AI캘린더', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          TextButton.icon(
            onPressed: () => _openDetail(),
            icon: const Icon(Icons.add, size: 18),
            label: const Text('새 프로파일'),
            style: TextButton.styleFrom(
              foregroundColor: const Color(0xFFFFB74D),
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
              child: ListView(
                padding: const EdgeInsets.all(12),
                children: [
                  if (_filtered.isEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 60),
                      child: Center(
                        child: Text('${_market == 'OVERSEAS' ? '해외' : '국내'} 프로파일이 없습니다.\n상단 + 새 프로파일로 추가하세요.',
                            textAlign: TextAlign.center,
                            style: const TextStyle(color: Colors.grey)),
                      ),
                    ),
                  for (final p in _filtered)
                    Card(
                      color: const Color(0xFF161B22),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      child: ListTile(
                        title: Text('${p['name']}',
                            style: const TextStyle(
                                color: Colors.white, fontWeight: FontWeight.bold)),
                        subtitle: Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: Row(children: [
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: _statusColor(p['last_status']).withValues(alpha: 0.15),
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Text(_statusLabel(p['last_status']),
                                  style: TextStyle(
                                      fontSize: 11, color: _statusColor(p['last_status']))),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text('${p['last_finished_at'] ?? ''}',
                                  style: const TextStyle(color: Colors.grey, fontSize: 11),
                                  overflow: TextOverflow.ellipsis),
                            ),
                          ]),
                        ),
                        trailing: IconButton(
                          icon: const Icon(Icons.delete_outline,
                              color: Colors.redAccent, size: 20),
                          onPressed: () => _confirmDelete(p),
                        ),
                        onTap: () => _openDetail(p),
                      ),
                    ),
                ],
              ),
            ),
        ),
      ]),
    );
  }
}

// ─────────────────────────────────────────────────────────────
/// 프로파일 편집 + 캘린더 결과
class AiCalendarDetailScreen extends StatefulWidget {
  final Map<String, dynamic>? profile;
  final String market; // 새 프로파일 생성 시 사용할 시장 구분
  const AiCalendarDetailScreen({super.key, this.profile, this.market = 'DOMESTIC'});

  @override
  State<AiCalendarDetailScreen> createState() => _AiCalendarDetailScreenState();
}

class _AiCalendarDetailScreenState extends State<AiCalendarDetailScreen> {
  static const _fallbackModels = [
    {'id': 'claude-fable-5', 'label': 'Fable 5 (최고 성능)'},
    {'id': 'claude-opus-5', 'label': 'Opus 5'},
    {'id': 'claude-sonnet-5', 'label': 'Sonnet 5'},
    {'id': 'claude-haiku-4-5', 'label': 'Haiku 4.5 (빠름/저비용)'},
  ];

  late TextEditingController _nameCtrl;
  late TextEditingController _promptCtrl;
  int? _profileId;
  List<Map<String, dynamic>> _models = List<Map<String, dynamic>>.from(_fallbackModels);
  String _model = 'claude-opus-5';
  Map<String, dynamic>? _result;
  bool _running = false;
  bool _saving = false;
  Timer? _pollTimer;

  DateTime _viewMonth = DateTime(DateTime.now().year, DateTime.now().month);
  String? _selectedDate;

  String get _todayStr => DateFormat('yyyy-MM-dd').format(DateTime.now());

  @override
  void initState() {
    super.initState();
    _profileId = widget.profile?['id'];
    _nameCtrl = TextEditingController(text: widget.profile?['name'] ?? '');
    _promptCtrl = TextEditingController(text: widget.profile?['prompt'] ?? '');
    _model = widget.profile?['model'] ?? 'claude-opus-5';
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadModels();
      if (_profileId != null) _loadResult();
    });
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _nameCtrl.dispose();
    _promptCtrl.dispose();
    super.dispose();
  }

  void _toast(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), behavior: SnackBarBehavior.floating),
    );
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

  Future<void> _loadResult() async {
    if (_profileId == null) return;
    try {
      final res = await context.read<TradingProvider>().api.getAiCalendarResult(_profileId!);
      if (!mounted) return;
      if (res['status'] == 'NONE') {
        setState(() { _result = null; _running = false; });
        return;
      }
      setState(() {
        _result = res;
        _running = res['status'] == 'running';
      });
      if (res['status'] == 'done' && _selectedDate == null) {
        final events = _events;
        if (events.isNotEmpty) {
          final next = events.firstWhere(
              (e) => '${e['date']}'.compareTo(_todayStr) >= 0,
              orElse: () => events.first);
          final d = DateTime.parse('${next['date']}');
          setState(() {
            _selectedDate = '${next['date']}';
            _viewMonth = DateTime(d.year, d.month);
          });
        }
      }
      if (_running) {
        _startPolling();
      } else {
        _pollTimer?.cancel();
      }
    } catch (_) {}
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 5), (_) => _loadResult());
  }

  List<Map<String, dynamic>> get _events =>
      ((_result?['events'] as List?) ?? const [])
          .whereType<Map>()
          .map((e) => Map<String, dynamic>.from(e))
          .toList();

  List<Map<String, dynamic>> get _watchlist =>
      ((_result?['watchlist'] as List?) ?? const [])
          .whereType<Map>()
          .map((e) => Map<String, dynamic>.from(e))
          .toList();

  List<Map<String, dynamic>> get _upsideStocks =>
      ((_result?['upside_stocks'] as List?) ?? const [])
          .whereType<Map>()
          .map((e) => Map<String, dynamic>.from(e))
          .toList();

  Map<String, List<Map<String, dynamic>>> get _eventsByDate {
    final map = <String, List<Map<String, dynamic>>>{};
    for (final e in _events) {
      (map['${e['date']}'] ??= []).add(e);
    }
    return map;
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
          ? await api.createAiCalendar(name, prompt, _model, market: market)
          : await api.updateAiCalendar(_profileId!, name, prompt, _model, market: market);
      if (res['status'] != 'SUCCESS') {
        _toast('저장 실패: ${res['message']}');
        return false;
      }
      _profileId ??= res['id'] as int?;
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
    if (!await _save(silent: true)) return;
    if (!mounted || _profileId == null) return;
    try {
      final res = await context.read<TradingProvider>().api.runAiCalendar(_profileId!);
      if (res['status'] == 'ERROR') {
        _toast('실행 실패: ${res['message']}');
        return;
      }
      setState(() {
        _running = true;
        _result = {'status': 'running', 'events': [], 'watchlist': []};
        _selectedDate = null;
      });
      _startPolling();
    } catch (e) {
      _toast('실행 오류: $e');
    }
  }

  static Color _impColor(dynamic v) => switch ('$v') {
        '높음' => Colors.redAccent,
        '낮음' => Colors.grey,
        _ => Colors.amber,
      };

  static Color _impactColor(dynamic v) => switch ('$v') {
        '긍정' => const Color(0xFF00D084),
        '부정' => Colors.redAccent,
        _ => Colors.grey,
      };

  String _won(dynamic v) => v is num
      ? '${NumberFormat('#,###', 'ko_KR').format(v.round())}원'
      : '-';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      appBar: AppBar(
        backgroundColor: const Color(0xFF161B22),
        title: const Text('캘린더 프로파일', style: TextStyle(fontWeight: FontWeight.bold)),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _nameCtrl,
            style: const TextStyle(color: Colors.white),
            decoration: _dec('프로파일 명칭'),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            initialValue: _models.any((m) => m['id'] == _model) ? _model : null,
            dropdownColor: const Color(0xFF161B22),
            style: const TextStyle(color: Colors.white),
            decoration: _dec('실행 AI 모델'),
            items: [
              for (final m in _models)
                DropdownMenuItem(value: m['id'] as String, child: Text('${m['label']}')),
            ],
            onChanged: (v) => setState(() => _model = v ?? _model),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _promptCtrl,
            style: const TextStyle(color: Color(0xFF9ECBFF), height: 1.5),
            maxLines: 6,
            decoration: _dec('일정 분석 프롬프트'),
          ),
          const SizedBox(height: 14),
          Row(children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _saving ? null : () => _save(),
                icon: const Icon(Icons.save, size: 18),
                label: const Text('저장'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white70,
                  side: const BorderSide(color: Colors.white24),
                  padding: const EdgeInsets.symmetric(vertical: 12),
                ),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: FilledButton.icon(
                onPressed: _running ? null : _run,
                icon: _running
                    ? const SizedBox(width: 14, height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.play_arrow, size: 18),
                label: Text(_running ? '분석 중...' : '캘린더 생성'),
                style: FilledButton.styleFrom(
                  backgroundColor: const Color(0xFFFFB74D),
                  foregroundColor: Colors.black,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                ),
              ),
            ),
          ]),
          const SizedBox(height: 20),
          if (_result != null) ..._buildResult(),
        ],
      ),
    );
  }

  InputDecoration _dec(String label) => InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: Colors.grey),
        filled: true,
        fillColor: const Color(0xFF161B22),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: Colors.white12),
        ),
      );

  List<Widget> _buildResult() {
    final status = _result!['status'];
    if (status == 'running') {
      return const [
        Padding(
          padding: EdgeInsets.symmetric(vertical: 30),
          child: Center(child: Column(children: [
            CircularProgressIndicator(),
            SizedBox(height: 12),
            Text('일정과 관련 종목을 조사하는 중입니다... (최대 15분)',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey, fontSize: 13)),
          ])),
        ),
      ];
    }
    if (status == 'error') {
      return [
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
        ),
      ];
    }
    if (status != 'done') return const [];

    return [
      Row(children: [
        const Text('🗓 주요 일정',
            style: TextStyle(color: Color(0xFFFFB74D),
                fontWeight: FontWeight.bold, fontSize: 15)),
        const Spacer(),
        Flexible(
          child: Text('${_result!['finished_at'] ?? ''}',
              style: const TextStyle(color: Colors.grey, fontSize: 11),
              overflow: TextOverflow.ellipsis),
        ),
      ]),
      const SizedBox(height: 10),
      _buildCalendar(),
      const SizedBox(height: 16),
      _buildDayDetail(),
      const SizedBox(height: 20),
      const Text('📈 상승 기대 종목',
          style: TextStyle(color: Color(0xFF00D084),
              fontWeight: FontWeight.bold, fontSize: 15)),
      const Padding(
        padding: EdgeInsets.only(top: 2, bottom: 8),
        child: Text('앞으로의 일정에서 긍정 영향을 받는 종목',
            style: TextStyle(color: Colors.grey, fontSize: 11.5)),
      ),
      if (_upsideStocks.isEmpty)
        const Padding(
          padding: EdgeInsets.only(bottom: 12),
          child: Text('남은 일정 중 긍정 영향으로 지목된 종목이 없습니다.',
              style: TextStyle(color: Colors.grey, fontSize: 12.5)),
        ),
      for (var i = 0; i < _upsideStocks.length; i++)
        _buildUpsideCard(i + 1, _upsideStocks[i]),
      const SizedBox(height: 20),
      const Text('🎯 일정 기반 관심 종목 · 매매 타이밍',
          style: TextStyle(color: Color(0xFF4FC3F7),
              fontWeight: FontWeight.bold, fontSize: 15)),
      const SizedBox(height: 10),
      ..._watchlist.map(_buildWatchCard),
      if (_watchlist.isEmpty)
        const Padding(
          padding: EdgeInsets.symmetric(vertical: 16),
          child: Text('관심 종목이 없습니다.', style: TextStyle(color: Colors.grey, fontSize: 13)),
        ),
      const Padding(
        padding: EdgeInsets.only(top: 12),
        child: Text('※ AI가 생성한 참고용 정보입니다. 일정은 변경될 수 있으니 원문 공시를 확인하세요.',
            style: TextStyle(color: Colors.grey, fontSize: 11, height: 1.4)),
      ),
    ];
  }

  Widget _buildCalendar() {
    final byDate = _eventsByDate;
    final first = DateTime(_viewMonth.year, _viewMonth.month, 1);
    final daysInMonth = DateTime(_viewMonth.year, _viewMonth.month + 1, 0).day;
    final cells = <Widget>[];

    for (var i = 0; i < first.weekday % 7; i++) {
      cells.add(const SizedBox.shrink());
    }
    for (var d = 1; d <= daysInMonth; d++) {
      final date = '${_viewMonth.year}-'
          '${_viewMonth.month.toString().padLeft(2, '0')}-'
          '${d.toString().padLeft(2, '0')}';
      final evs = byDate[date] ?? const [];
      final isToday = date == _todayStr;
      final isOn = date == _selectedDate;
      cells.add(InkWell(
        onTap: () => setState(() => _selectedDate = date),
        child: Container(
          decoration: BoxDecoration(
            color: isOn
                ? const Color(0xFF4FC3F7).withValues(alpha: 0.18)
                : evs.isNotEmpty
                    ? const Color(0xFFFFB74D).withValues(alpha: 0.08)
                    : Colors.transparent,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: isOn
                  ? const Color(0xFF4FC3F7)
                  : isToday
                      ? const Color(0xFF00D084)
                      : Colors.transparent,
            ),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text('$d', style: TextStyle(
                  color: evs.isNotEmpty ? Colors.white : Colors.grey,
                  fontSize: 12.5,
                  fontWeight: evs.isNotEmpty ? FontWeight.bold : FontWeight.normal)),
              if (evs.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      for (final e in evs.take(3))
                        Container(
                          width: 5, height: 5,
                          margin: const EdgeInsets.symmetric(horizontal: 1),
                          decoration: BoxDecoration(
                            color: _impColor(e['importance']),
                            shape: BoxShape.circle,
                          ),
                        ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ));
    }

    return Column(children: [
      Row(children: [
        IconButton(
          icon: const Icon(Icons.chevron_left, color: Colors.white70),
          onPressed: () => setState(() =>
              _viewMonth = DateTime(_viewMonth.year, _viewMonth.month - 1)),
        ),
        Text('${_viewMonth.year}년 ${_viewMonth.month}월',
            style: const TextStyle(
                color: Colors.white, fontWeight: FontWeight.bold, fontSize: 15)),
        IconButton(
          icon: const Icon(Icons.chevron_right, color: Colors.white70),
          onPressed: () => setState(() =>
              _viewMonth = DateTime(_viewMonth.year, _viewMonth.month + 1)),
        ),
        const Spacer(),
        Text('일정 ${_events.length}건',
            style: const TextStyle(color: Colors.grey, fontSize: 11.5)),
      ]),
      Row(
        children: [
          for (final d in ['일', '월', '화', '수', '목', '금', '토'])
            Expanded(
              child: Center(
                child: Text(d, style: const TextStyle(color: Colors.grey, fontSize: 11)),
              ),
            ),
        ],
      ),
      const SizedBox(height: 4),
      GridView.count(
        crossAxisCount: 7,
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        mainAxisSpacing: 3,
        crossAxisSpacing: 3,
        childAspectRatio: 1.05,
        children: cells,
      ),
    ]);
  }

  Widget _buildDayDetail() {
    final evs = _eventsByDate[_selectedDate] ?? const [];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(_selectedDate ?? '날짜를 선택하세요',
            style: const TextStyle(
                color: Color(0xFF4FC3F7), fontWeight: FontWeight.bold, fontSize: 14)),
        const SizedBox(height: 8),
        if (evs.isEmpty)
          const Text('이 날짜에는 등록된 일정이 없습니다.',
              style: TextStyle(color: Colors.grey, fontSize: 12.5)),
        for (final e in evs)
          Container(
            width: double.infinity,
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFF161B22),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: Colors.white10),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(spacing: 6, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    _chip('${e['category']}', const Color(0xFF4FC3F7)),
                    _chip('${e['importance']}', _impColor(e['importance'])),
                  ],
                ),
                const SizedBox(height: 6),
                Text('${e['title']}',
                    style: const TextStyle(
                        color: Colors.white, fontWeight: FontWeight.bold, fontSize: 13.5)),
                if ('${e['description'] ?? ''}'.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text('${e['description']}',
                      style: const TextStyle(
                          color: Colors.white70, fontSize: 12.5, height: 1.5)),
                ],
                if ((e['stocks'] as List?)?.isNotEmpty ?? false) ...[
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 6, runSpacing: 6,
                    children: [
                      for (final s in (e['stocks'] as List).whereType<Map>())
                        Tooltip(
                          message: '${s['reason'] ?? ''}',
                          child: _chip('${s['name']} ${s['ticker']} · ${s['impact']}',
                              _impactColor(s['impact'])),
                        ),
                    ],
                  ),
                ],
              ],
            ),
          ),
      ],
    );
  }

  Widget _buildUpsideCard(int rank, Map<String, dynamic> u) {
    final events = ((u['events'] as List?) ?? const [])
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList();
    final soon = '${u['nearest_date']}'.compareTo(_todayStr) >= 0 &&
        DateTime.tryParse('${u['nearest_date']}') != null &&
        DateTime.parse('${u['nearest_date']}')
                .difference(DateTime.parse(_todayStr))
                .inDays <= 7;

    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF00D084).withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFF00D084).withValues(alpha: 0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Container(
              width: 20, height: 20,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: const Color(0xFF00D084).withValues(alpha: 0.2),
                shape: BoxShape.circle,
              ),
              child: Text('$rank',
                  style: const TextStyle(
                      color: Color(0xFF00D084), fontSize: 11, fontWeight: FontWeight.bold)),
            ),
            const SizedBox(width: 7),
            Expanded(
              child: Text('${u['name']} (${u['ticker']})',
                  style: const TextStyle(
                      color: Colors.white, fontWeight: FontWeight.bold, fontSize: 13.5),
                  overflow: TextOverflow.ellipsis),
            ),
            _chip('${u['score']}점', const Color(0xFF00D084)),
          ]),
          const SizedBox(height: 5),
          Row(children: [
            Text('관련 일정 ${u['event_count']}건 · 최근접 ${u['nearest_date']}',
                style: const TextStyle(color: Colors.grey, fontSize: 11)),
            if (soon) ...[
              const SizedBox(width: 6),
              _chip('임박', Colors.amber),
            ],
          ]),
          const SizedBox(height: 7),
          for (final e in events.take(3))
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('${e['date']}'.substring(5),
                        style: const TextStyle(color: Color(0xFF4FC3F7), fontSize: 11.5)),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text('${e['title']}',
                          style: const TextStyle(color: Colors.white70, fontSize: 11.5)),
                    ),
                  ]),
                  if ('${e['reason'] ?? ''}'.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(left: 42, top: 1),
                      child: Text('${e['reason']}',
                          style: const TextStyle(
                              color: Colors.white38, fontSize: 11, height: 1.35)),
                    ),
                ],
              ),
            ),
          if (events.length > 3)
            Text('외 ${events.length - 3}건',
                style: const TextStyle(color: Colors.grey, fontSize: 11)),
        ],
      ),
    );
  }

  Widget _buildWatchCard(Map<String, dynamic> w) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: const Color(0xFF4FC3F7).withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF4FC3F7).withValues(alpha: 0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Expanded(
              child: Text('${w['name']} (${w['ticker']})',
                  style: const TextStyle(
                      color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14)),
            ),
            _chip('신뢰도 ${w['confidence']}', _impColor(w['confidence'])),
          ]),
          const SizedBox(height: 4),
          Text('${w['event_date']} · ${w['event']}',
              style: const TextStyle(color: Colors.grey, fontSize: 11.5)),
          const SizedBox(height: 10),
          _timing('🟢 매수', '${w['buy_timing']}', const Color(0xFF7EE0B8)),
          _timing('🔴 매도', '${w['sell_timing']}', const Color(0xFF9ECBFF)),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: _metric('목표가', _won(w['target_price']), const Color(0xFF00D084))),
            Expanded(child: _metric('손절가', _won(w['stop_loss']), Colors.redAccent)),
            Expanded(child: _metric('기대수익', '${w['expected_return'] ?? '-'}', Colors.white)),
          ]),
          if ('${w['reason'] ?? ''}'.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text('${w['reason']}',
                style: const TextStyle(color: Colors.white60, fontSize: 12, height: 1.45)),
          ],
        ],
      ),
    );
  }

  Widget _timing(String label, String text, Color color) => Padding(
        padding: const EdgeInsets.only(bottom: 5),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(width: 54,
              child: Text(label, style: const TextStyle(color: Colors.grey, fontSize: 12))),
          Expanded(
            child: Text(text,
                style: TextStyle(color: color, fontSize: 12.5, height: 1.45)),
          ),
        ]),
      );

  Widget _metric(String label, String value, Color color) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: Colors.grey, fontSize: 11)),
          Text(value, style: TextStyle(color: color, fontSize: 12.5, fontWeight: FontWeight.bold)),
        ],
      );

  Widget _chip(String text, Color color) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Text(text, style: TextStyle(fontSize: 11, color: color)),
      );
}
