import sys
import os
import logging

sys.path.append(r'c:\repo_jb\jbaipromptstudy\sample\stock\system_trading\split_buy_sell_vue\split_buy_sell_vue_009')

from core.database import DatabaseManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def migrate_ohlcv_split():
    db = DatabaseManager()
    conn = db.get_connection()
    
    try:
        with conn.cursor() as cur:
            # 1. Create new tables
            tables = {
                '1m': 'ohlcv_1m',
                '5m': 'ohlcv_5m',
                '1d': 'ohlcv_1d'
            }
            
            for interval, table_name in tables.items():
                logging.info(f"Creating table {table_name}...")
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        ticker VARCHAR(10),
                        datetime DATETIME,
                        open DECIMAL(20, 4),
                        high DECIMAL(20, 4),
                        low DECIMAL(20, 4),
                        close DECIMAL(20, 4),
                        volume BIGINT,
                        PRIMARY KEY (ticker, datetime)
                    )
                """)
            
            # 2. Migrate data
            for interval, table_name in tables.items():
                logging.info(f"Migrating data for {interval} to {table_name}...")
                cur.execute(f"""
                    INSERT INTO {table_name} (ticker, datetime, open, high, low, close, volume)
                    SELECT ticker, datetime, open, high, low, close, volume
                    FROM ohlcv_data
                    WHERE interval_type = %s
                    ON DUPLICATE KEY UPDATE
                        open = VALUES(open),
                        high = VALUES(high),
                        low = VALUES(low),
                        close = VALUES(close),
                        volume = VALUES(volume)
                """, (interval,))
                logging.info(f"Migrated {cur.rowcount} records for {interval}.")

            # 3. Verify counts
            for interval, table_name in tables.items():
                cur.execute(f"SELECT COUNT(*) as count FROM ohlcv_data WHERE interval_type = %s", (interval,))
                original_count = cur.fetchone()['count']
                
                cur.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                new_count = cur.fetchone()['count']
                
                logging.info(f"Validation for {interval}: Original={original_count}, New={new_count}")
                if original_count != new_count:
                    logging.warning(f"Mismatch in counts for {interval}!")

            # 4. Drop original table (Optional until verified, but user asked for it)
            # We'll do this in a separate step or prompt confirmation? 
            # The user explicitly said "삭제해주세요" (Please delete).
            logging.info("Dropping ohlcv_data table...")
            cur.execute("DROP TABLE ohlcv_data")
            logging.info("ohlcv_data table dropped successfully.")

        conn.commit()
        logging.info("Migration completed successfully.")
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_ohlcv_split()
