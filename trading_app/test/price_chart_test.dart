import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:trading_app/screens/ai_trades_screen.dart';

/// 실제 AI 매매 전략 응답(파마리서치)과 동일한 값
const _strategy = {
  'current_price': 398000,
  'target_price': 440000,
  'stop_loss': 362000,
  'entry_price': '380,000 ~ 396,000',
};

/// 페인터를 실제로 그려서 픽셀을 읽어온다
Future<(Uint8List, int, int)> _renderPainter(
    Map<String, dynamic> data, double w, double h) async {
  final recorder = ui.PictureRecorder();
  final canvas = Canvas(recorder, Rect.fromLTWH(0, 0, w, h));
  PriceLevelPainter(data).paint(canvas, Size(w, h));
  final img = await recorder.endRecording().toImage(w.toInt(), h.toInt());
  final bytes = await img.toByteData(format: ui.ImageByteFormat.rawRgba);
  return (bytes!.buffer.asUint8List(), w.toInt(), h.toInt());
}

/// (x, y) 픽셀의 RGBA
(int, int, int, int) _px(Uint8List b, int w, int x, int y) {
  final i = (y * w + x) * 4;
  return (b[i], b[i + 1], b[i + 2], b[i + 3]);
}

/// 해당 색이 처음/마지막으로 나타나는 y (없으면 null). x 범위는 플롯 영역 안쪽.
(int?, int?) _rowsWithColor(
    Uint8List b, int w, int h, int r, int g, int bl, {int tol = 24}) {
  int? first, last;
  for (var y = 0; y < h; y++) {
    var hit = false;
    for (var x = 80; x < w - 100; x += 2) {
      final (pr, pg, pb, pa) = _px(b, w, x, y);
      if (pa > 200 &&
          (pr - r).abs() <= tol &&
          (pg - g).abs() <= tol &&
          (pb - bl).abs() <= tol) {
        hit = true;
        break;
      }
    }
    if (hit) {
      first ??= y;
      last = y;
    }
  }
  return (first, last);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('가격대 전략 그래프 계산', () {
    test('필수 가격이 모두 있으면 레벨을 계산한다', () {
      final d = buildChartLevels(Map<String, dynamic>.from(_strategy));
      expect(d, isNotNull);

      final levels = (d!['levels'] as List).cast<Map<String, dynamic>>();
      final byLabel = {for (final l in levels) l['label'] as String: l};

      expect(byLabel.keys, containsAll(['목표가', '진입 상단', '진입 하단', '현재가', '손절가']));
      expect(byLabel['목표가']!['price'], 440000);
      expect(byLabel['손절가']!['price'], 362000);
      expect(byLabel['진입 상단']!['price'], 396000);
      expect(byLabel['진입 하단']!['price'], 380000);

      // 현재가 대비 등락률
      expect(byLabel['목표가']!['diff'], '+10.6%');
      expect(byLabel['손절가']!['diff'], '-9.0%');
      expect(byLabel['진입 상단']!['diff'], '-0.5%');

      // 손익비 = (440000-388000) / (388000-362000) = 2.0
      expect((d['rr'] as double), closeTo(2.0, 0.01));

      // 축 범위가 모든 가격을 포함
      expect(d['min'] as double, lessThan(362000));
      expect(d['max'] as double, greaterThan(440000));
    });

    test('필수 가격이 없으면 null (그래프 버튼 미표시)', () {
      expect(buildChartLevels({'current_price': 1000}), isNull);
      expect(buildChartLevels({'current_price': 1000, 'target_price': 1200}), isNull);
    });

    test('진입가가 단일 값이어도 동작한다', () {
      final d = buildChartLevels({
        'current_price': 1000, 'target_price': 1200, 'stop_loss': 900,
        'entry_price': '980',
      });
      final labels =
          (d!['levels'] as List).map((l) => l['label']).toList();
      expect(labels.contains('진입 상단'), isTrue);
      expect(labels.contains('진입 하단'), isFalse); // 상·하단이 같으면 한 줄만
    });
  });

  group('그래프 실제 렌더링', () {
    test('목표가(초록)·현재가(흰)·손절가(빨강)가 가격 순서대로 그려진다', () async {
      final d = buildChartLevels(Map<String, dynamic>.from(_strategy))!;
      final (bytes, w, h) = await _renderPainter(d, 400, 240);

      // 목표가 초록 0xFF00D084
      final (greenY, _) = _rowsWithColor(bytes, w, h, 0x00, 0xD0, 0x84);
      // 손절가 빨강 (Colors.redAccent = 0xFFFF5252)
      final (redY, _) = _rowsWithColor(bytes, w, h, 0xFF, 0x52, 0x52);
      // 현재가 흰색
      final (whiteY, _) = _rowsWithColor(bytes, w, h, 0xFF, 0xFF, 0xFF, tol: 6);

      expect(greenY, isNotNull, reason: '목표가 선이 그려지지 않음');
      expect(redY, isNotNull, reason: '손절가 선이 그려지지 않음');
      expect(whiteY, isNotNull, reason: '현재가 선이 그려지지 않음');

      // 가격이 높을수록 위(y가 작아야 함): 목표가 < 현재가 < 손절가
      expect(greenY!, lessThan(whiteY!),
          reason: '목표가가 현재가보다 위에 있어야 함');
      expect(whiteY, lessThan(redY!), reason: '현재가가 손절가보다 위에 있어야 함');
    });

    test('진입 가격대 밴드가 현재가와 손절가 사이에 그려진다', () async {
      final d = buildChartLevels(Map<String, dynamic>.from(_strategy))!;
      final (bytes, w, h) = await _renderPainter(d, 400, 240);

      // 진입 밴드 색 0xFF00A8CC 계열
      final (bandTop, bandBottom) = _rowsWithColor(bytes, w, h, 0x00, 0xA8, 0xCC, tol: 60);
      expect(bandTop, isNotNull, reason: '진입 가격대 밴드가 그려지지 않음');
      expect(bandBottom! - bandTop!, greaterThan(5), reason: '밴드에 높이가 있어야 함');

      final (redY, _) = _rowsWithColor(bytes, w, h, 0xFF, 0x52, 0x52);
      expect(bandBottom, lessThan(redY!), reason: '진입 하단이 손절가보다 위여야 함');
    });

    test('캔버스가 비어 있지 않다 (실제로 무언가 그려짐)', () async {
      final d = buildChartLevels(Map<String, dynamic>.from(_strategy))!;
      final (bytes, w, h) = await _renderPainter(d, 400, 240);
      var painted = 0;
      for (var i = 3; i < bytes.length; i += 4) {
        if (bytes[i] > 0) painted++;
      }
      expect(painted, greaterThan(500), reason: '그려진 픽셀이 거의 없음');
    });
  });
}
