import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';
import '../providers/trading_provider.dart';
import '../models/models.dart';
import '../widgets/status_badge.dart';
import 'ticker_detail_screen.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      appBar: AppBar(
        backgroundColor: const Color(0xFF161B22),
        title: const Text('대시보드', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          // 목록을 가리지 않도록 종목 추가는 상단에 둔다 (기존 FAB 대체)
          Consumer<TradingProvider>(
            builder: (context, p, __) => TextButton.icon(
              onPressed: () => _showAddTickerDialog(context, p),
              icon: const Icon(Icons.add, size: 18),
              label: const Text('종목 추가'),
              style: TextButton.styleFrom(
                foregroundColor: const Color(0xFF00D084),
                textStyle: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
              ),
            ),
          ),
          Consumer<TradingProvider>(
            builder: (_, p, __) => IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: p.fetchStatus,
            ),
          ),
        ],
      ),
      body: Consumer<TradingProvider>(
        builder: (context, provider, _) {
          return RefreshIndicator(
            onRefresh: provider.fetchStatus,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                _ConnectionCard(provider: provider),
                const SizedBox(height: 12),
                if (provider.account != null)
                  _AccountCard(account: provider.account!),
                const SizedBox(height: 12),
                HoldingsSection(holdings: provider.holdings),
                const SizedBox(height: 12),
                _TickerListSection(provider: provider),
                const SizedBox(height: 12),
                _LogSection(logs: provider.logs),
              ],
            ),
          );
        },
      ),
    );
  }

  void _showAddTickerDialog(BuildContext context, TradingProvider provider) {
    showDialog(
      context: context,
      builder: (ctx) => _AddTickerDialog(provider: provider),
    );
  }
}

class _ConnectionCard extends StatelessWidget {
  final TradingProvider provider;
  const _ConnectionCard({required this.provider});

  @override
  Widget build(BuildContext context) {
    return Card(
      color: const Color(0xFF161B22),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              width: 12, height: 12,
              decoration: BoxDecoration(
                color: provider.isConnected ? const Color(0xFF00D084) : Colors.red,
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    provider.isConnected ? '연결됨' : '연결 끊김',
                    style: TextStyle(
                      color: provider.isConnected ? const Color(0xFF00D084) : Colors.red,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  Text(
                    provider.baseUrl,
                    style: const TextStyle(color: Colors.grey, fontSize: 12),
                  ),
                ],
              ),
            ),
            StatusBadge(text: provider.engineStatus),
          ],
        ),
      ),
    );
  }
}

class _AccountCard extends StatelessWidget {
  final AccountInfo account;
  const _AccountCard({required this.account});

  /// "1234567890" → "1234-5678" (뒤 2자리는 표시하지 않음, 웹과 동일)
  static String _fmtAcc(String acc) {
    if (acc.length < 10) return acc;
    return '${acc.substring(0, 4)}-${acc.substring(4, 8)}';
  }

  @override
  Widget build(BuildContext context) {
    final fmt = NumberFormat('#,###', 'ko_KR');
    final isOverseas = account.market == 'OVERSEAS';
    final label = isOverseas ? '해외 예수금' : '예수금';
    final amount = isOverseas
        ? '\$${fmt.format(account.balance)}'
        : '${fmt.format(account.balance)}원';
    // 해외 주식 가능 계좌 판정 (웹과 동일: 접미사 10 = 위탁종합)
    final canOverseas = account.hasOverseas || account.accNo.endsWith('10');

    return Card(
      color: const Color(0xFF161B22),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.account_balance_wallet, color: Color(0xFF00D084), size: 18),
                const SizedBox(width: 8),
                Text(account.name, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                const Spacer(),
                // 국내/해외 전환 (해외 가능 계좌만 표시)
                if (canOverseas)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 3, vertical: 2),
                    decoration: BoxDecoration(
                      color: Colors.black26,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Row(children: [
                      _MarketToggleBtn(
                        label: '국내',
                        isSelected: !isOverseas,
                        onTap: () {
                          if (isOverseas) {
                            context.read<TradingProvider>().changeMarket('DOMESTIC');
                          }
                        },
                      ),
                      _MarketToggleBtn(
                        label: '해외',
                        isSelected: isOverseas,
                        onTap: () {
                          if (!isOverseas) {
                            context.read<TradingProvider>().changeMarket('OVERSEAS');
                          }
                        },
                      ),
                    ]),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            // 계좌 선택 (목록이 있으면 드롭다운, 없으면 텍스트)
            if (account.accList.length > 1)
              Row(children: [
                const Text('계좌: ', style: TextStyle(color: Colors.grey, fontSize: 13)),
                DropdownButton<String>(
                  value: account.accList.contains(account.accNo) ? account.accNo : null,
                  hint: Text(_fmtAcc(account.accNo),
                      style: const TextStyle(color: Colors.white, fontSize: 13)),
                  dropdownColor: const Color(0xFF161B22),
                  style: const TextStyle(color: Colors.white, fontSize: 13),
                  underline: const SizedBox.shrink(),
                  isDense: true,
                  items: [
                    for (final a in account.accList)
                      DropdownMenuItem(
                        value: a,
                        child: Text('${_fmtAcc(a)}${a.endsWith('10') ? ' [종합]' : ''}'),
                      ),
                  ],
                  onChanged: (v) {
                    if (v != null && v != account.accNo) {
                      context.read<TradingProvider>().changeAccount(v);
                    }
                  },
                ),
              ])
            else
              Text('계좌번호: ${account.accNo}',
                  style: const TextStyle(color: Colors.grey, fontSize: 13)),
            // 계좌별 시장 고정 설정: 체크하면 계좌 변경 시 국내/해외 자동 전환
            Row(children: [
              _PrefCheckbox(
                label: '국내전용',
                checked: account.accMarketPrefs[account.accNo] == 'DOMESTIC',
                onChanged: (v) => context.read<TradingProvider>()
                    .setAccountMarketPref(account.accNo, v ? 'DOMESTIC' : null),
              ),
              if (canOverseas)
                _PrefCheckbox(
                  label: '해외전용',
                  checked: account.accMarketPrefs[account.accNo] == 'OVERSEAS',
                  onChanged: (v) => context.read<TradingProvider>()
                      .setAccountMarketPref(account.accNo, v ? 'OVERSEAS' : null),
                ),
            ]),
            const SizedBox(height: 2),
            Text(
              '$label: $amount',
              style: const TextStyle(color: Color(0xFF00D084), fontSize: 18, fontWeight: FontWeight.bold),
            ),
          ],
        ),
      ),
    );
  }
}

