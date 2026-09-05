import 'package:flutter/material.dart';

/// 국내/해외 구분 탭 — 매매일지·AI종목·AI매매·AI캘린더·AI Notice 공용
class MarketTabBar extends StatelessWidget {
  final String market; // 'DOMESTIC' | 'OVERSEAS'
  final ValueChanged<String> onChanged;

  const MarketTabBar({super.key, required this.market, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return Container(
      color: const Color(0xFF161B22),
      padding: const EdgeInsets.fromLTRB(12, 6, 12, 8),
      child: Row(
        children: [
          _tab('🇰🇷 국내', 'DOMESTIC'),
          const SizedBox(width: 8),
          _tab('🌎 해외', 'OVERSEAS'),
        ],
      ),
    );
  }

  Widget _tab(String label, String value) {
    final selected = market == value;
    return Expanded(
      child: GestureDetector(
        onTap: () {
          if (!selected) onChanged(value);
        },
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 8),
          decoration: BoxDecoration(
            color: selected ? const Color(0xFF00D084).withOpacity(0.15) : Colors.black26,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: selected ? const Color(0xFF00D084) : Colors.white12,
            ),
          ),
          child: Text(
            label,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: selected ? const Color(0xFF00D084) : Colors.grey,
              fontWeight: selected ? FontWeight.bold : FontWeight.normal,
              fontSize: 13,
            ),
          ),
        ),
      ),
    );
  }
}

/// 항목의 시장 구분 판정 유틸
class MarketUtil {
  /// 프로파일/알림의 market 필드 (없으면 국내)
  static String of(Map<String, dynamic> item) =>
      (item['market'] == 'OVERSEAS') ? 'OVERSEAS' : 'DOMESTIC';

  /// 종목코드 형식으로 판정 (숫자 = 국내, 그 외 = 해외)
  static String ofTicker(dynamic ticker) {
    final t = '$ticker'.trim();
    if (t.isEmpty) return 'DOMESTIC';
    return RegExp(r'^\d+$').hasMatch(t) ? 'DOMESTIC' : 'OVERSEAS';
  }
}
