import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/trading_provider.dart';
import '../widgets/market_tab_bar.dart';

/// AI Notice — 메신저(디스코드)로 발송된 AI 알림 조회
/// (전략 이탈 감시 / 아침 브리핑 / 매매일지 복기, 웹 AI Notice 탭과 동일 API)
class AiNoticesScreen extends StatefulWidget {
  const AiNoticesScreen({super.key});

  @override
  State<AiNoticesScreen> createState() => _AiNoticesScreenState();
}

class _AiNoticesScreenState extends State<AiNoticesScreen> {
  List<Map<String, dynamic>> _notices = [];
  String _filter = '';
  String _market = 'DOMESTIC'; // 국내/해외 탭
  bool _loading = true;
  final Set<int> _expanded = {};
  Timer? _timer;

  static const _categories = [
    ('', '전체'),
    ('전략감시', '⚡ 전략감시'),
    ('브리핑', '☀️ 브리핑'),
    ('복기', '📋 복기'),
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
    _timer = Timer.periodic(const Duration(seconds: 60), (_) => _load(silent: true));
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _load({bool silent = false}) async {
    try {
      final list = await context.read<TradingProvider>().api.getAiNotices();
      if (!mounted) return;
      setState(() {
        _notices =
            list.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _loading = false);
      if (!silent) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('알림 조회 실패: $e'), behavior: SnackBarBehavior.floating),
        );
      }
    }
  }

  List<Map<String, dynamic>> get _filtered => _notices
      .where((n) => MarketUtil.of(n) == _market)
      .where((n) => _filter.isEmpty || '${n['category']}' == _filter)
      .toList();

  static Color _levelColor(dynamic level) => switch ('$level') {
        'critical' => Colors.redAccent,
        'warning' => Colors.amber,
        'good' => const Color(0xFF00D084),
        _ => const Color(0xFF4FC3F7),
      };

  static Color _categoryColor(dynamic cat) => switch ('$cat') {
        '전략감시' => Colors.amber,
        '브리핑' => const Color(0xFF4FC3F7),
        '복기' => const Color(0xFF00D084),
        _ => Colors.grey,
      };

  /// 디스코드용 마크다운 볼드 제거
  static String _clean(dynamic msg) => '$msg'.replaceAll('**', '');

  static String _preview(dynamic msg) {
    final lines =
        _clean(msg).split('\n').where((l) => l.trim().isNotEmpty).toList();
    final t = lines.take(2).join(' · ');
    return t.length > 120 ? '${t.substring(0, 120)}…' : t;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      appBar: AppBar(
        backgroundColor: const Color(0xFF161B22),
        title: const Text('AI Notice', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: '새로고침',
            onPressed: _load,
          ),
        ],
      ),
      body: Column(
        children: [
          // 국내/해외 탭
          MarketTabBar(market: _market, onChanged: (m) => setState(() => _market = m)),
          // 카테고리 필터
          SizedBox(
            height: 52,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              children: [
                for (final (value, label) in _categories)
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: FilterChip(
                      label: Text(label),
                      selected: _filter == value,
                      onSelected: (_) => setState(() => _filter = value),
                      backgroundColor: const Color(0xFF161B22),
                      selectedColor: const Color(0xFF00D084).withOpacity(0.2),
                      labelStyle: TextStyle(
                        color: _filter == value ? const Color(0xFF00D084) : Colors.white70,
                        fontSize: 13,
                      ),
                      side: BorderSide(
                        color: _filter == value
                            ? const Color(0xFF00D084)
                            : Colors.white24,
                      ),
                    ),
                  ),
              ],
            ),
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : RefreshIndicator(
                    onRefresh: _load,
                    child: _filtered.isEmpty
                        ? ListView(
                            children: const [
                              SizedBox(height: 120),
                              Center(
                                child: Text(
                                  '표시할 알림이 없습니다.\n전략 감시·브리핑·복기가 발송되면 여기에 쌓입니다.',
                                  textAlign: TextAlign.center,
                                  style: TextStyle(color: Colors.white54, height: 1.6),
                                ),
                              ),
                            ],
                          )
                        : ListView.builder(
                            padding: const EdgeInsets.fromLTRB(12, 4, 12, 16),
                            itemCount: _filtered.length,
                            itemBuilder: (context, i) => _noticeCard(_filtered[i]),
                          ),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _noticeCard(Map<String, dynamic> n) {
    final id = (n['id'] as num?)?.toInt() ?? 0;
    final expanded = _expanded.contains(id);
    final catColor = _categoryColor(n['category']);

    return Card(
      color: const Color(0xFF161B22),
      margin: const EdgeInsets.only(bottom: 10),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: _levelColor(n['level']).withOpacity(0.5)),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => setState(() {
          expanded ? _expanded.remove(id) : _expanded.add(id);
        }),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: catColor.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text('${n['category']}',
                        style: TextStyle(color: catColor, fontSize: 11,
                            fontWeight: FontWeight.bold)),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text('${n['title']}',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                            color: Colors.white, fontWeight: FontWeight.w600)),
                  ),
                  Icon(expanded ? Icons.expand_less : Icons.expand_more,
                      color: Colors.white38, size: 18),
                ],
              ),
              const SizedBox(height: 6),
              Text('${n['created_at']}',
                  style: const TextStyle(color: Colors.white38, fontSize: 11)),
              const SizedBox(height: 6),
              expanded
                  ? Text(_clean(n['message']),
                      style: const TextStyle(
                          color: Colors.white70, fontSize: 13, height: 1.55))
                  : Text(_preview(n['message']),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: Colors.white54, fontSize: 12.5)),
            ],
          ),
        ),
      ),
    );
  }
}