/// 계좌별 시장 고정 설정 체크박스 (국내전용/해외전용)
class _PrefCheckbox extends StatelessWidget {
  final String label;
  final bool checked;
  final ValueChanged<bool> onChanged;
  const _PrefCheckbox(
      {required this.label, required this.checked, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () => onChanged(!checked),
      child: Padding(
        padding: const EdgeInsets.only(right: 12),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          SizedBox(
            width: 30, height: 30,
            child: Checkbox(
              value: checked,
              onChanged: (v) => onChanged(v == true),
              activeColor: const Color(0xFF00D084),
              checkColor: Colors.black,
              materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              visualDensity: VisualDensity.compact,
            ),
          ),
          Text(label, style: const TextStyle(color: Colors.grey, fontSize: 12)),
        ]),
      ),
    );
  }
}

class _MarketToggleBtn extends StatelessWidget {
  final String label;
  final bool isSelected;
  final VoidCallback onTap;
  const _MarketToggleBtn(
      {required this.label, required this.isSelected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: isSelected ? const Color(0xFF00D084) : Colors.transparent,
          borderRadius: BorderRadius.circular(6),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? Colors.black : Colors.grey,
            fontSize: 11.5,
            fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
          ),
        ),
      ),
    );
  }
}

/// 계좌 보유 종목 — 웹 보유종목 탭과 동일한 항목 및 헤더 정렬을 제공한다.
/// (종목명/보유수량/매입단가/매입금액/현재가/평가손익/수익률)
class HoldingsSection extends StatefulWidget {
  final List<Map<String, dynamic>> holdings;
  const HoldingsSection({required this.holdings});

  @override
  State<HoldingsSection> createState() => HoldingsSectionState();
}

class HoldingsSectionState extends State<HoldingsSection> {
  bool _expanded = true;
  int? _sortColumnIndex;
  bool _sortAscending = false;

