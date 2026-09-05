import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:trading_app/providers/trading_provider.dart';
import 'package:trading_app/screens/dashboard_screen.dart';

/// 보유 종목 표의 레이아웃 회귀 방지.
///
/// DataTable은 정렬 가능한 컬럼에 화살표를 덧붙이므로, 헤더에 여유 폭이 없으면
/// "RIGHT OVERFLOWED BY n PIXELS" 오버플로가 난다 (Flutter 웹에서 특히 잘 드러남).
List<Map<String, dynamic>> _holdings() => [
      {
        'ticker': '000660', 'name': 'SK하이닉스', 'qty': 1,
        'buy_price': 1689000.0, 'current_price': 1645000.0,
        'profit': -47779, 'ratio': -2.83,
      },
      {
        'ticker': '004090', 'name': '한국석유', 'qty': 291,
        'buy_price': 14622.0, 'current_price': 10930.0,
        'profit': -1081920, 'ratio': -25.43,
      },
      {
        'ticker': '272210', 'name': '한화시스템', 'qty': 285,
        'buy_price': 79925.0, 'current_price': 80300.0,
        'profit': 54154, 'ratio': 0.24,
      },
    ];

Widget _wrap(List<Map<String, dynamic>> holdings) => MaterialApp(
      home: ChangeNotifierProvider<TradingProvider>(
        create: (_) => TradingProvider(),
        child: Scaffold(
          body: SingleChildScrollView(
            child: HoldingsSection(holdings: holdings),
          ),
        ),
      ),
    );

void main() {
  testWidgets('보유 종목 표가 오버플로 없이 그려진다', (tester) async {
    // 사용자가 오버플로를 본 폭과 비슷하게 맞춘다
    tester.view.physicalSize = const Size(835, 700);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(_wrap(_holdings()));
    await tester.pump();

    expect(tester.takeException(), isNull);
    expect(find.text('매입금액'), findsOneWidget);
    expect(find.text('SK하이닉스'), findsOneWidget);
  });

  testWidgets('좁은 폭에서도 오버플로가 없다', (tester) async {
    tester.view.physicalSize = const Size(360, 640);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(_wrap(_holdings()));
    await tester.pump();

    expect(tester.takeException(), isNull);
  });

  testWidgets('헤더를 누르면 정렬된다', (tester) async {
    tester.view.physicalSize = const Size(835, 700);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(_wrap(_holdings()));
    await tester.pump();

    // 첫 탭은 오름차순: SK하이닉스(1,689,000) < 한국석유(4,255,002) < 한화시스템(22,778,625)
    await tester.tap(find.text('매입금액'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);

    final state = tester.state<HoldingsSectionState>(find.byType(HoldingsSection));
    expect(state.sortedForTest.map((h) => h['name']).toList(),
        ['SK하이닉스', '한국석유', '한화시스템']);

    // 같은 헤더를 다시 누르면 내림차순
    await tester.tap(find.text('매입금액'));
    await tester.pumpAndSettle();
    expect(state.sortedForTest.map((h) => h['name']).toList(),
        ['한화시스템', '한국석유', 'SK하이닉스']);
  });

  testWidgets('보유 종목이 없으면 안내 문구를 보여준다', (tester) async {
    await tester.pumpWidget(_wrap([]));
    await tester.pump();

    expect(tester.takeException(), isNull);
    expect(find.text('보유 중인 종목이 없습니다'), findsOneWidget);
  });
}
