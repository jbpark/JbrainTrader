import sys
import os
import pandas as pd
import logging
from typing import Dict, List

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Add project root to sys.path to import core modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.database import DatabaseManager

STOCK_EXCEL_FILE = "stock.xlsx"

def load_tickers_from_excel(file_path: str) -> List[Dict]:
    """
    Load tickers with name and market info from Excel file.
    Expected columns: Ticker, Name (종목명), Market (코스닥/코스피)
    """
    if not os.path.exists(file_path):
        logging.error(f"File not found: {file_path}")
        return []

    try:
        # Read Excel file
        df = pd.read_excel(file_path, dtype=str)
        
        if df.empty:
            logging.warning("Excel file is empty")
            return []

        # Check for expected columns
        # Support both Korean and English column names
        ticker_col = None
        name_col = None
        market_col = None
        
        for col in df.columns:
            col_lower = col.lower().strip()
            if col_lower in ['ticker', '티커', '종목코드']:
                ticker_col = col
            elif col_lower in ['name', '종목명', '이름']:
                name_col = col
            elif col_lower in ['market', '시장', '시장구분', '코스닥/코스피']:
                market_col = col
        
        if ticker_col is None:
            logging.error("Ticker column not found in Excel file")
            return []
        
        # Build list of ticker dictionaries
        tickers_data = []
        for _, row in df.iterrows():
            ticker = str(row[ticker_col]).strip() if pd.notna(row[ticker_col]) else None
            if not ticker or len(ticker) < 1:
                continue
                
            name = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else None
            market = str(row[market_col]).strip() if market_col and pd.notna(row[market_col]) else None
            
            tickers_data.append({
                'ticker': ticker,
                'name': name,
                'market': market
            })
        
        logging.info(f"Loaded {len(tickers_data)} tickers from {file_path}")
        return tickers_data
        
    except Exception as e:
        logging.error(f"Failed to read Excel file: {str(e)}")
        return []

def sync_tickers():
    db = DatabaseManager()  # 접속 정보는 .env(DB_USER/DB_PASSWORD/DB_NAME)에서 로드
    
    # 1. Get current tickers from DB
    db_tickers_list = db.get_tickers()
    db_tickers_dict = {row['ticker']: row for row in db_tickers_list}
    db_tickers = set(db_tickers_dict.keys())
    logging.info(f"Current DB tickers: {len(db_tickers)}")
    
    # 2. Get tickers from Excel
    excel_tickers_list = load_tickers_from_excel(STOCK_EXCEL_FILE)
    
    if not excel_tickers_list and not os.path.exists(STOCK_EXCEL_FILE):
        logging.error(f"{STOCK_EXCEL_FILE} missing. Cannot sync. Please create the file.")
        return
    
    excel_tickers_dict = {item['ticker']: item for item in excel_tickers_list}
    excel_tickers = set(excel_tickers_dict.keys())
    
    # 3. Calculate differences
    to_add = excel_tickers - db_tickers
    to_remove = db_tickers - excel_tickers
    to_update = excel_tickers & db_tickers  # 기존에 있는 티커들도 업데이트
    
    logging.info(f"Tickers to add: {len(to_add)}")
    logging.info(f"Tickers to remove: {len(to_remove)}")
    logging.info(f"Tickers to update: {len(to_update)}")
    
    # 4. Apply changes
    # Additions
    for ticker in to_add:
        ticker_data = excel_tickers_dict[ticker]
        logging.info(f"Adding ticker: {ticker} ({ticker_data.get('name', 'N/A')}, {ticker_data.get('market', 'N/A')})")
        db.add_ticker(ticker, ticker_data.get('name'), ticker_data.get('market'))
    
    # Updates (기존 티커의 종목명, 시장구분 업데이트)
    for ticker in to_update:
        ticker_data = excel_tickers_dict[ticker]
        db_data = db_tickers_dict[ticker]
        
        # 변경사항이 있는 경우만 업데이트
        if (ticker_data.get('name') != db_data.get('name') or 
            ticker_data.get('market') != db_data.get('market')):
            logging.info(f"Updating ticker: {ticker} ({ticker_data.get('name', 'N/A')}, {ticker_data.get('market', 'N/A')})")
            db.add_ticker(ticker, ticker_data.get('name'), ticker_data.get('market'))
        
    # Removals
    for ticker in to_remove:
        logging.info(f"Removing ticker: {ticker}")
        db.remove_ticker(ticker)
        
    logging.info("Synchronization complete.")

if __name__ == "__main__":
    sync_tickers()
