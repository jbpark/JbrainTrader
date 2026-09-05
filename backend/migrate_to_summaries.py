import sys
import os
import logging

sys.path.append(r'c:\repo_jb\jbaipromptstudy\sample\stock\system_trading\split_buy_sell_vue\split_buy_sell_vue_009')

from core.database import DatabaseManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def migrate_summaries():
    db = DatabaseManager()
    conn = db.get_connection()
    
    try:
        with conn.cursor() as cur:
            intervals = ['1m', '5m', 'tick']
            for interval in intervals:
                table_name = db._get_ohlcv_table(interval)
                logging.info(f"Processing interval: {interval} (Table: {table_name})")
                
                # Get all ticker-date pairs
                cur.execute(f"SELECT DISTINCT ticker, DATE(datetime) as date_val FROM {table_name}")
                pairs = cur.fetchall()
                
                logging.info(f"Found {len(pairs)} ticker-date pairs for {interval}")
                
                for pair in pairs:
                    ticker = pair['ticker']
                    date_val = pair['date_val']
                    logging.info(f"Updating summary for {ticker} on {date_val} ({interval})")
                    db.update_ohlcv_summary(ticker, interval, date_val)
                    
        logging.info("Migration to summaries completed successfully.")
        
    except Exception as e:
        logging.error(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_summaries()
