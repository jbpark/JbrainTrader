import 'package:flutter/material.dart';

class StatusBadge extends StatelessWidget {
  final String text;
  const StatusBadge({super.key, required this.text});

  Color _getColor() {
    switch (text.toUpperCase()) {
      case 'RUNNING':
      case 'ACTIVE':
      case '매수완료':
      case '매도완료':
        return const Color(0xFF00D084);
      case 'PAUSED':
      case '일시정지':
        return Colors.amber;
      case 'DISCONNECTED':
      case 'ERROR':
        return Colors.redAccent;
      case 'SIMULATING':
      case '시뮬레이션':
        return Colors.purpleAccent;
      case 'MONITORING':
      case '모니터링':
        return Colors.blueAccent;
      default:
        return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = _getColor();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        border: Border.all(color: color.withOpacity(0.5)),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }
}
