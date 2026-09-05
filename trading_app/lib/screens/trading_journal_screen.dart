import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';
import '../providers/trading_provider.dart';
import '../widgets/market_tab_bar.dart';
import 'package:shared_preferences/shared_preferences.dart';

class TradingJournalScreen extends StatefulWidget {
  const TradingJournalScreen({super.key});

  @override
  State<TradingJournalScreen> createState() => _TradingJournalScreenState();
}

class _TradingJournalScreenState extends State<TradingJournalScreen> {
  DateTime _selectedDate = DateTime.now();
  List<Map<String, dynamic>> _allTrades = [];
  bool _isLoading = false;
  bool _isSyncing = false;
  String _displayMode = 'ticker'; // 'ticker' (합산) or 'detail' (상세)
  String _market = 'DOMESTIC'; // 국내/해외 탭 (종목코드 형식으로 구분)

  /// 현재 탭(국내/해외)에 해당하는 매매만 (숫자 종목코드 = 국내)
  List<Map<String, dynamic>> get _trades => _allTrades
      .where((t) => MarketUtil.ofTicker(t['ticker']) == _market)
      .toList();

  @override
  void initState() {
    super.initState();
    _loadSavedDate();
  }

  Future<void> _loadSavedDate() async {
    final prefs = await SharedPreferences.getInstance();
    final savedDateStr = prefs.getString('last_journal_date');
    if (savedDateStr != null) {
      try {
        setState(() {
          _selectedDate = DateTime.parse(savedDateStr);
        });
      } catch (e) {
        // Ignore parse errors
      }
    }
    _fetchTrades();
  }

