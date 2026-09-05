import sys
import os
import logging

sys.path.append(r'c:\repo_jb\jbaipromptstudy\sample\stock\system_trading\split_buy_sell_vue\split_buy_sell_vue_009')

from core.database import DatabaseManager

def verify_split():
    db = DatabaseManager()
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            tables = ['ohlcv_1m', 'ohlcv_5m', 'ohlcv_1d']
            for table in tables:
                cur.execute(f"SELECT COUNT(*) as count FROM {table}")
                count = cur.fetchone()['count']
                print(f"Table {table}: {count} records")
            
            # Check if ohlcv_data still exists
            try:
                cur.execute("SELECT COUNT(*) FROM ohlcv_data")
                print("ohlcv_data STILL EXISTS!")
            except:
                print("ohlcv_data table deleted successfully.")
    finally:
        conn.close()

if __name__ == "__main__":
    verify_split()
