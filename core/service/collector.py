import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from core.provider.yahoo import YahooProvider
from core.provider.krx import KrxProvider

class CollectionService:
    def __init__(self, db_manager):
        self.db = db_manager
        self.yahoo = YahooProvider()
        self.krx = KrxProvider()
        self.is_running = False
        self._stop_event = threading.Event()
        self.progress = {} # {ticker: status}
        self.logs = []


    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        msg = f"[{timestamp}] {message}"
        self.logs.append(msg)
        logging.info(msg)
        # 로그가 너무 많아지면 슬라이싱 (최근 1000개 유지)
        if len(self.logs) > 1000:
            self.logs = self.logs[-1000:]

    def stop(self):
        self._stop_event.set()
        self.is_running = False
        self.log("수집 중지 요청됨")

    def search_ticker(self, query: str, source="KRX"):
        """종목 검색 기능 수행"""
        import re
        results = []
        query = query.strip()
        
        # 1. 한국 종목(6자리 숫자)인 경우 KRX 우선
        is_kr_numeric = re.match(r'^\d{6}$', query)
        
        # KRX 검색 시도 (숫자 티커이거나 소스가 KRX인 경우)
        if is_kr_numeric or source == "KRX":
            try:
                krx_res = self.krx.search_ticker(query)
                if krx_res:
                    results.extend(krx_res)
            except Exception as e:
                logging.error(f"KRX search failed for {query}: {e}")

        # 2. Yahoo 검색 시도 (티커가 영문이거나, KRX 결과가 없거나, 소스가 Yahoo인 경우)
        # QQQ, AAPL 등은 Yahoo가 훨씬 정확함
        is_alpha_ticker = re.match(r'^[A-Z]{1,5}$', query.upper())
        
        if is_alpha_ticker or source == "Yahoo" or not results:
            try:
                yahoo_res = self.yahoo.search_ticker(query)
                if yahoo_res:
                    seen = {r['ticker'] for r in results}
                    for r in yahoo_res:
                        if r['ticker'] not in seen:
                            results.append(r)
                            seen.add(r['ticker'])
            except Exception as e:
                logging.error(f"Yahoo search failed for {query}: {e}")
                
        return results[:50]

    def get_ticker_name_map_safe(self):
        """네트워크 호출(pykrx) 없이 현재 캐시된 정보만 안전하게 반환"""
        mapping = {}
        try:
            if self.krx._cache is not None and not self.krx._cache.empty:
                for _, row in self.krx._cache.iterrows():
                    ticker = row['ticker']
                    name = row['name']
                    mapping[ticker] = name
                    normalized = self.db.normalize_ticker(ticker)
                    if normalized not in mapping:
                        mapping[normalized] = name
        except:
            pass
        return mapping

    def get_ticker_name_map(self):
        """현재 캐시된 모든 종목의 티커-이름 매핑 반환 (필요시 업데이트 유도)"""
        # 캐시가 없으면 업데이트 유도
        if self.krx._cache is None or self.krx._cache.empty:
            # API 스레드에서 직접 호출되는 경우 위험하므로 로깅만 남기고 빈 값 반환 가능성 염두
            try:
                # KRX 제공자가 이미 비활성화되었거나 실패 이력이 너무 많으면 로드 시도 안함
                self.krx.search_ticker("")
            except Exception as e:
                logging.warning(f"Failed to auto-update KRX cache: {e}")
            
        return self.get_ticker_name_map_safe()

    def run_collection(self, tickers, interval, start_date, end_date, source="Yahoo"):
        if self.is_running:
            self.log("이미 수집 작업이 진행 중입니다.")
            return
        
        self.is_running = True
        self._stop_event.clear()
        
        # 종목코드 정규화 (한국 종목 .KS 연동)
        normalized_tickers = [self.db.normalize_ticker(t) for t in tickers]
        self.progress = {t: "대기 중" for t in normalized_tickers}
        
        # 별도 스레드에서 원격 작업 실행
        thread = threading.Thread(
            target=self._execute_batch, 
            args=(normalized_tickers, interval, start_date, end_date, source)
        )
        thread.start()

    def _execute_batch(self, tickers, interval, start_date, end_date, source):
        import yfinance as yf
        self.log(f"수집 시작: {len(tickers)}개 종목 ({source}, {interval}) [yfinance: {yf.__version__}]")
        
        # interval 변환 (UI -> API 규격 및 Storage 규격)
        storage_interval = self.db.map_interval(interval)
        if interval in ["Tick", "틱", "tick"]:
            api_interval = "1m"
        else:
            api_interval = storage_interval

        # 멀티스레드 실행 (max_workers로 API 제한 조절)
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self._collect_single, t, api_interval, storage_interval, start_date, end_date, source): t 
                for t in tickers
            }
            
            for future in futures:
                if self._stop_event.is_set():
                    break
                ticker = futures[future]
                try:
                    count = future.result()
                    self.progress[ticker] = f"완료 ({count}건)"
                    # API 부하 방지 및 안정성을 위해 종목 사이 1초 대기
                    if not self._stop_event.is_set():
                        time.sleep(1)
                except Exception as e:
                    self.progress[ticker] = f"오류: {str(e)}"
                    self.log(f"{ticker} 수집 실패: {str(e)}")

        self.is_running = False
        self.log("모든 배치 작업 종료")

    def _collect_single(self, ticker, api_interval, storage_interval, start, end, source, retry_count=3):
        """단일 종목 수집 및 DB 저장 로직 (필요시 재시도 포함)"""
        ticker = self.db.normalize_ticker(ticker)
        self.progress[ticker] = "진행 중..."
        
        for attempt in range(retry_count):
            if self._stop_event.is_set():
                return 0
                
            try:
                # 1. 데이터 가져오기
                df = None
                if source == "Yahoo":
                    # yfinance는 .KS 접미사가 필요하므로 변환
                    yf_ticker = self.db.to_yfinance_ticker(ticker)
                    df = self.yahoo.fetch_data(yf_ticker, api_interval, start, end)
                
                if df is not None and not df.empty:
                    # 2. DB 저장
                    if storage_interval == 'tick':
                        # 틱 데이터는 ohlcv_tick 테이블에 저장
                        # OHLCV 형식을 틱 형식으로 변환
                        import pandas as pd
                        
                        # datetime이 컬럼에 있는지 인덱스에 있는지 확인
                        if 'datetime' in [str(c).lower() for c in df.columns]:
                            dt_col = [c for c in df.columns if str(c).lower() == 'datetime'][0]
                            df['ts'] = df[dt_col]
                        else:
                            df['ts'] = df.index
                        
                        # close를 price로, scenario 추가
                        df['price'] = df['Close'] if 'Close' in df.columns else df['close']
                        df['volume'] = df['Volume'] if 'Volume' in df.columns else df['volume']
                        df['scenario'] = 'COLLECTED'
                        
                        # 필요한 컬럼만 선택
                        tick_df = df[['ts', 'price', 'volume', 'scenario']]
                        count = self.db.save_tick_data(ticker, tick_df)
                    else:
                        # 일반 OHLCV 데이터는 주기별 테이블 (ohlcv_1m, ohlcv_5m 등)에 저장
                        count = self.db.save_ohlcv_data(ticker, storage_interval, df)
                    
                    self.log(f"{ticker} 수집 성공: {count}건 저장됨")
                    return count
                else:
                    msg = "데이터가 비어 있습니다."
                    if api_interval in ['1m']:
                        msg += " (Yahoo 제한: 1분봉은 최근 7일 이내만 수집 가능합니다.)"
                    elif api_interval in ['2m', '5m', '15m', '30m', '60m', '1h']:
                        msg += " (Yahoo 제한: 분봉 데이터는 최근 60일 이내만 수집 가능합니다.)"
                    raise Exception(msg)
                    
            except Exception as e:
                wait_time = (attempt + 1) * 2
                self.log(f"{ticker} 수집 실패 ({attempt+1}/{retry_count}): {str(e)}")
                
                if attempt < retry_count - 1 and not self._stop_event.is_set():
                    self.log(f"{wait_time}초 후 재시도...")
                    time.sleep(wait_time)
                else:
                    raise e
        return 0
