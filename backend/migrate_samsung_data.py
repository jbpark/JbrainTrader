import sys
import os

sys.path.append(r'c:\repo_jb\jbaipromptstudy\sample\stock\system_trading\split_buy_sell_vue\split_buy_sell_vue_009')

from core.database import DatabaseManager

def migrate():
    db = DatabaseManager()
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            ticker = '005930.KS'
            date = '2026-02-04'
            
            # Check if 1m data exists
            cur.execute("SELECT COUNT(*) FROM ohlcv_data WHERE ticker=%s AND interval_type='1m' AND DATE(datetime)=%s", (ticker, date))
            count_1m = cur.fetchone()['COUNT(*)']
            print(f"Found {count_1m} rows with '1m' for {ticker} on {date}")
            
            if count_1m > 0:
                print("Migrating '1m' to 'tick'...")
                cur.execute("""
                    UPDATE ohlcv_data 
                    SET interval_type = 'tick' 
                    WHERE ticker = %s AND interval_type = '1m' AND DATE(datetime) = %s
                """, (ticker, date))
                conn.commit()
                print("Migration complete.")
            else:
                print("No '1m' data found to migrate. Maybe already migrated or doesn't exist.")

    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
