import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../providers/trading_provider.dart';
import '../widgets/market_tab_bar.dart';

/// AI 추천 종목 — 프로파일 관리 및 실행 (웹 서비스와 동일 API 사용, 자동 동기화)
class AiPicksScreen extends StatefulWidget {
  const AiPicksScreen({super.key});

  @override
  State<AiPicksScreen> createState() => _AiPicksScreenState();
}

class _AiPicksScreenState extends State<AiPicksScreen> {
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
      final res = await context.read<TradingProvider>().api.getAiPicks();
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
    await context.read<TradingProvider>().api.deleteAiPick(p['id']);
    _toast('삭제되었습니다.');
    _loadProfiles();
  }

  void _openEditor([Map<String, dynamic>? profile]) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
          builder: (_) => AiPickEditorScreen(profile: profile, market: _market)),
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
        title: const Text('✨ AI 종목', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          // 목록을 가리지 않도록 상단에 둔다 (기존 FAB 대체)
          TextButton.icon(
            onPressed: () => _openEditor(),
            icon: const Icon(Icons.add, size: 18),
            label: const Text('새 프로파일'),
            style: TextButton.styleFrom(
              foregroundColor: const Color(0xFF00D084),
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
                                    color: _statusColor(p['last_status']).withOpacity(0.15),
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                  child: Text(_statusLabel(p['last_status']),
                                      style: TextStyle(fontSize: 11, color: _statusColor(p['last_status']))),
                                ),
                                const SizedBox(width: 8),
                                if (p['last_finished_at'] != null)
                                  Expanded(
                                    child: Text(p['last_finished_at'],
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

/// 프로파일 편집 + 실행 + 결과 화면
class AiPickEditorScreen extends StatefulWidget {
  final Map<String, dynamic>? profile;
  final String market; // 새 프로파일 생성 시 사용할 시장 구분
  const AiPickEditorScreen({super.key, this.profile, this.market = 'DOMESTIC'});

  @override
  State<AiPickEditorScreen> createState() => _AiPickEditorScreenState();
}

class _AiPickEditorScreenState extends State<AiPickEditorScreen> {
  // 성능 순 모델 목록 (서버 목록으로 갱신됨)
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

  // 상세 비교 (재무·투자지표)
  Map<String, dynamic>? _comparison;
  bool _comparing = false;
  Timer? _comparePollTimer;
  int? _sortColumnIndex;
  bool _sortAscending = false;
  bool _exportingSheet = false;
  String? _gsheetUrl;

  @override
  void initState() {
    super.initState();
    _profileId = widget.profile?['id'];
    _nameCtrl = TextEditingController(text: widget.profile?['name'] ?? '');
    _promptCtrl = TextEditingController(text: widget.profile?['prompt'] ?? '');
    _model = widget.profile?['model'] ?? 'claude-opus-5';
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadModels();
      if (_profileId != null) {
        _loadResult();
        _loadComparison();
      }
    });
  }

  Future<void> _loadModels() async {
    try {
      final res = await context.read<TradingProvider>().api.getAiPickModels();
      final list = (res['models'] as List?)?.cast<Map<String, dynamic>>();
      if (list != null && list.isNotEmpty && mounted) {
        final serverDefault = (res['default'] ?? list.first['id']) as String;
        setState(() {
          _models = list;
          // 신규 프로파일은 서버가 지정한 기본 모델을 따름 (앱 재배포 없이 기본값 변경 반영)
          if (widget.profile == null || !_models.any((m) => m['id'] == _model)) {
            _model = serverDefault;
          }
        });
      }
    } catch (_) {}
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _comparePollTimer?.cancel();
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

  Future<void> _loadResult() async {
    if (_profileId == null) return;
    try {
      final res = await context.read<TradingProvider>().api.getAiPickResult(_profileId!);
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

  // ── 상세 비교 ──
  Future<void> _loadComparison() async {
    if (_profileId == null) return;
    try {
      final res = await context.read<TradingProvider>().api.getAiPickComparison(_profileId!);
      if (!mounted) return;
      if (res['status'] == 'NONE') {
        setState(() { _comparison = null; _comparing = false; _gsheetUrl = null; });
        return;
      }
      setState(() {
        _comparison = res;
        _comparing = res['status'] == 'running';
      });
      if (_comparing) {
        _startComparePolling();
      } else {
        _comparePollTimer?.cancel();
      }
    } catch (_) {}
  }

  void _startComparePolling() {
    _comparePollTimer?.cancel();
    _comparePollTimer = Timer.periodic(const Duration(seconds: 3), (_) => _loadComparison());
  }

  Future<void> _runCompare() async {
    if (_profileId == null) return;
    try {
      final res = await context.read<TradingProvider>().api.runAiPickCompare(_profileId!);
      if (res['status'] == 'ERROR') {
        _toast('비교 분석 실패: ${res['message']}');
        return;
      }
      setState(() {
        _comparing = true;
        _comparison = {'status': 'running', 'comparison': []};
        _sortColumnIndex = null;
        _gsheetUrl = null;
      });
      _startComparePolling();
    } catch (e) {
      _toast('비교 분석 오류: $e');
    }
  }

  /// 상세 비교 결과를 구글 시트에 업로드 (탭 이름 = 프로파일명)
  Future<void> _exportComparison() async {
    if (_profileId == null || _exportingSheet) return;
    setState(() => _exportingSheet = true);
    try {
      final res = await context
          .read<TradingProvider>()
          .api
          .exportAiPickComparisonToGSheet(_profileId!);
      if (!mounted) return;
      if (res['status'] == 'SUCCESS') {
        setState(() => _gsheetUrl = res['url'] as String?);
        _toast("구글 시트 '${res['sheet']}' 탭에 ${res['rows']}종목 업로드 완료");
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
          ? await api.createAiPick(name, prompt, _model, market: market)
          : await api.updateAiPick(_profileId!, name, prompt, _model, market: market);
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
    // 변경 사항 저장 후 실행
    if (!await _save(silent: true)) return;
    if (!mounted) return;
    try {
      final res = await context.read<TradingProvider>().api.runAiPick(_profileId!);
      if (res['status'] == 'ERROR') {
        _toast('실행 실패: ${res['message']}');
        return;
      }
      setState(() {
        _running = true;
        _result = {'status': 'running', 'stocks': []};
        // 새로 선별하면 이전 비교 결과는 무효
        _comparison = null;
        _comparing = false;
      });
      _comparePollTimer?.cancel();
      _startPolling();
    } catch (e) {
      _toast('실행 오류: $e');
    }
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
              hintText: '예: 주가_재무기반',
              border: OutlineInputBorder(),
            ),
            style: const TextStyle(color: Colors.white),
          ),
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
              labelText: '추천 프롬프트',
              hintText: 'AI에게 요청할 종목 선별 조건을 입력하세요',
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
                label: Text(_running ? '실행 중...' : '실행',
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
    final stocks = (_result!['stocks'] as List?) ?? [];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text('📋 선별 결과',
                style: TextStyle(color: Color(0xFF00D084), fontWeight: FontWeight.bold, fontSize: 15)),
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
                Text('AI가 종목을 선별하는 중입니다... (최대 7분)',
                    style: TextStyle(color: Colors.grey, fontSize: 13)),
              ]),
            ),
          )
        else if (status == 'error')
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.redAccent.withOpacity(0.08),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: Colors.redAccent.withOpacity(0.4)),
            ),
            child: Text('⚠️ ${_result!['error']}',
                style: const TextStyle(color: Colors.redAccent, fontSize: 13)),
          )
        else if (status == 'done') ...[
          for (var i = 0; i < stocks.length; i++) _stockCard(i, stocks[i] as Map<String, dynamic>),
          if (stocks.isNotEmpty) ...[
            const SizedBox(height: 6),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xFF4FC3F7),
                  side: const BorderSide(color: Color(0xFF00A8CC)),
                  padding: const EdgeInsets.symmetric(vertical: 12),
                ),
                onPressed: _comparing ? null : _runCompare,
                icon: _comparing
                    ? const SizedBox(width: 14, height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white70))
                    : const Icon(Icons.table_chart, size: 18),
                label: Text(_comparing ? '비교 분석 중...' : '📊 상세 비교',
                    style: const TextStyle(fontWeight: FontWeight.bold)),
              ),
            ),
          ],
          const Padding(
            padding: EdgeInsets.only(top: 8),
            child: Text('※ AI가 생성한 참고용 정보입니다. 투자 판단과 책임은 본인에게 있습니다.',
                style: TextStyle(color: Colors.grey, fontSize: 11)),
          ),
        ],
        if (_comparison != null) ...[
          const SizedBox(height: 20),
          _buildComparison(),
        ],
      ],
    );
  }

  /// 상세 비교 결과 — 가로 스크롤 + 헤더 정렬 가능한 테이블
  Widget _buildComparison() {
    final status = _comparison!['status'];
    final rows = ((_comparison!['comparison'] as List?) ?? []).cast<Map<String, dynamic>>();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Flexible(
              child: Text('📊 상세 비교 (재무·투자지표)',
                  style: TextStyle(color: Color(0xFF4FC3F7), fontWeight: FontWeight.bold, fontSize: 15)),
            ),
            if (_comparison!['finished_at'] != null)
              Text('${_comparison!['finished_at']}',
                  style: const TextStyle(color: Colors.grey, fontSize: 11)),
          ],
        ),
        if (status == 'done' && rows.isNotEmpty) ...[
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 4,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              OutlinedButton.icon(
                onPressed: _exportingSheet ? null : _exportComparison,
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
        ],
        const SizedBox(height: 10),
        if (status == 'running')
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 24),
            child: Center(
              child: Column(children: [
                CircularProgressIndicator(),
                SizedBox(height: 12),
                Text('재무제표와 투자지표를 비교 분석하는 중입니다... (최대 15분)',
                    textAlign: TextAlign.center,
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
            child: Text('⚠️ ${_comparison!['error']}',
                style: const TextStyle(color: Colors.redAccent, fontSize: 13)),
          )
        else if (status == 'done' && rows.isNotEmpty) ...[
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: DataTable(
              sortColumnIndex: _sortColumnIndex,
              sortAscending: _sortAscending,
              headingRowColor: WidgetStateProperty.all(const Color(0xFF161B22)),
              headingTextStyle: const TextStyle(
                  color: Color(0xFF4FC3F7), fontSize: 11.5, fontWeight: FontWeight.bold),
              dataTextStyle: const TextStyle(color: Colors.white, fontSize: 11.5),
              columnSpacing: 20,
              headingRowHeight: 40,
              dataRowMinHeight: 38,
              dataRowMaxHeight: 56,
              columns: [
                for (var i = 0; i < _compareColumns.length; i++)
                  DataColumn(
                    label: Text(_compareColumns[i].$1),
                    numeric: _compareColumns[i].$2 != 'name',
                    onSort: (idx, asc) => setState(() {
                      _sortColumnIndex = idx;
                      _sortAscending = asc;
                    }),
                  ),
                const DataColumn(label: Text('총평')),
              ],
              rows: [
                for (final c in _sortedComparison(rows))
                  DataRow(cells: [
                    for (final col in _compareColumns)
                      DataCell(col.$2 == 'name'
                          ? Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Text('${c['name']}',
                                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 11.5)),
                                Text('${c['ticker']}',
                                    style: const TextStyle(color: Colors.grey, fontSize: 10)),
                              ],
                            )
                          : Text(_fmtNum(c[col.$2]),
                              style: TextStyle(color: _valueColor(col.$2, c[col.$2]), fontSize: 11.5))),
                    DataCell(SizedBox(
                      width: 260,
                      child: Text('${c['comment'] ?? ''}',
                          style: const TextStyle(color: Colors.grey, fontSize: 11, height: 1.4),
                          maxLines: 3, overflow: TextOverflow.ellipsis),
                    )),
                  ]),
              ],
            ),
          ),
          const Padding(
            padding: EdgeInsets.only(top: 8),
            child: Text(
                '※ 좌우로 스크롤하고 헤더를 눌러 정렬할 수 있습니다. "-"는 AI가 확인하지 못한 값입니다.',
                style: TextStyle(color: Colors.grey, fontSize: 11)),
          ),
        ],
      ],
    );
  }

  /// (헤더 라벨, 데이터 키) — 표시 순서
  static const List<(String, String)> _compareColumns = [
    ('종목명', 'name'),
    ('주가', 'price'),
    ('시가총액(억)', 'market_cap'),
    ('PER', 'per'),
    ('PBR', 'pbr'),
    ('ROE(%)', 'roe'),
    ('매출(억)', 'revenue'),
    ('영업이익(억)', 'operating_profit'),
    ('순이익(억)', 'net_income'),
    ('영업이익률(%)', 'operating_margin'),
    ('부채비율(%)', 'debt_ratio'),
    ('매출성장(%)', 'revenue_growth'),
    ('배당(%)', 'dividend_yield'),
    ('외국인(%)', 'foreign_ownership'),
    ('52주 최고', 'week52_high'),
    ('52주 최저', 'week52_low'),
  ];

  /// 문자열/숫자에서 숫자만 추출 (없으면 null)
  static double? _toNum(dynamic v) {
    if (v == null) return null;
    if (v is num) return v.toDouble();
    final m = RegExp(r'-?\d+(\.\d+)?').firstMatch(v.toString().replaceAll(',', ''));
    return m == null ? null : double.tryParse(m.group(0)!);
  }

  static String _fmtNum(dynamic v) {
    final n = _toNum(v);
    if (n == null) return '-';
    final isInt = n == n.roundToDouble();
    final s = isInt ? n.toInt().toString() : n.toStringAsFixed(2);
    // 천 단위 구분 (소수부는 유지)
    final parts = s.split('.');
    parts[0] = parts[0].replaceAllMapped(
        RegExp(r'(\d)(?=(\d{3})+$)'), (m) => '${m[1]},');
    return parts.join('.');
  }

  static const _profitKeys = {
    'roe', 'operating_profit', 'net_income', 'operating_margin', 'revenue_growth'
  };

  Color _valueColor(String key, dynamic v) {
    if (!_profitKeys.contains(key)) return Colors.white;
    final n = _toNum(v);
    if (n == null) return Colors.white;
    return n > 0 ? const Color(0xFF00D084) : (n < 0 ? Colors.redAccent : Colors.white);
  }

  /// 선택된 헤더 기준 정렬 (값 없는 행은 항상 뒤로)
  List<Map<String, dynamic>> _sortedComparison(List<Map<String, dynamic>> rows) {
    if (_sortColumnIndex == null || _sortColumnIndex! >= _compareColumns.length) return rows;
    final key = _compareColumns[_sortColumnIndex!].$2;
    final sorted = [...rows];
    sorted.sort((a, b) {
      if (key == 'name') {
        final r = '${a['name']}'.compareTo('${b['name']}');
        return _sortAscending ? r : -r;
      }
      final an = _toNum(a[key]), bn = _toNum(b[key]);
      if (an == null && bn == null) return 0;
      if (an == null) return 1;   // 값 없으면 뒤로
      if (bn == null) return -1;
      final r = an.compareTo(bn);
      return _sortAscending ? r : -r;
    });
    return sorted;
  }

  Widget _stockCard(int index, Map<String, dynamic> s) {
    final isKospi = s['market'] == '코스피';
    final price = (s['price'] is num) ? (s['price'] as num).toInt() : 0;
    return Card(
      color: const Color(0xFF161B22),
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Text('${index + 1}. ', style: const TextStyle(color: Colors.grey, fontSize: 13)),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                decoration: BoxDecoration(
                  color: (isKospi ? const Color(0xFF00A8CC) : Colors.amber).withOpacity(0.15),
                  borderRadius: BorderRadius.circular(5),
                ),
                child: Text(s['market'] ?? '',
                    style: TextStyle(
                        fontSize: 10.5,
                        fontWeight: FontWeight.bold,
                        color: isKospi ? const Color(0xFF4FC3F7) : Colors.amber)),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text('${s['name']} (${s['ticker']})',
                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14),
                    overflow: TextOverflow.ellipsis),
              ),
              Text(s['upside'] ?? '',
                  style: const TextStyle(color: Color(0xFF00D084), fontWeight: FontWeight.bold, fontSize: 14)),
            ]),
            const SizedBox(height: 6),
            Row(children: [
              const Text('현재가 ', style: TextStyle(color: Colors.grey, fontSize: 12)),
              Text('${_comma(price)}원',
                  style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600)),
            ]),
            if ((s['reason'] ?? '').toString().isNotEmpty) ...[
              const SizedBox(height: 5),
              Text(s['reason'],
                  style: const TextStyle(color: Colors.grey, fontSize: 12, height: 1.4)),
            ],
          ],
        ),
      ),
    );
  }

  String _comma(int n) => n.toString().replaceAllMapped(
      RegExp(r'(\d)(?=(\d{3})+(?!\d))'), (m) => '${m[1]},');
}
