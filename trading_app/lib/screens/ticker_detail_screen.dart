import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../providers/trading_provider.dart';
import '../widgets/status_badge.dart';
import 'package:intl/intl.dart';

class TickerDetailScreen extends StatelessWidget {
  final TickerInfo ticker;

  const TickerDetailScreen({super.key, required this.ticker});

  @override
  Widget build(BuildContext context) {
    final fmt = NumberFormat('#,###');
    final provider = context.read<TradingProvider>();

    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      appBar: AppBar(
        backgroundColor: const Color(0xFF161B22),
        title: Text(ticker.name),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _InfoCard(ticker: ticker),
          const SizedBox(height: 12),
          _ActionCard(ticker: ticker, provider: provider),
        ],
      ),
    );
  }
}

class _InfoCard extends StatelessWidget {
  final TickerInfo ticker;
  const _InfoCard({required this.ticker});

  @override
  Widget build(BuildContext context) {
    final fmt = NumberFormat('#,###');
    return Card(
      color: const Color(0xFF161B22),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            _Row('종목코드', ticker.ticker),
            _Row('현재가', '${fmt.format(ticker.price)}원'),
            _Row('전략', ticker.buyRule),
            _Row('상태', ticker.status),
            _Row('보유수량', '${ticker.positionQty}주'),
            _Row('평균단가', '${fmt.format(ticker.avgPrice.toInt())}원'),
            _Row('실현손익', '${fmt.format(ticker.realizedProfit.toInt())}원',
                valueColor: ticker.realizedProfit >= 0
                    ? const Color(0xFF00D084)
                    : Colors.redAccent),
          ],
        ),
      ),
    );
  }
}

class _Row extends StatelessWidget {
  final String label;
  final String value;
  final Color? valueColor;
  const _Row(this.label, this.value, {this.valueColor});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.grey)),
          Text(value,
              style: TextStyle(
                  color: valueColor ?? Colors.white, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }
}

class _ActionCard extends StatefulWidget {
  final TickerInfo ticker;
  final TradingProvider provider;
  const _ActionCard({required this.ticker, required this.provider});

  @override
  State<_ActionCard> createState() => _ActionCardState();
}

class _ActionCardState extends State<_ActionCard> {
  String _selectedRule = 'DEFAULT';
  List<String> _strategies = ['DEFAULT', 'NONE'];

  @override
  void initState() {
    super.initState();
    _selectedRule = widget.ticker.buyRule;
    widget.provider.getStrategies().then((s) {
      if (mounted) setState(() => _strategies = s);
    });
  }

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
            const Text('Actions', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              value: _strategies.contains(_selectedRule) ? _selectedRule : _strategies.first,
              dropdownColor: const Color(0xFF1C2128),
              decoration: const InputDecoration(
                  labelText: '전략 변경', border: OutlineInputBorder()),
              items: _strategies
                  .map((s) => DropdownMenuItem(value: s, child: Text(s)))
                  .toList(),
              onChanged: (v) => setState(() => _selectedRule = v!),
            ),
            const SizedBox(height: 8),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF00D084)),
                onPressed: () async {
                  await widget.provider.setRule(widget.ticker.ticker, _selectedRule);
                  if (context.mounted) Navigator.pop(context);
                },
                child: const Text('전략 적용', style: TextStyle(color: Colors.black)),
              ),
            ),
            const SizedBox(height: 8),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                icon: Icon(widget.ticker.paused ? Icons.play_arrow : Icons.pause),
                label: Text(widget.ticker.paused ? '재개' : '일시정지'),
                onPressed: () async {
                  await widget.provider.togglePause(widget.ticker);
                  if (context.mounted) Navigator.pop(context);
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
