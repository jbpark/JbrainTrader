import yfinance as yf
import pandas as pd
import logging
import re
import threading
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class YahooProvider:
    # yfinance.download는 멀티스레드 환경에서 데이터가 섞이는 이슈가 알려져 있어 Lock을 도입함
    _download_lock = threading.Lock()

    def __init__(self):
        self.name = "Yahoo Finance"
        # API 차단 방지를 위한 세션 설정
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        })
        # 재시도 전략 설정
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    def _yf_download(self, ticker, interval, start, end, use_session=True, period=None):
        """yfinance.download를 안전하게 호출하는 내부 메서드"""
        try:
            kwargs = {
                "tickers": ticker,
                "interval": interval,
                "progress": False,
                "auto_adjust": True,
                "threads": False
            }
            if period:
                kwargs["period"] = period
            else:
                kwargs["start"] = start
                kwargs["end"] = end
            
            if use_session:
                kwargs["session"] = self.session

            with self._download_lock:
                return yf.download(**kwargs)
        except Exception as e:
            logging.debug(f"[{self.name}] _yf_download error (session={use_session}): {e}")
            return None

    def fetch_data(self, ticker: str, interval: str, start: str, end: str) -> pd.DataFrame:
        """
        Yahoo Finance로부터 데이터 수집 (상세 로깅 및 강도 높은 재시도 포함)
        """
        try:
            start_dt = datetime.strptime(start, "%Y-%m-%d")
            end_dt = datetime.strptime(end, "%Y-%m-%d")
            real_end_dt = end_dt + pd.Timedelta(days=1)
            real_end = real_end_dt.strftime("%Y-%m-%d")
            
            # [자동 기간 조정] Yahoo API 제한에 맞춰 시작 날짜를 조정함
            now = datetime.now()
            adjusted_start_dt = start_dt
            
            limit_days = None
            if interval == '1m': limit_days = 7
            elif interval in ['2m', '5m', '15m', '30m', '90m']: limit_days = 60
            elif interval in ['1h', '60m']: limit_days = 730
            
            if limit_days:
                # 60일 제한의 경우 안전하게 58일 정도로 설정
                max_start_dt = (now - pd.Timedelta(days=limit_days - 2)).replace(hour=0, minute=0, second=0)
                if start_dt < max_start_dt:
                    adjusted_start_dt = max_start_dt
                    logging.info(f"[{self.name}] {ticker} ({interval}) 기간 조정: {start} -> {adjusted_start_dt.strftime('%Y-%m-%d')}")
            
            final_start = adjusted_start_dt.strftime("%Y-%m-%d")

            # 1. 안전하게 세션 없이 먼저 시도 (최근 Yahoo API 정책상 세션 헤더가 오히려 문제가 되는 경우가 많음)
            df = self._yf_download(ticker, interval, final_start, real_end, use_session=False)

            # 2. 실패 시 세션 포함하여 재시도
            if df is None or df.empty:
                logging.debug(f"[{self.name}] {ticker} ({interval}) 1차 시도(no-session) 실패. 세션 포함 재시도...")
                df = self._yf_download(ticker, interval, final_start, real_end, use_session=True)

            # 3. 그래도 실패하고 기간이 최근인 경우 period="60d"로 시도 (yfinance 버전에 따른 호환성)
            if (df is None or df.empty) and limit_days == 60:
                logging.info(f"[{self.name}] {ticker} ({interval}) start/end 실패. period='60d' 백업 시도...")
                df = self._yf_download(ticker, interval, None, None, use_session=False, period="60d")
                if df is not None and not df.empty:
                    # 요청한 기간만 필터링 (Pandas 인덱스 기반)
                    if df.index.tz is not None:
                        start_ts = pd.Timestamp(final_start).tz_localize(df.index.tz)
                        end_ts = pd.Timestamp(real_end).tz_localize(df.index.tz)
                    else:
                        start_ts = pd.Timestamp(final_start)
                        end_ts = pd.Timestamp(real_end)
                    df = df[(df.index >= start_ts) & (df.index < end_ts)]
                    logging.info(f"[{self.name}] period='60d' 데이터에서 {len(df)}건 추출 성공")

            if df is not None and not df.empty:
                logging.info(f"[{self.name}] Received {len(df)} rows for {ticker}. Columns: {df.columns.tolist()}")

                # --- 컬럼 정규화 로직 강화 ---
                # 1. MultiIndex 처리
                if isinstance(df.columns, pd.MultiIndex):
                    ticker_level = -1
                    for level in range(df.columns.nlevels):
                        if ticker in df.columns.get_level_values(level):
                            ticker_level = level
                            break
                    if ticker_level != -1:
                        df = df.xs(ticker, axis=1, level=ticker_level)
                    else:
                        df.columns = df.columns.get_level_values(0)

                # 2. 컬럼명 클렌징 (예: [('Close', 'AAPL')] -> 'Close' 또는 'AAPL Close' -> 'Close')
                new_cols = []
                for col in df.columns:
                    c_str = str(col)
                    # 티커명 제거 및 공백/특수문자 정리
                    # 단어 경계 기반 제거: 부분 문자열 치환은 한 글자 티커(C, V 등)가
                    # 컬럼명을 파괴함 ("Close".replace("C","") -> "lose")
                    clean_name = re.sub(rf'\b{re.escape(ticker)}\b', '', c_str)
                    clean_name = clean_name.replace("(", "").replace(")", "").replace("'", "").replace(",", "")
                    if "_" in clean_name: clean_name = clean_name.split("_")[-1]
                    clean_name = clean_name.strip()
                    
                    # 만약 티커명을 뺐더니 비어버리면 (드문 경우) 원래 이름 유지
                    if not clean_name: clean_name = c_str
                    new_cols.append(clean_name.lower())
                
                df.columns = new_cols

                # 중복 컬럼 제거 (필요시 첫번째 것 사용)
                df = df.loc[:, ~df.columns.duplicated()]
                
                # 필수 컬럼 존재 여부 확인
                required = ['open', 'high', 'low', 'close', 'volume']
                missing = [r for r in required if r not in df.columns]
                if missing:
                    logging.warning(f"[{self.name}] {ticker} 필수 컬럼 누락: {missing}. Available: {df.columns.tolist()}")
                    return None
                
                # [TIMEZONE FIX] 미국 주식은 현지 시간(미국 날짜), 한국 주식은 KST 변환
                is_us = not str(ticker).split('.')[0].isdigit()
                
                if df.index.tz is not None:
                    if is_us:
                        # 미국 주식은 현지 시간(America/New_York)으로 변환 후 타임존 정보 제거 (Wall-clock time)
                        # Yahoo가 1m 등 분봉 데이터는 UTC로 돌려주는 경우가 많으므로 명시적 변환 필요
                        df.index = df.index.tz_convert('America/New_York').tz_localize(None)
                    else:
                        # 한국 주식은 KST로 변환
                        df.index = df.index.tz_convert('Asia/Seoul').tz_localize(None)
                elif interval in ['1m', '2m', '5m', '15m', '30m', '60m', '1h']:
                    if not is_us:
                        # 타임존 정보가 없는데 분봉인 경우 한국 주식만 9시간 가산 (Yahoo가 UTC로 줄 때를 가정)
                        df.index = df.index + pd.Timedelta(hours=9)
                # 미국 주식인데 타임존 정보가 없는 경우는 이미 현지 시간으로 가정함 (yfinance 기본 동작)
                
                return df
            
            logging.warning(f"[{self.name}] {ticker} ({interval}) 최종 데이터 없음 ({final_start} ~ {real_end})")
            return None
            
        except Exception as e:
            logging.error(f"[{self.name}] Error fetching {ticker}: {str(e)}", exc_info=True)
            return None

    def search_ticker(self, query: str):
        """
        주요 종목 매핑 및 Yahoo Finance를 활용한 종목 검색
        """
        import urllib.parse
        import re

        query = query.strip()
        results = []

        # 1. 주요 한국 종목 매핑 (강력한 편의성 제공)
        kr_preset = {
            "삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "신한지주": "055550.KS",
            "LG에너지솔루션": "373220.KS", "삼성바이오로직스": "207940.KS", "현대차": "005380.KS",
            "기아": "000270.KS", "셀트리온": "068270.KS", "POSCO홀딩스": "005490.KS",
            "KB금융": "105560.KS", "네이버": "035420.KS", "NAVER": "035420.KS",
            "삼성SDI": "006400.KS", "LG화학": "051910.KS", "카카오": "035720.KS",
            "Kakao": "035720.KS", "현대모비스": "012330.KS", "포스코퓨처엠": "003670.KS",
            "에코프로비엠": "247540.KQ", "에코프로": "086520.KQ", "두산": "000150.KS",
            "두산에너빌리티": "034020.KS", "두산퓨얼셀": "336260.KS", "두산테스나": "131970.KQ",
            "한화": "000880.KS", "한화솔루션": "009830.KS", "한화에어로스페이스": "012450.KS",
            "한화시스템": "272210.KS", "HMM": "011200.KS", "대한항공": "003490.KS",
            "아시아나항공": "020560.KS", "한국전력": "015760.KS", "KT": "030200.KS",
            "LG": "003550.KS", "KODEX 200": "069500.KS", "KODEX 인버스": "114800.KS",
            "TIGER 차이나전기차SOLACTIVE": "371460.KS",
            "KODEX 삼성그룹": "069110.KS", "KODEX 레버리지": "122630.KS", "KODEX 200선물인버스2X": "252670.KS"
        }
        
        for name, ticker in kr_preset.items():
            if query in name or query.upper() in name.upper() or query.upper() == ticker.split('.')[0] or query.upper() == ticker.upper():
                if not any(r['ticker'] == ticker for r in results):
                    results.append({
                        "ticker": ticker,
                        "name": name,
                        "market": "KRX",
                        "type": "EQUITY"
                    })

        # 3. Yahoo Finance 검색 (기본)
        try:
            url = "https://query1.finance.yahoo.com/v1/finance/search"
            params = {
                'q': query,
                'quotesCount': 10,
                'lang': 'ko-KR',
                'region': 'KR'
            }
            # 세션을 사용하여 요청 (User-Agent 자동 포함 및 속도 향상)
            response = self.session.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                for quote in data.get('quotes', []):
                    quote_type = quote.get('quoteType', '')
                    if quote_type not in ['EQUITY', 'ETF', 'INDEX']: continue
                    
                    symbol = quote.get('symbol')
                    name = quote.get('longname') or quote.get('shortname') or symbol
                    market = quote.get('exchange')
                    
                    if not any(r['ticker'] == symbol for r in results):
                        results.append({
                            "ticker": symbol,
                            "name": name,
                            "market": market,
                            "type": quote_type
                        })
        except Exception as e:
            logging.error(f"[{self.name}] Search error for {query}: {str(e)}")
            
        results.sort(key=lambda x: (x['ticker'].upper() != query.upper(), x['name'].upper().find(query.upper()) if x['name'].upper().find(query.upper()) != -1 else 999, x['ticker']))
        return results
