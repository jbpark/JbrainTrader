class AccountInfo {
  final String name;
  final String accNo;
  final int balance;
  final String assetType;
  final String market;
  final List<String> accList;
  final bool hasOverseas;
  final Map<String, String> accMarketPrefs; // 계좌별 시장 고정 설정

  AccountInfo({
    required this.name,
    required this.accNo,
    required this.balance,
    this.assetType = 'STOCK',
    this.market = 'DOMESTIC',
    this.accList = const [],
    this.hasOverseas = false,
    this.accMarketPrefs = const {},
  });

  factory AccountInfo.fromJson(Map<String, dynamic> json) {
    return AccountInfo(
      name: json['name'] ?? '사용자',
      accNo: json['acc_no'] ?? '-',
      balance: (json['balance'] ?? 0).toInt(),
      assetType: json['asset_type'] ?? 'STOCK',
      market: json['market'] ?? 'DOMESTIC',
      accList: (json['acc_list'] as List<dynamic>? ?? [])
          .map((e) => e.toString())
          .toList(),
      hasOverseas: json['has_overseas'] == true,
      accMarketPrefs: (json['acc_market_prefs'] as Map<String, dynamic>? ?? {})
          .map((k, v) => MapEntry(k, v.toString())),
    );
  }
}

class TickerInfo {
  final String ticker;
  final String name;
  final int price;
  final String status;
  final String buyRule;
  final int positionQty;
  final double avgPrice;
  final double realizedProfit;
  final bool paused;
  final bool simulating;

  TickerInfo({
    required this.ticker,
    required this.name,
    required this.price,
    required this.status,
    required this.buyRule,
    required this.positionQty,
    required this.avgPrice,
    required this.realizedProfit,
    required this.paused,
    required this.simulating,
  });

  factory TickerInfo.fromJson(String ticker, Map<String, dynamic> json) {
    return TickerInfo(
      ticker: ticker,
      name: json['name'] ?? ticker,
      price: (json['price'] ?? 0).toInt(),
      status: json['status'] ?? '-',
      buyRule: json['buy_rule'] ?? 'DEFAULT',
      positionQty: (json['position_qty'] ?? 0).toInt(),
      avgPrice: (json['avg_price'] ?? 0.0).toDouble(),
      realizedProfit: (json['realized_profit'] ?? 0.0).toDouble(),
      paused: json['paused'] ?? false,
      simulating: json['simulating'] ?? false,
    );
  }
}

class TickData {
  final int time;
  final double value;
  final int volume;
  final String? marker;
  final String? scenario;

  TickData({
    required this.time,
    required this.value,
    required this.volume,
    this.marker,
    this.scenario,
  });

  factory TickData.fromJson(Map<String, dynamic> json) {
    return TickData(
      time: (json['time'] ?? 0).toInt(),
      value: (json['value'] ?? 0.0).toDouble(),
      volume: (json['volume'] ?? 0).toInt(),
      marker: json['marker'],
      scenario: json['scenario'],
    );
  }
}
