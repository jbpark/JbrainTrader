import sys
import os

sys.path.append(r'c:\repo_jb\jbaipromptstudy\sample\stock\system_trading\split_buy_sell_vue\split_buy_sell_vue_009')
from core.database import DatabaseManager

def migrate():
    db = DatabaseManager()
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            tables = ['ohlcv_1m', 'ohlcv_5m', 'ohlcv_1d', 'ohlcv_tick']
            for table in tables:
                try:
                    cur.execute(f"SHOW COLUMNS FROM {table} LIKE 'scenario'")
                    if not cur.fetchone():
                        print(f"Adding scenario to {table}")
                        cur.execute(f"ALTER TABLE {table} ADD COLUMN scenario VARCHAR(50) DEFAULT 'NONE'")
                except Exception as e:
                    print(f"Error checking/altering {table}: {e}")
            conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