  // 종목코드 -> AI 매매 전략 목록
  Map<String, List<dynamic>> _strategies = {};

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadStrategies();
      _loadAiProfiles();
    });
  }

  Future<void> _loadStrategies() async {
    try {
      final res = await context.read<TradingProvider>().api.getAiTradeStrategies();
      if (!mounted) return;
      setState(() {
        _strategies = res.map((k, v) => MapEntry(k, (v as List?) ?? []));
      });
    } catch (_) {}
  }

  // 선언 타입과 실제 반환 타입이 어긋나면 firstWhere의 orElse에서
  // 런타임 타입 오류가 나므로 정확한 타입으로 선언한다
  List<Map<String, dynamic>> _strategiesFor(Map<String, dynamic> h) =>
      (_strategies['${h['ticker']}'] ?? const [])
          .whereType<Map>()
          .map((e) => Map<String, dynamic>.from(e))
          .toList();

  /// 특정 프로파일이 이 종목에 대해 낸 분석 결과 (없으면 null)
  Map<String, dynamic>? _strategyOf(Map<String, dynamic> h, int pid) {
    for (final s in _strategiesFor(h)) {
      if (s['profile_id'] == pid) return s;
    }
    return null;
  }

  // AI 매매 프로파일 목록 및 분석 실행 상태
  List<Map<String, dynamic>> _aiProfiles = [];
  int? _runProfileId;
  String? _runningTicker;
  final Map<String, int> _selectedProfileId = {};   // 종목코드 -> 보고 있는 프로파일

  // ── 보유 종목 전체 일괄 분석 ──
  int? _batchProfileId;
  Map<String, dynamic> _batch = {'running': false, 'total': 0, 'done': 0,
                                 'current': '', 'errors': 0};
  Timer? _batchTimer;

  void _pollBatch(int pid) {
    _batchTimer?.cancel();
    _batchTimer = Timer.periodic(const Duration(seconds: 5), (t) async {
      try {
        final st = await context.read<TradingProvider>().api.getAiTradeBatchStatus(pid);
        await _loadStrategies();     // 완료된 종목부터 바로 반영
        if (!mounted) return;
        setState(() => _batch = st);
        if (st['running'] != true) t.cancel();
      } catch (_) {}
    });
  }

  Future<void> _runBatch() async {
    final pid = _batchProfileId;
    if (pid == null || widget.holdings.isEmpty) return;
    final name = _aiProfiles.firstWhere((p) => p['id'] == pid,
        orElse: () => <String, dynamic>{})['name'] ?? '';
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF161B22),
        title: const Text('보유 종목 전체 분석', style: TextStyle(color: Colors.white)),
        content: Text(
          "보유 종목 ${widget.holdings.length}개를 '$name' 프로파일로 분석합니다.\n"
          '한 종목씩 순서대로 진행하며 종목당 최대 15분이 걸릴 수 있습니다.',
          style: const TextStyle(color: Colors.white70, fontSize: 13.5),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false),
              child: const Text('취소', style: TextStyle(color: Colors.grey))),
          FilledButton(onPressed: () => Navigator.pop(ctx, true),
              child: const Text('시작')),
        ],
      ),
    );
    if (ok != true || !mounted) return;

    final items = [
      for (final h in widget.holdings)
        {'ticker': '${h['ticker']}', 'name': '${h['name'] ?? ''}'},
    ];
    try {
      final res = await context.read<TradingProvider>().api.runAiTradeBatch(pid, items);
      if (!mounted) return;
      if (res['status'] == 'ERROR') {
        _toast('일괄 분석 실행 실패: ${res['message']}');
        return;
      }
      if (res['status'] == 'RUNNING') _toast('이미 실행 중입니다.');
      setState(() => _batch = {'running': true, 'total': items.length,
                               'done': 0, 'current': '', 'errors': 0});
      _pollBatch(pid);
    } catch (e) {
      _toast('일괄 분석 오류: $e');
    }
  }

  Future<void> _loadAiProfiles() async {
    try {
      final list = await context.read<TradingProvider>().api.getAiTrades();
      if (!mounted) return;
      setState(() {
        _aiProfiles = list.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
        _runProfileId ??= _aiProfiles.isNotEmpty ? _aiProfiles.first['id'] as int : null;
        _batchProfileId ??= _runProfileId;
      });
      // 앱을 다시 열어도 진행 중인 일괄 분석을 이어서 표시
      final pid = _batchProfileId;
      if (pid != null) {
        final st = await context.read<TradingProvider>().api.getAiTradeBatchStatus(pid);
        if (mounted && st['running'] == true) {
          setState(() => _batch = st);
          _pollBatch(pid);
        }
      }
    } catch (_) {}
  }

  @override
  void dispose() {
    _batchTimer?.cancel();
    super.dispose();
  }

  // ── 실행 전 확인 팝업 ──
  Future<bool> _confirmAction(String title, String message) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF161B22),
        title: Text(title, style: const TextStyle(color: Colors.white)),
        content: Text(message, style: const TextStyle(color: Colors.white70)),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('취소', style: TextStyle(color: Colors.grey))),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: const Color(0xFF00D084)),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('실행', style: TextStyle(color: Colors.black)),
          ),
        ],
      ),
    );
    return ok == true;
  }

  // ── 보유 종목 업데이트 (브로커 계좌 새로고침) ──
  bool _refreshing = false;

  Future<void> _refreshHoldings() async {
    if (_refreshing) return;
    if (!await _confirmAction('보유 종목 업데이트',
        '증권사에서 보유 종목과 현재가를 다시 불러올까요?')) return;
    if (!mounted) return;
    setState(() => _refreshing = true);
    try {
      final res = await context.read<TradingProvider>().api.refreshAccount();
      if (!mounted) return;
      if (res['status'] == 'ERROR') {
        _toast('업데이트 실패: ${res['message'] ?? '알 수 없는 오류'}');
        setState(() => _refreshing = false);
        return;
      }
      // 키움은 게이트웨이 TR 조회 후 반영되므로 잠시 뒤 status 폴링으로 갱신된다
      await Future.delayed(const Duration(seconds: 6));
    } catch (e) {
      if (mounted) _toast('업데이트 오류: $e');
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  // ── 구글 시트 업로드 ('보유종목' 탭) ──
  bool _exportingSheet = false;
  String? _gsheetUrl;

  Future<void> _exportHoldings() async {
    if (_exportingSheet) return;
    if (!await _confirmAction('구글 시트 업로드',
        "보유 종목 ${widget.holdings.length}개를 '보유종목' 탭에 업로드할까요?\n기존 탭 내용은 덮어씁니다.")) return;
    if (!mounted) return;
    setState(() => _exportingSheet = true);
    try {
      final res = await context.read<TradingProvider>().api.exportHoldingsToGSheet();
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

  void _toast(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), behavior: SnackBarBehavior.floating),
    );
  }

  static double _d(dynamic v) => (v is num) ? v.toDouble() : 0;

  static double _buyAmount(Map<String, dynamic> h) =>
      _d(h['buy_price']) * _d(h['qty']);

  // 서버 ratio는 수수료·세금이 반영된 평가손익 기준. 없으면 매입금액으로 계산
  static double _ratio(Map<String, dynamic> h) {
    if (h['ratio'] is num) return _d(h['ratio']);
    final cost = _buyAmount(h);
    return cost > 0 ? _d(h['profit']) / cost * 100 : 0.0;
  }

  /// (헤더 라벨, 정렬값 추출) — 표시 순서
  static final List<(String, double Function(Map<String, dynamic>))> _columns = [
    ('보유수량', (h) => _d(h['qty'])),
    ('매입단가', (h) => _d(h['buy_price'])),
    ('매입금액', _buyAmount),
    ('현재가', (h) => _d(h['current_price'])),
    ('평가손익', (h) => _d(h['profit'])),
    ('수익률', _ratio),
  ];

  @visibleForTesting
  List<Map<String, dynamic>> get sortedForTest => _sorted;

  List<Map<String, dynamic>> get _sorted {
    final items = [...widget.holdings];
    final idx = _sortColumnIndex;
    if (idx == null) return items;
    final dir = _sortAscending ? 1 : -1;
    if (idx == 0) {
      // 종목명은 가나다순
      items.sort((a, b) =>
          '${a['name'] ?? ''}'.compareTo('${b['name'] ?? ''}') * dir);
      return items;
    }
    final getter = _columns[idx - 1].$2;
    items.sort((a, b) => getter(a).compareTo(getter(b)) * dir);
    return items;
  }

  void _toggleSort(int index) => setState(() {
        if (_sortColumnIndex == index) {
          _sortAscending = !_sortAscending;
        } else {
          _sortColumnIndex = index;
          _sortAscending = true;
        }
      });

  /// 정렬 헤더를 직접 그린다.
  ///
  /// DataTable의 onSort를 쓰면 라벨 옆에 정렬 화살표가 Row로 덧붙는데,
  /// 이 Row는 라벨을 Flexible로 감싸기 때문에 폰트 실측폭이 고유폭 계산과
  /// 조금만 어긋나도 화살표가 밀려나 "RIGHT OVERFLOWED BY n PIXELS"가 뜬다
  /// (브라우저마다 한글 대체 폰트가 달라 Flutter 웹에서 특히 잘 드러난다).
  /// 화살표를 라벨 안에 직접 넣어 헤더 폭이 항상 내용과 일치하게 만든다.
  Widget _sortHeader(String text, int index) {
    final active = _sortColumnIndex == index;
    return InkWell(
      onTap: () => _toggleSort(index),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(text),
          const SizedBox(width: 2),
          Icon(
            _sortAscending ? Icons.arrow_upward : Icons.arrow_downward,
            size: 13,
            // 비활성 컬럼도 같은 폭을 차지하도록 투명하게 그린다
            color: active ? const Color(0xFF4FC3F7) : Colors.transparent,
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final fmt = NumberFormat('#,###', 'ko_KR');
    final items = widget.holdings;

    // 총 매입금액 / 총 평가손익 / 총 수익률
    double totalProfit = 0, totalCost = 0;
    for (final h in items) {
      totalProfit += _d(h['profit']);
      totalCost += _buyAmount(h);
    }
    final totalRatio = totalCost > 0 ? totalProfit / totalCost * 100 : 0.0;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(
          onTap: items.isEmpty ? null : () => setState(() => _expanded = !_expanded),
          child: Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(
              children: [
                Flexible(
                  child: Text('보유 종목${items.isEmpty ? '' : ' (${items.length})'}',
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                ),
                if (items.isNotEmpty) ...[
                  const SizedBox(width: 6),
                  Icon(_expanded ? Icons.expand_less : Icons.expand_more,
                      size: 20, color: Colors.grey),
                ],
                const SizedBox(width: 8),
                // 좁은 화면에서 합계가 길어져도 넘치지 않도록 남는 폭에 맞춰 줄인다
                if (items.isNotEmpty)
                  Expanded(
                    child: Align(
                      alignment: Alignment.centerRight,
                      child: FittedBox(
                        fit: BoxFit.scaleDown,
                        alignment: Alignment.centerRight,
                        child: Text(
                          '${totalProfit > 0 ? '+' : ''}${fmt.format(totalProfit.round())}원'
                          '  (${totalRatio > 0 ? '+' : ''}${totalRatio.toStringAsFixed(2)}%)',
                          style: TextStyle(
                              color: _profitColor(totalProfit),
                              fontSize: 13,
                              fontWeight: FontWeight.bold),
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
        if (items.isEmpty)
          const Card(
            color: Color(0xFF161B22),
            child: Padding(
              padding: EdgeInsets.all(24),
              child: Center(
                  child: Text('보유 중인 종목이 없습니다', style: TextStyle(color: Colors.grey))),
            ),
          )
        else if (_expanded) ...[
          // 보유 종목 전체를 한 프로파일로 분석
          Wrap(
            spacing: 8, runSpacing: 4,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              const Text('🤖 전체 분석',
                  style: TextStyle(color: Color(0xFF4FC3F7),
                      fontWeight: FontWeight.bold, fontSize: 12.5)),
              if (_aiProfiles.isNotEmpty)
                DropdownButton<int>(
                  value: _batchProfileId,
                  dropdownColor: const Color(0xFF161B22),
                  style: const TextStyle(color: Colors.white, fontSize: 12.5),
                  underline: const SizedBox.shrink(),
                  isDense: true,
                  items: [
                    for (final p in _aiProfiles)
                      DropdownMenuItem(value: p['id'] as int, child: Text('${p['name']}')),
                  ],
                  onChanged: _batch['running'] == true
                      ? null
                      : (v) => setState(() => _batchProfileId = v),
                ),
              OutlinedButton.icon(
                onPressed: (_batch['running'] == true || items.isEmpty || _aiProfiles.isEmpty)
                    ? null
                    : _runBatch,
                icon: _batch['running'] == true
                    ? const SizedBox(width: 12, height: 12,
                        child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.play_arrow, size: 15),
                label: Text(_batch['running'] == true
                    ? '분석 중 ${_batch['done']}/${_batch['total']}'
                    : '${items.length}개 분석'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xFF4FC3F7),
                  side: const BorderSide(color: Color(0xFF4FC3F7)),
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 0),
                  minimumSize: Size.zero,
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  textStyle: const TextStyle(fontSize: 12),
                ),
              ),
            ],
          ),
          if (_batch['running'] == true && '${_batch['current']}'.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text('진행 중: ${_batch['current']}',
                  style: const TextStyle(color: Colors.grey, fontSize: 11.5)),
            ),
          const SizedBox(height: 6),
          Row(children: [
            Expanded(
              child: Text('총 매입금액 ${fmt.format(totalCost.round())}원',
                  style: const TextStyle(color: Colors.grey, fontSize: 12)),
            ),
            if (_gsheetUrl != null)
              TextButton(
                onPressed: _openGSheet,
                style: TextButton.styleFrom(
                  foregroundColor: const Color(0xFF4FC3F7),
                  padding: const EdgeInsets.symmetric(horizontal: 6),
                  minimumSize: Size.zero,
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  textStyle: const TextStyle(fontSize: 12),
                ),
                child: const Text('시트 열기 ↗'),
              ),
            const SizedBox(width: 4),
            OutlinedButton.icon(
              onPressed: _refreshing ? null : _refreshHoldings,
              icon: _refreshing
                  ? const SizedBox(
                      width: 12, height: 12,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.refresh, size: 14),
              label: Text(_refreshing ? '업데이트 중' : '업데이트'),
              style: OutlinedButton.styleFrom(
                foregroundColor: const Color(0xFF4FC3F7),
                side: const BorderSide(color: Color(0xFF4FC3F7)),
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 0),
                minimumSize: Size.zero,
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                textStyle: const TextStyle(fontSize: 12),
              ),
            ),
            const SizedBox(width: 4),
            OutlinedButton.icon(
              onPressed: _exportingSheet ? null : _exportHoldings,
              icon: _exportingSheet
                  ? const SizedBox(
                      width: 12, height: 12,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('📗', style: TextStyle(fontSize: 12)),
              label: Text(_exportingSheet ? '업로드 중' : '구글 시트'),
              style: OutlinedButton.styleFrom(
                foregroundColor: const Color(0xFF34A853),
                side: const BorderSide(color: Color(0xFF34A853)),
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 0),
                minimumSize: Size.zero,
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                textStyle: const TextStyle(fontSize: 12),
              ),
            ),
          ]),
          const SizedBox(height: 6),
          Card(
            color: const Color(0xFF161B22),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              // 정렬 표시는 _sortHeader가 직접 그린다 (sortColumnIndex/onSort 미사용)
              child: DataTable(
                // onSelectChanged를 쓰면 기본으로 체크박스 열이 붙는다. 탭 동작만 필요하므로 끈다
                showCheckboxColumn: false,
                headingRowColor: WidgetStateProperty.all(const Color(0xFF0D1117)),
                headingTextStyle: const TextStyle(
                    color: Color(0xFF4FC3F7), fontSize: 11.5, fontWeight: FontWeight.bold),
                dataTextStyle: const TextStyle(color: Colors.white, fontSize: 12),
                columnSpacing: 18,
                horizontalMargin: 14,
                headingRowHeight: 38,
                dataRowMinHeight: 40,
                dataRowMaxHeight: 48,
                columns: [
                  DataColumn(label: _sortHeader('종목명', 0)),
                  for (var i = 0; i < _columns.length; i++)
                    DataColumn(label: _sortHeader(_columns[i].$1, i + 1), numeric: true),
                ],
                rows: [
                  for (final h in _sorted) _holdingRow(h, fmt),
                ],
              ),
            ),
          ),
          const Padding(
            padding: EdgeInsets.only(top: 6),
            child: Text('※ 좌우로 스크롤하고 헤더를 눌러 정렬할 수 있습니다.',
                style: TextStyle(color: Colors.grey, fontSize: 11)),
          ),
        ],
      ],
    );
  }

  DataRow _holdingRow(Map<String, dynamic> h, NumberFormat fmt) {
    final profit = _d(h['profit']);
    final ratio = _ratio(h);
    final color = _profitColor(profit);
    final count = _strategiesFor(h).length;
    return DataRow(
      // 분석 이력이 없어도 눌러서 분석을 시작할 수 있게 항상 탭 가능
      onSelectChanged: (_) => _showStrategySheet(h),
      cells: [
      DataCell(Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Row(mainAxisSize: MainAxisSize.min, children: [
            Flexible(
              child: Text('${h['name'] ?? h['ticker']}',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12.5),
                  overflow: TextOverflow.ellipsis),
            ),
            Padding(
              padding: const EdgeInsets.only(left: 4),
              // 분석 이력이 없으면 흐리게 (눌러서 분석은 가능)
              child: Opacity(
                opacity: count > 0 ? 1.0 : 0.3,
                child: Text(count > 1 ? '🤖$count' : '🤖',
                    style: const TextStyle(fontSize: 11)),
              ),
            ),
          ]),
          Text('${h['ticker']}',
              style: const TextStyle(color: Colors.grey, fontSize: 10)),
        ],
      )),
      DataCell(Text(fmt.format(_d(h['qty']).round()))),
      DataCell(Text(fmt.format(_d(h['buy_price']).round()))),
      DataCell(Text(fmt.format(_buyAmount(h).round()))),
      DataCell(Text(fmt.format(_d(h['current_price']).round()))),
      DataCell(Text('${profit > 0 ? '+' : ''}${fmt.format(profit.round())}',
          style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.bold))),
      DataCell(Text('${ratio > 0 ? '+' : ''}${ratio.toStringAsFixed(2)}%',
          style: TextStyle(color: color, fontSize: 12))),
    ]);
  }

  /// 보유 종목 탭 시 해당 종목의 AI 매매 전략과 분석 실행 UI를 바텀시트로 표시.
  /// 분석 이력이 없어도 열리며, 여러 프로파일이 분석한 경우 골라서 볼 수 있다.
  void _showStrategySheet(Map<String, dynamic> h) {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF161B22),
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheetState) {
          final list = _strategiesFor(h);
          Map<String, dynamic>? selected;
          if (list.isNotEmpty) {
            final pid = _selectedProfileId['${h['ticker']}'];
            selected = list.firstWhere((s) => s['profile_id'] == pid,
                orElse: () => list.first);
          }
          final running = _runningTicker == '${h['ticker']}';

          return DraggableScrollableSheet(
            expand: false,
            initialChildSize: 0.75,
            maxChildSize: 0.95,
            builder: (_, controller) => ListView(
              controller: controller,
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
              children: [
                Center(
                  child: Container(
                    width: 40, height: 4,
                    decoration: BoxDecoration(
                      color: Colors.grey.shade700,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                ),
                const SizedBox(height: 14),
                Text('🤖 AI 매매 전략 — ${h['name'] ?? h['ticker']}',
                    style: const TextStyle(
                        color: Color(0xFF4FC3F7), fontWeight: FontWeight.bold, fontSize: 16)),
                const SizedBox(height: 4),
                Text('${h['ticker']} · 보유 ${_d(h['qty']).round()}주',
                    style: const TextStyle(color: Colors.grey, fontSize: 12)),
                const SizedBox(height: 14),

                // 분석 실행 (프로파일 선택 + 실행)
                Wrap(
                  spacing: 8, runSpacing: 6,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    if (_aiProfiles.isNotEmpty)
                      DropdownButton<int>(
                        value: _runProfileId,
                        dropdownColor: const Color(0xFF161B22),
                        style: const TextStyle(color: Colors.white, fontSize: 13),
                        underline: const SizedBox.shrink(),
                        items: [
                          for (final p in _aiProfiles)
                            DropdownMenuItem(value: p['id'] as int,
                                child: Text('${p['name']}')),
                        ],
                        onChanged: running
                            ? null
                            : (v) => setSheetState(() => _runProfileId = v),
                      ),
                    OutlinedButton.icon(
                      onPressed: (running || _aiProfiles.isEmpty)
                          ? null
                          : () => _runAnalysis(h, setSheetState),
                      icon: running
                          ? const SizedBox(
                              width: 14, height: 14,
                              child: CircularProgressIndicator(strokeWidth: 2))
                          : const Icon(Icons.play_arrow, size: 16),
                      label: Text(running ? '분석 중... (최대 15분)' : '분석 실행'),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: const Color(0xFF4FC3F7),
                        side: const BorderSide(color: Color(0xFF4FC3F7)),
                        textStyle: const TextStyle(fontSize: 13),
                      ),
                    ),
                  ],
                ),
                if (list.isEmpty && !running)
                  const Padding(
                    padding: EdgeInsets.only(top: 12),
                    child: Text('아직 이 종목의 분석 결과가 없습니다.',
                        style: TextStyle(color: Colors.grey, fontSize: 13)),
                  ),

                // 프로파일이 여러 개면 골라서 각각의 분석을 본다
                if (list.length > 1) ...[
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 6, runSpacing: 6,
                    children: [
                      for (final s in list)
                        ChoiceChip(
                          label: Text('${s['profile_name']}',
                              style: const TextStyle(fontSize: 12)),
                          selected: s['profile_id'] == selected?['profile_id'],
                          onSelected: (_) => setSheetState(() =>
                              _selectedProfileId['${h['ticker']}'] = s['profile_id'] as int),
                          selectedColor: const Color(0xFF4FC3F7).withValues(alpha: 0.25),
                          backgroundColor: const Color(0xFF0D1117),
                          labelStyle: const TextStyle(color: Colors.white),
                        ),
                    ],
                  ),
                ],
                const SizedBox(height: 12),
                if (selected != null) _strategyCard(selected),
              ],
            ),
          );
        },
      ),
    );
  }

  /// 선택한 프로파일로 해당 종목 분석을 실행하고 완료될 때까지 결과를 갱신한다
  Future<void> _runAnalysis(
      Map<String, dynamic> h, void Function(void Function()) setSheetState) async {
    final pid = _runProfileId;
    if (pid == null) return;
    final ticker = '${h['ticker']}';

    // 같은 종목 재분석 시 기존 결과가 남아 있으므로 완료 시각 변화로 판정한다
    final prevFinishedAt = _strategyOf(h, pid)?['finished_at'];

    try {
      final res = await context
          .read<TradingProvider>()
          .api
          .runAiTrade(pid, ticker, '${h['name'] ?? ''}');
      if (res['status'] == 'ERROR') {
        _toast('분석 실행 실패: ${res['message']}');
        return;
      }
    } catch (e) {
      _toast('분석 실행 오류: $e');
      return;
    }

    setSheetState(() => _runningTicker = ticker);
    setState(() {});

    final started = DateTime.now();
    while (mounted && DateTime.now().difference(started).inMinutes < 15) {
      await Future.delayed(const Duration(seconds: 5));
      await _loadStrategies();
      final cur = _strategyOf(h, pid);
      if (cur != null && cur['finished_at'] != prevFinishedAt) {
        _selectedProfileId[ticker] = pid;
        break;
      }
    }
    if (!mounted) return;
    _runningTicker = null;
    setSheetState(() {});
    setState(() {});
  }

  Widget _strategyCard(Map<String, dynamic> s) {
    final st = (s['strategy'] as Map?)?.cast<String, dynamic>() ?? {};
    final fmt = NumberFormat('#,###', 'ko_KR');
    String won(dynamic v) => v is num ? '${fmt.format(v.round())}원' : '${v ?? '-'}';

    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.all(14),
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
              child: Text('${s['profile_name']}',
                  style: const TextStyle(
                      color: Color(0xFF4FC3F7), fontWeight: FontWeight.bold, fontSize: 14)),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: _riskColor(st['risk_level']).withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text('리스크 ${st['risk_level'] ?? '-'}',
                  style: TextStyle(fontSize: 11, color: _riskColor(st['risk_level']))),
            ),
          ]),
          const SizedBox(height: 4),
          Text('${s['finished_at'] ?? ''} · ${s['model'] ?? ''}',
              style: const TextStyle(color: Colors.grey, fontSize: 10.5)),
          if ('${st['summary'] ?? ''}'.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text('${st['summary']}',
                style: const TextStyle(color: Colors.white70, fontSize: 13, height: 1.5)),
          ],
          const SizedBox(height: 12),
          _metric('진입 가격대', '${st['entry_price'] ?? '-'}', const Color(0xFF4FC3F7)),
          _metric('목표가', won(st['target_price']), const Color(0xFF00D084)),
          _metric('손절가', won(st['stop_loss']), Colors.redAccent),
          _metric('기대 수익', '${st['expected_return'] ?? '-'}', Colors.white),
          _metric('투자 비중', '${st['position_size'] ?? '-'}', Colors.white),
          _metric('보유 기간', '${st['holding_period'] ?? '-'}', Colors.white),
          _condList('✅ 매수 조건', st['buy_conditions'], const Color(0xFF00D084)),
          _condList('🎯 매도 조건', st['sell_conditions'], const Color(0xFF4FC3F7)),
          _condList('⚠️ 리스크', st['risks'], Colors.redAccent),
        ],
      ),
    );
  }

  Widget _metric(String label, String value, Color color) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: 84,
              child: Text(label, style: const TextStyle(color: Colors.grey, fontSize: 12.5)),
            ),
            Expanded(
              child: Text(value,
                  textAlign: TextAlign.right,
                  style: TextStyle(color: color, fontSize: 12.5, fontWeight: FontWeight.bold)),
            ),
          ],
        ),
      );

  Widget _condList(String title, dynamic items, Color color) {
    final list = (items as List?) ?? const [];
    if (list.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 12.5)),
          const SizedBox(height: 4),
          for (final c in list)
            Padding(
              padding: const EdgeInsets.only(top: 3),
              child: Text('· $c',
                  style: const TextStyle(color: Colors.white70, fontSize: 12, height: 1.45)),
            ),
        ],
      ),
    );
  }

  static Color _riskColor(dynamic level) => switch ('$level') {
        '높음' => Colors.redAccent,
        '낮음' => const Color(0xFF00D084),
        _ => Colors.amber,
      };

  // 앱 전체 관행과 동일: 이익 초록, 손실 빨강
  static Color _profitColor(double v) {
    if (v > 0) return const Color(0xFF00D084);
    if (v < 0) return Colors.redAccent;
    return Colors.white;
  }
}

