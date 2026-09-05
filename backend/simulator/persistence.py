import pandas as pd
import sqlite3
import os

class TickPersistence:
    """
    틱 데이터의 파일 저장(Export/Import) 및 DB 연동을 담당합니다.
    """
    def __init__(self, db_path: str = "market_data.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """SQLite 테이블 초기화"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ohlcv_tick (
                ts INTEGER PRIMARY KEY,
                price REAL,
                volume INTEGER,
                scenario TEXT
            )
        ''')
        # 분석을 위한 인덱스 추가
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scenario ON ohlcv_tick(scenario)')
        conn.commit()
        conn.close()

    # --- File Export / Import ---
    
    def export_to_parquet(self, df: pd.DataFrame, file_path: str):
        """DataFrame을 Parquet 파일로 저장"""
        df.to_parquet(file_path, index=False)
        print(f"Exported to Parquet: {file_path}")

    def export_to_csv(self, df: pd.DataFrame, file_path: str):
        """DataFrame을 CSV 파일로 저장"""
        df.to_csv(file_path, index=False)
        print(f"Exported to CSV: {file_path}")

    def import_from_parquet(self, file_path: str) -> pd.DataFrame:
        """Parquet 파일에서 DataFrame 로드"""
        return pd.read_parquet(file_path)

    # --- DB Storage ---

    def save_to_db(self, df: pd.DataFrame):
        """DataFrame을 SQLite DB에 저장 (기존 데이터 교체)"""
        conn = sqlite3.connect(self.db_path)
        df.to_sql('ohlcv_tick', conn, if_exists='replace', index=False)
        conn.close()
        print(f"Saved {len(df)} rows to DB: {self.db_path}")

    def query_from_db(self, scenario: str = None, start_ts: int = None, end_ts: int = None) -> pd.DataFrame:
        """DB에서 조건부 조회"""
        conn = sqlite3.connect(self.db_path)
        query = "SELECT * FROM ohlcv_tick WHERE 1=1"
        params = []
        
        if scenario:
            query += " AND scenario = ?"
            params.append(scenario)
        if start_ts:
            query += " AND ts >= ?"
            params.append(start_ts)
        if end_ts:
            query += " AND ts <= ?"
            params.append(end_ts)
            
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