  Future<void> _saveSelectedDate() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('last_journal_date', DateFormat('yyyy-MM-dd').format(_selectedDate));
  }

  Future<void> _fetchTrades() async {
    setState(() => _isLoading = true);
    try {
      final dateStr = DateFormat('yyyy-MM-dd').format(_selectedDate);
      final results = await context.read<TradingProvider>().getTrades(dateStr);
      if (mounted) {
        setState(() {
          _allTrades = results;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _isLoading = false);
    }
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

  Future<void> _syncFromKiwoom() async {
    final dateLabel = DateFormat('yyyy-MM-dd').format(_selectedDate);
    if (!await _confirmAction('매매일지 업데이트',
        '$dateLabel 매매 내역을 키움 API에서 다시 불러올까요?\n해당 날짜의 기존 내역은 새 데이터로 교체됩니다.')) return;
    if (!mounted) return;
    setState(() => _isSyncing = true);
    try {
      final dateStr = DateFormat('yyyy-MM-dd').format(_selectedDate);
      await context.read<TradingProvider>().syncTrades(dateStr);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('동기화 명령 전송 완료')),
        );
        Future.delayed(const Duration(seconds: 2), _fetchTrades);
      }
    } finally {
      if (mounted) setState(() => _isSyncing = false);
    }
  }

  // ── 구글 시트 업로드 (월별 탭 + 일별요약) ──
  bool _exporting = false;
  String? _gsheetUrl;

  Future<void> _exportToGSheet() async {
    if (_exporting) return;
    final dateLabel = DateFormat('yyyy-MM-dd').format(_selectedDate);
    if (!await _confirmAction('구글 시트 업로드',
        '$dateLabel 매매일지를 구글 시트에 업로드할까요?\n같은 날짜의 기존 행은 덮어씁니다.')) return;
    if (!mounted) return;
    setState(() => _exporting = true);
    try {
      final dateStr = DateFormat('yyyy-MM-dd').format(_selectedDate);
      final res = await context.read<TradingProvider>().exportTradesToGSheet(dateStr);
      if (!mounted) return;
      if (res['status'] == 'SUCCESS') {
        setState(() => _gsheetUrl = res['url'] as String?);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('구글 시트 업로드 완료 (매매 ${res['rows']}건)'),
          behavior: SnackBarBehavior.floating,
        ));
      } else {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('업로드 실패: ${res['message'] ?? res['msg'] ?? '알 수 없는 오류'}'),
          behavior: SnackBarBehavior.floating,
        ));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('업로드 오류: $e'), behavior: SnackBarBehavior.floating));
      }
    } finally {
      if (mounted) setState(() => _exporting = false);
    }
  }

  Future<void> _openGSheet() async {
    final url = _gsheetUrl;
    if (url == null) return;
    try {
      await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('시트를 열 수 없습니다: $e'), behavior: SnackBarBehavior.floating));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final fmt = NumberFormat('#,###');

    // ── 데이터 처리 ──
    List<Map<String, dynamic>> displayList = [];
    double totalDayProfit = 0;

    if (_displayMode == 'ticker') {
      // ── 종목별 합산 로직 (PC 웹과 동일) ──
      final Map<String, bool> hasSummary = {};
      for (var t in _trades) {
        if (t['side']?.toString() == 'SUMMARY') {
          hasSummary[t['ticker']?.toString() ?? ''] = true;
        }
      }

      final Map<String, Map<String, dynamic>> groups = {};
      final Set<String> processedOrders = {};

      for (var t in _trades) {
        final ticker = t['ticker']?.toString() ?? '';
        if (ticker.isEmpty) continue;

        final side = t['side']?.toString() ?? '';
        if (hasSummary[ticker] == true && (side == 'BUY' || side == 'SELL')) continue;

        final orderNo = t['order_no']?.toString() ?? '';
        if (orderNo.isNotEmpty) {
          if (processedOrders.contains(orderNo)) continue;
          processedOrders.add(orderNo);
        }

        if (!groups.containsKey(ticker)) {
          groups[ticker] = {
            'ticker': ticker,
            'ticker_name': t['ticker_name'] ?? '-',
            'buy_amount': 0.0,
            'sell_amount': 0.0,
            'buy_qty': 0,
            'sell_qty': 0,
            'profit': 0.0,
            'fee': 0.0,
            'tax': 0.0,
            'side': 'SUMMARY',
            'time_str': t['time_str'],
          };
        }

        final g = groups[ticker]!;
        final double profit = double.tryParse(t['profit']?.toString() ?? '0') ?? 0;
        final int qty = (double.tryParse(t['qty']?.toString() ?? '0') ?? 0).toInt();
        final double fee = double.tryParse(t['fee']?.toString() ?? '0') ?? 0;
        final double tax = double.tryParse(t['tax']?.toString() ?? '0') ?? 0;

        if (side == 'SUMMARY' || side == 'BUY') {
          final bAmt = double.tryParse(t['buy_amount']?.toString() ?? '0') ?? 
                     (side == 'BUY' ? (double.tryParse(t['amount']?.toString() ?? '0') ?? 0) : 0);
          g['buy_amount'] = (g['buy_amount'] as double) + bAmt;
          g['buy_qty'] = (g['buy_qty'] as int) + qty;
        }
        
        if (side == 'SUMMARY' || side == 'SELL') {
          final sAmt = double.tryParse(t['amount']?.toString() ?? '0') ?? 0;
          g['sell_amount'] = (g['sell_amount'] as double) + sAmt;
          g['sell_qty'] = (g['sell_qty'] as int) + qty;
        }

        g['profit'] = (g['profit'] as double) + profit;
        g['fee'] = (g['fee'] as double) + fee;
        g['tax'] = (g['tax'] as double) + tax;
      }

      displayList = groups.values.map((g) {
        final buyAmt = g['buy_amount'] as double;
        final sellAmt = g['sell_amount'] as double;
        final profit = g['profit'] as double;
        final buyQty = g['buy_qty'] as int;
        final sellQty = g['sell_qty'] as int;

        return {
          ...g,
          'buy_price': buyQty > 0 ? buyAmt / buyQty : 0.0,
          'price': sellQty > 0 ? sellAmt / sellQty : 0.0,
          'qty': sellQty > 0 ? sellQty : buyQty,
          'profit_rate': buyAmt > 0 ? (profit / buyAmt) * 100 : 0.0,
        };
      }).where((g) => (g['profit'] as double).abs() > 0).toList();
      
      displayList.sort((a, b) => (a['ticker_name'] ?? '').compareTo(b['ticker_name'] ?? ''));
    } else {
      // ── 상세 내역 모드 ──
      displayList = _trades.map((t) {
        final double p = double.tryParse(t['profit']?.toString() ?? '0') ?? 0;
        final double bAmt = double.tryParse(t['buy_amount']?.toString() ?? '0') ?? (t['side'] == 'BUY' ? (double.tryParse(t['amount']?.toString() ?? '0') ?? 0) : 0);
        
        return {
          ...t,
          'profit_rate': bAmt > 0 ? (p / bAmt) * 100 : 0.0,
        };
      }).toList();
      // 시간순 정렬 (최신순)
      displayList.sort((a, b) => (b['time_str'] ?? '').compareTo(a['time_str'] ?? ''));
    }

    // ── 합산 데이터를 항상 계산하여 정확한 일일 손익 산출 ──
    final Map<String, bool> hasSummaryForTotal = {};
    for (var t in _trades) {
      if (t['side']?.toString() == 'SUMMARY') {
        hasSummaryForTotal[t['ticker']?.toString() ?? ''] = true;
      }
    }

    final Map<String, double> tickerProfits = {};
    final Set<String> processedForTotal = {};

    for (var t in _trades) {
      final ticker = t['ticker']?.toString() ?? '';
      if (ticker.isEmpty) continue;

      final side = t['side']?.toString() ?? '';
      if (hasSummaryForTotal[ticker] == true && (side == 'BUY' || side == 'SELL')) continue;

      final orderNo = t['order_no']?.toString() ?? '';
      if (orderNo.isNotEmpty) {
        if (processedForTotal.contains(orderNo)) continue;
        processedForTotal.add(orderNo);
      }

      final double p = double.tryParse(t['profit']?.toString() ?? '0') ?? 0;
      tickerProfits[ticker] = (tickerProfits[ticker] ?? 0) + p;
    }
    
    totalDayProfit = tickerProfits.values.fold(0, (sum, p) => sum + p);


    final profitColor = totalDayProfit >= 0 ? const Color(0xFF00D084) : Colors.redAccent;

    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      appBar: AppBar(
        backgroundColor: const Color(0xFF161B22),
        title: const Text('매매일지', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _fetchTrades),
        ],
      ),
      body: Column(
        children: [
          // 국내/해외 탭 (종목코드 형식으로 구분)
          MarketTabBar(market: _market, onChanged: (m) => setState(() => _market = m)),
          // 필터 및 전체 요약 바
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            color: const Color(0xFF161B22),
            child: Row(
              children: [
                Expanded(
                  child: InkWell(
                    onTap: () async {
                      final date = await showDatePicker(
                        context: context,
                        initialDate: _selectedDate,
                        firstDate: DateTime(2020),
                        lastDate: DateTime.now(),
                      );
                      if (date != null) {
                        setState(() => _selectedDate = date);
                        _saveSelectedDate();
                        _fetchTrades();
                      }
                    },
                    child: Row(
                      children: [
                        const Icon(Icons.calendar_today, color: Color(0xFF00D084), size: 16),
                        const SizedBox(width: 8),
                        Text(DateFormat('yyyy-MM-dd').format(_selectedDate), 
                             style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
                      ],
                    ),
                  ),
                ),
                // 모드 전환 토글
                Container(
                  height: 32,
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  decoration: BoxDecoration(
                    color: Colors.black26,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    children: [
                      _ModeToggleBtn(
                        label: '합산', 
                        isSelected: _displayMode == 'ticker', 
                        onTap: () => setState(() => _displayMode = 'ticker')
                      ),
                      _ModeToggleBtn(
                        label: '상세', 
                        isSelected: _displayMode == 'detail', 
                        onTap: () => setState(() => _displayMode = 'detail')
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                Text('${totalDayProfit >= 0 ? '+' : ''}${fmt.format(totalDayProfit.toInt())}원',
                     style: TextStyle(color: profitColor, fontWeight: FontWeight.bold, fontSize: 14)),
              ],
            ),
          ),
          // 업데이트(키움 동기화) / 구글 시트 업로드 버튼
          Container(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            color: const Color(0xFF161B22),
            child: Row(
              children: [
                OutlinedButton.icon(
                  onPressed: _isSyncing ? null : _syncFromKiwoom,
                  icon: _isSyncing
                      ? const SizedBox(width: 12, height: 12,
                          child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.refresh, size: 14),
                  label: Text(_isSyncing ? '업데이트 중' : '업데이트'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: const Color(0xFF4FC3F7),
                    side: const BorderSide(color: Color(0xFF4FC3F7)),
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 0),
                    minimumSize: Size.zero,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    textStyle: const TextStyle(fontSize: 12),
                  ),
                ),
                const SizedBox(width: 8),
                OutlinedButton.icon(
                  onPressed: _exporting ? null : _exportToGSheet,
                  icon: _exporting
                      ? const SizedBox(width: 12, height: 12,
                          child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text('📗', style: TextStyle(fontSize: 12)),
                  label: Text(_exporting ? '업로드 중' : '구글 시트 업로드'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: const Color(0xFF34A853),
                    side: const BorderSide(color: Color(0xFF34A853)),
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 0),
                    minimumSize: Size.zero,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    textStyle: const TextStyle(fontSize: 12),
                  ),
                ),
                if (_gsheetUrl != null) ...[
                  const SizedBox(width: 4),
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
                ],
              ],
            ),
          ),
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator(color: Color(0xFF00D084)))
                : displayList.isEmpty
                    ? const Center(child: Text('매매 내역이 없습니다', style: TextStyle(color: Colors.grey)))
                    : ListView.builder(
                        padding: const EdgeInsets.all(12),
                        itemCount: displayList.length,
                        itemBuilder: (context, index) => _TradeCard(trade: displayList[index], isSummary: _displayMode == 'ticker'),
                      ),
          ),
        ],
      ),
    );
  }
}