class _TickerListSection extends StatelessWidget {
  final TradingProvider provider;
  const _TickerListSection({required this.provider});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.only(bottom: 8),
          child: Text('종목 목록', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
        ),
        if (provider.tickers.isEmpty)
          const Card(
            color: Color(0xFF161B22),
            child: Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: Text('등록된 종목이 없습니다', style: TextStyle(color: Colors.grey))),
            ),
          )
        else
          ...provider.tickers.map((t) => _TickerCard(ticker: t, provider: provider)),
      ],
    );
  }
}

class _TickerCard extends StatelessWidget {
  final TickerInfo ticker;
  final TradingProvider provider;
  const _TickerCard({required this.ticker, required this.provider});

  @override
  Widget build(BuildContext context) {
    final fmt = NumberFormat('#,###');
    final profit = ticker.realizedProfit;
    final profitColor = profit >= 0 ? const Color(0xFF00D084) : Colors.redAccent;

    return Card(
      color: const Color(0xFF161B22),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      margin: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => TickerDetailScreen(ticker: ticker)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(ticker.name,
                            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                        Text(ticker.ticker,
                            style: const TextStyle(color: Colors.grey, fontSize: 12)),
                      ],
                    ),
                  ),
                  Text('${fmt.format(ticker.price)}원',
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  StatusBadge(text: ticker.status),
                  const Spacer(),
                  if (ticker.positionQty > 0)
                    Text('보유 ${ticker.positionQty}주  ${fmt.format(ticker.avgPrice.toInt())}원',
                        style: const TextStyle(color: Colors.grey, fontSize: 12)),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('전략: ${ticker.buyRule}',
                      style: const TextStyle(color: Colors.grey, fontSize: 12)),
                  Text('실현손익: ${fmt.format(profit.toInt())}원',
                      style: TextStyle(color: profitColor, fontSize: 12, fontWeight: FontWeight.bold)),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  IconButton(
                    icon: Icon(ticker.paused ? Icons.play_arrow : Icons.pause,
                        color: ticker.paused ? const Color(0xFF00D084) : Colors.amber, size: 20),
                    onPressed: () => provider.togglePause(ticker),
                    tooltip: ticker.paused ? '재개' : '일시정지',
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(),
                  ),
                  const SizedBox(width: 12),
                  IconButton(
                    icon: const Icon(Icons.delete_outline, color: Colors.redAccent, size: 20),
                    onPressed: () => _confirmDelete(context),
                    tooltip: '삭제',
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _confirmDelete(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF161B22),
        title: const Text('종목 삭제'),
        content: Text('${ticker.name}(${ticker.ticker})을 삭제하시겠습니까?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('취소')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () async {
              await provider.removeTicker(ticker.ticker);
              if (ctx.mounted) Navigator.pop(ctx);
            },
            child: const Text('삭제'),
          ),
        ],
      ),
    );
  }
}

