import sqlite3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import os

class TickPersistence:
    def __init__(self, db_path: str = "ticks.db"):
        self.db_path = db_path

    def save_to_db(self, df: pd.DataFrame, table_name: str = "ticks"):
        """Saves the dataframe to a SQLite database."""
        conn = sqlite3.connect(self.db_path)
        # Convert timestamp to string for sqlite compatibility if needed
        temp_df = df.copy()
        temp_df['ts'] = temp_df['ts'].astype(str)
        temp_df.to_sql(table_name, conn, if_exists='replace', index=False)
        conn.close()

    def load_from_db(self, table_name: str = "ticks") -> pd.DataFrame:
        """Loads data from a SQLite database."""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        df['ts'] = pd.to_datetime(df['ts'])
        conn.close()
        return df

    def export_to_parquet(self, df: pd.DataFrame, file_path: str):
        """Exports the dataframe to a Parquet file."""
        df.to_parquet(file_path, engine='pyarrow', index=False)

    def import_from_parquet(self, file_path: str) -> pd.DataFrame:
        """Imports data from a Parquet file."""
        return pd.read_parquet(file_path, engine='pyarrow')

    def export_to_csv(self, df: pd.DataFrame, file_path: str):
        """Exports the dataframe to a CSV file."""
        df.to_csv(file_path, index=False)

    def import_from_csv(self, file_path: str) -> pd.DataFrame:
        """Imports data from a CSV file."""
        df = pd.read_csv(file_path)
        df['ts'] = pd.to_datetime(df['ts'])
        return df