class _ModeToggleBtn extends StatelessWidget {
  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  const _ModeToggleBtn({required this.label, required this.isSelected, required this.onTap});

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
            fontSize: 11,
            fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
          ),
        ),
      ),
    );
  }
}

class _TradeCard extends StatelessWidget {
  final Map<String, dynamic> trade;
  final bool isSummary;
  const _TradeCard({required this.trade, required this.isSummary});

  @override
  Widget build(BuildContext context) {
    final fmt = NumberFormat('#,###');
    final profit = double.tryParse(trade['profit']?.toString() ?? '0') ?? 0;
    final ratio = double.tryParse(trade['profit_rate']?.toString() ?? '0') ?? 0;
    final feeTax = (double.tryParse(trade['fee']?.toString() ?? '0') ?? 0) + (double.tryParse(trade['tax']?.toString() ?? '0') ?? 0);
    final String side = trade['side']?.toString() ?? 'BUY';
    final qty = (double.tryParse(trade['qty']?.toString() ?? '0') ?? 0).toInt();

    return Card(
      color: const Color(0xFF161B22),
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
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
                      Text(trade['ticker_name'] ?? '-', 
                           style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                      Text(trade['ticker'] ?? '-', 
                           style: const TextStyle(color: Colors.grey, fontSize: 12)),
                    ],
                  ),
                ),
                _SideBadge(side: side),
              ],
            ),
            const Divider(color: Color(0xFF30363D), height: 24),
            if (isSummary || side == 'SUMMARY') ...[
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  _InfoItem(label: '평균매수', value: '${fmt.format((double.tryParse(trade['buy_price']?.toString() ?? '0') ?? 0).toInt())}원'),
                  _InfoItem(label: '평균매도', value: '${fmt.format((double.tryParse(trade['price']?.toString() ?? '0') ?? 0).toInt())}원'),
                  _InfoItem(label: '수량', value: '${fmt.format(qty)}주'),
                ],
              ),
            ] else if (side == 'BUY') ...[
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  _InfoItem(label: '매수단가', value: '${fmt.format((double.tryParse(trade['price']?.toString() ?? '0') ?? 0).toInt())}원'),
                  _InfoItem(label: '수량', value: '${fmt.format(qty)}주'),
                  _InfoItem(label: '체결시간', value: trade['time_str']?.split(' ').last ?? '-'),
                ],
              ),
            ] else ...[
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  _InfoItem(label: '매도단가', value: '${fmt.format((double.tryParse(trade['price']?.toString() ?? '0') ?? 0).toInt())}원'),
                  _InfoItem(label: '수량', value: '${fmt.format(qty)}주'),
                  _InfoItem(label: '체결시간', value: trade['time_str']?.split(' ').last ?? '-'),
                ],
              ),
            ],
            if (side != 'BUY') ...[
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  _InfoItem(label: '수수료+제세금', value: '${fmt.format(feeTax.toInt())}원', isMuted: true),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text('${profit >= 0 ? '+' : ''}${fmt.format(profit.toInt())}원',
                           style: TextStyle(color: profit >= 0 ? const Color(0xFF00D084) : Colors.redAccent, 
                                          fontWeight: FontWeight.bold, fontSize: 14)),
                      Text('${ratio >= 0 ? '+' : ''}${ratio.toStringAsFixed(2)}%',
                           style: TextStyle(color: ratio >= 0 ? const Color(0xFF00D084) : Colors.redAccent, fontSize: 12)),
                    ],
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _SideBadge extends StatelessWidget {
  final String side;
  const _SideBadge({required this.side});

  @override
  Widget build(BuildContext context) {
    Color color = Colors.amber;
    String text = '정산';
    if (side == 'BUY') {
      color = Colors.redAccent;
      text = '매수';
    } else if (side == 'SELL') {
      color = Colors.blueAccent;
      text = '매도';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: color.withOpacity(0.1), borderRadius: BorderRadius.circular(4)),
      child: Text(text, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.bold)),
    );
  }
}

class _InfoItem extends StatelessWidget {
  final String label;
  final String value;
  final bool isMuted;
  const _InfoItem({required this.label, required this.value, this.isMuted = false});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: Colors.grey, fontSize: 10)),
        const SizedBox(height: 2),
        Text(value, style: TextStyle(color: isMuted ? Colors.grey : Colors.white, fontSize: 12, fontWeight: FontWeight.bold)),
      ],
    );
  }
}