class _LogSection extends StatelessWidget {
  final List<String> logs;
  const _LogSection({required this.logs});

  @override
  Widget build(BuildContext context) {
    return Card(
      color: const Color(0xFF161B22),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.list_alt, color: Color(0xFF00D084), size: 16),
                SizedBox(width: 6),
                Text('최근 로그', style: TextStyle(fontWeight: FontWeight.bold)),
              ],
            ),
            const SizedBox(height: 8),
            if (logs.isEmpty)
              const Text('로그 없음', style: TextStyle(color: Colors.grey))
            else
              ...logs.take(20).map(
                (log) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Text(log,
                      style: const TextStyle(fontSize: 12, color: Color(0xFFB0B8C1)),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// 종목 검색 + 추가 다이얼로그
// ─────────────────────────────────────────────
class _AddTickerDialog extends StatefulWidget {
  final TradingProvider provider;
  const _AddTickerDialog({required this.provider});

  @override
  State<_AddTickerDialog> createState() => _AddTickerDialogState();
}

class _AddTickerDialogState extends State<_AddTickerDialog> {
  final _searchCtrl = TextEditingController();
  String _selectedTicker = '';
  String _selectedName = '';
  String _selectedRule = 'DEFAULT';
  List<Map<String, dynamic>> _searchResults = [];
  List<String> _strategies = ['DEFAULT', 'NONE'];
  bool _isSearching = false;
  bool _isAdding = false;

  @override
  void initState() {
    super.initState();
    widget.provider.getStrategies().then((list) {
      if (mounted) setState(() => _strategies = list);
    });
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  Future<void> _onSearchChanged(String query) async {
    if (query.length < 2) {
      setState(() { _searchResults = []; _isSearching = false; });
      return;
    }
    setState(() => _isSearching = true);
    await Future.delayed(const Duration(milliseconds: 500));
    if (_searchCtrl.text != query) return; // 디바운스: 입력이 바뀌면 취소
    final results = await widget.provider.searchTickers(query);
    if (mounted) setState(() { _searchResults = results; _isSearching = false; });
  }

  void _selectTicker(Map<String, dynamic> item) {
    final ticker = (item['ticker'] ?? '').toString().split('.').first;
    final name   = (item['name'] ?? ticker).toString();
    setState(() {
      _selectedTicker = ticker;
      _selectedName   = name;
      _searchCtrl.text = '$name ($ticker)';
      _searchResults   = [];
    });
  }

  Future<void> _submit(BuildContext ctx) async {
    final code = _selectedTicker.isNotEmpty
        ? _selectedTicker
        : _searchCtrl.text.trim();
    if (code.isEmpty) return;
    setState(() => _isAdding = true);
    await widget.provider.addTicker(code, _selectedRule);
    if (ctx.mounted) Navigator.pop(ctx);
  }

  @override
  Widget build(BuildContext context) {
    final hasSelection = _selectedTicker.isNotEmpty;

    return Dialog(
      backgroundColor: const Color(0xFF161B22),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Container(
        width: 420,
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── 제목
            Row(
              children: [
                const Icon(Icons.add_circle_outline, color: Color(0xFF00D084), size: 20),
                const SizedBox(width: 8),
                const Text('종목 추가',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              ],
            ),
            const SizedBox(height: 20),

            // ── 검색창
            TextField(
              controller: _searchCtrl,
              autofocus: true,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                hintText: '종목명 또는 코드 입력 (예: 삼성, 005930)',
                hintStyle: const TextStyle(color: Colors.grey),
                prefixIcon: const Icon(Icons.search, color: Colors.grey),
                suffixIcon: _isSearching
                    ? const Padding(
                        padding: EdgeInsets.all(12),
                        child: SizedBox(
                          width: 16, height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2,
                              color: Color(0xFF00D084)),
                        ))
                    : (_searchCtrl.text.isNotEmpty
                        ? IconButton(
                            icon: const Icon(Icons.clear, color: Colors.grey),
                            onPressed: () {
                              _searchCtrl.clear();
                              setState(() {
                                _selectedTicker = '';
                                _selectedName = '';
                                _searchResults = [];
                              });
                            })
                        : null),
                filled: true,
                fillColor: const Color(0xFF0D1117),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                  borderSide: BorderSide.none,
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                  borderSide: const BorderSide(color: Color(0xFF00D084), width: 1.5),
                ),
              ),
              onChanged: (v) {
                setState(() { _selectedTicker = ''; _selectedName = ''; });
                _onSearchChanged(v);
              },
            ),

            // ── 검색 결과 목록
            if (_searchResults.isNotEmpty) ...[
              const SizedBox(height: 6),
              Container(
                constraints: const BoxConstraints(maxHeight: 200),
                decoration: BoxDecoration(
                  color: const Color(0xFF0D1117),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: const Color(0xFF30363D)),
                ),
                child: ListView.separated(
                  shrinkWrap: true,
                  itemCount: _searchResults.length,
                  separatorBuilder: (_, __) =>
                      const Divider(height: 1, color: Color(0xFF30363D)),
                  itemBuilder: (_, i) {
                    final item = _searchResults[i];
                    final ticker = (item['ticker'] ?? '').toString().split('.').first;
                    final name   = (item['name'] ?? ticker).toString();
                    return ListTile(
                      dense: true,
                      leading: Container(
                        width: 36, height: 36,
                        decoration: BoxDecoration(
                          color: const Color(0xFF1C2128),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(Icons.bar_chart, color: Color(0xFF00D084), size: 18),
                      ),
                      title: Text(name,
                          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                      subtitle: Text(ticker,
                          style: const TextStyle(fontSize: 12, color: Colors.grey)),
                      onTap: () => _selectTicker(item),
                    );
                  },
                ),
              ),
            ],

            // ── 선택된 종목 표시
            if (hasSelection) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                decoration: BoxDecoration(
                  color: const Color(0xFF00D084).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFF00D084).withOpacity(0.4)),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.check_circle, color: Color(0xFF00D084), size: 16),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text('$_selectedName  ($_selectedTicker)',
                          style: const TextStyle(color: Color(0xFF00D084),
                              fontSize: 13, fontWeight: FontWeight.w600)),
                    ),
                  ],
                ),
              ),
            ],

            const SizedBox(height: 16),

            // ── 전략 선택
            DropdownButtonFormField<String>(
              value: _selectedRule,
              dropdownColor: const Color(0xFF1C2128),
              decoration: InputDecoration(
                labelText: '전략 선택',
                labelStyle: const TextStyle(color: Colors.grey),
                filled: true,
                fillColor: const Color(0xFF0D1117),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                  borderSide: BorderSide.none,
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                  borderSide: const BorderSide(color: Color(0xFF00D084)),
                ),
              ),
              items: _strategies
                  .map((s) => DropdownMenuItem(value: s, child: Text(s)))
                  .toList(),
              onChanged: (v) => setState(() => _selectedRule = v!),
            ),

            const SizedBox(height: 24),

            // ── 버튼
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('취소', style: TextStyle(color: Colors.grey)),
                ),
                const SizedBox(width: 12),
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF00D084),
                    foregroundColor: Colors.black,
                    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  onPressed: _isAdding ? null : () => _submit(context),
                  icon: _isAdding
                      ? const SizedBox(
                          width: 16, height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black))
                      : const Icon(Icons.add, size: 18),
                  label: Text(_isAdding ? '추가 중...' : '추가',
                      style: const TextStyle(fontWeight: FontWeight.bold)),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
