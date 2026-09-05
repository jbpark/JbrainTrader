import sys
import os

sys.path.append(r'c:\repo_jb\jbaipromptstudy\sample\stock\system_trading\split_buy_sell_vue\split_buy_sell_vue_009')
from core.database import DatabaseManager

db = DatabaseManager()

ticker = "005930"
interval = "5분"

print(f"Testing get_ohlcv_summaries for {ticker} / {interval}")
summaries = db.get_ohlcv_summaries(ticker, interval)
print(f"Result: {summaries}")
print(f"Length: {len(summaries)}")

if summaries:
    import json
    print("\nFirst item:")
    print(json.dumps(summaries[0], indent=2, ensure_ascii=False, default=str))
