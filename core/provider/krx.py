from pykrx import stock
import pandas as pd
import logging
import threading
import time
from datetime import datetime, timedelta

# pykrx의 내부 로깅 버그(TypeError: not all arguments converted during string formatting)를 
# 원천 차단하기 위해 pykrx 내부 wrapper가 사용하는 로깅 객체를 가짜(Mock)로 교체합니다.
try:
    import pykrx.website.comm.util as pykrx_util
    class ZeroLogger:
        def info(self, *args, **kwargs): pass
        def error(self, *args, **kwargs): pass
        def warning(self, *args, **kwargs): pass
        def debug(self, *args, **kwargs): pass
    pykrx_util.logging = ZeroLogger()
except:
    pass

# 기존 방식대로 로거 레벨도 상향 조정
logging.getLogger("pykrx").setLevel(logging.CRITICAL)

class KrxProvider:
    def __init__(self):
        self.name = "KRX (pykrx)"
        self._cache = None
        self._last_update = None
        self._lock = threading.Lock()
        self._fail_count = 0
        self._last_fail_time = None
        self._is_disabled = False # 심각한 장애 시 전체 중단용
        self._cache_file = "tickers_krx_cache.json"
        self._load_cache()

    def _load_cache(self):
        """파일에서 캐시 로드"""
        try:
            import os, json
            if os.path.exists(self._cache_file):
                with open(self._cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._cache = pd.DataFrame(data)
                    self._last_update = datetime.fromtimestamp(os.path.getmtime(self._cache_file))
                    logging.info(f"[{self.name}] Loaded {len(self._cache)} tickers from persistent cache.")
        except Exception as e:
            logging.warning(f"[{self.name}] Failed to load persistent cache: {e}")

    def _save_cache(self):
        """파일에 캐시 저장"""
        try:
            if self._cache is not None and not self._cache.empty:
                self._cache.to_json(self._cache_file, orient='records', force_ascii=False)
        except Exception as e:
            logging.warning(f"[{self.name}] Failed to save persistent cache: {e}")

    def _update_cache_if_needed(self):
        """종목 리스트 캐시 업데이트 (하루 한 번)"""
        if self._is_disabled: return

        now = datetime.now()
        
        # 이미 데이터가 있고 오늘 업데이트했으면 건너뜀
        if self._cache is not None and not self._cache.empty and self._last_update:
            if self._last_update.date() == now.date():
                return
        
        # 연속 실패 시 재시도 억제 (1시간 간격으로 상향)
        if self._last_fail_time and now - self._last_fail_time < timedelta(hours=1):
            return

        with self._lock:
            if self._cache is not None and self._last_update is not None:
                if now - self._last_update < timedelta(hours=12):
                    return

            try:
                logging.info(f"[{self.name}] Updating ticker cache...")
                start_time = time.time()
                
                # 최근 영업일 확보
                target_date = self._get_last_trading_date()
                if not target_date:
                    logging.warning(f"[{self.name}] No valid trading date found for cache update.")
                    if self._cache is None:
                        self._cache = pd.DataFrame(columns=["ticker", "name", "market", "type"])
                    return

                logging.info(f"[{self.name}] Using target date: {target_date}")
                
                stocks_list = []

                # 시장별로 가격 변동 정보를 가져와서 종목명-티커 매핑 생성 (bulk fetching)
                for mkt in ["KOSPI", "KOSDAQ"]:
                    try:
                        # get_market_price_change_by_ticker가 에러를 낼 경우를 대비하여 중첩 예외 처리
                        mkt_df = stock.get_market_price_change_by_ticker(target_date, target_date, market=mkt)
                        
                        if mkt_df is not None and not mkt_df.empty and '종목명' in mkt_df.columns:
                            suffix = ".KS" if mkt == "KOSPI" else ".KQ"
                            for code, row in mkt_df.iterrows():
                                stocks_list.append({
                                    "ticker": f"{code}{suffix}",
                                    "name": row['종목명'],
                                    "market": mkt,
                                    "type": "EQUITY"
                                })
                            logging.info(f"[{self.name}] Fetched {len(mkt_df)} {mkt} tickers via price change")
                        else:
                            # 차선책: 티커 리스트를 가져온 후 개별 이름 매핑 (속도는 느리지만 확실함)
                            try:
                                tickers = stock.get_market_ticker_list(target_date, market=mkt)
                                if tickers:
                                    logging.info(f"[{self.name}] Low-level ticker list fallback for {mkt} ({len(tickers)} items)")
                                    suffix = ".KS" if mkt == "KOSPI" else ".KQ"
                                    for code in tickers:
                                        stocks_list.append({
                                            "ticker": f"{code}{suffix}",
                                            "name": code,
                                            "market": mkt,
                                            "type": "EQUITY"
                                        })
                            except: pass
                                
                    except IndexError:
                        # pykrx 내부 인덱스 에러 (데이터가 아예 없는 경우 등) 시 로그만 남김
                        logging.warning(f"[{self.name}] No data available for {mkt} on {target_date} (IndexError)")
                    except Exception as inner_e:
                        logging.error(f"[{self.name}] Error fetching {mkt} tickers: {inner_e}")
                
                # [안전 조치] ETF 가져오기 일시 중단 (최근 pykrx/KRX 연동 오류 집중 발생 구간)
                # 꼭 필요할 경우 Yahoo 검색 결과를 활용하도록 종속성 분리됨
                """
                try:
                    etf_codes = stock.get_etf_ticker_list(target_date)
                    if etf_codes:
                        for code in etf_codes:
                            stocks_list.append({
                                "ticker": f"{code}.KS",
                                "name": code,
                                "market": "ETF",
                                "type": "ETF"
                            })
                except Exception as e:
                    logging.warning(f"[{self.name}] Failed to fetch ETFs: {e}")
                """

                if stocks_list:
                    self._cache = pd.DataFrame(stocks_list)
                    self._last_update = now
                    self._fail_count = 0
                    self._last_fail_time = None
                    self._save_cache()
                    logging.info(f"[{self.name}] Cache updated: {len(self._cache)} items ({time.time() - start_time:.2f}s)")
                elif self._cache is None:
                    # 데이터가 아예 없는 경우 빈 프레임이라도 유지하여 반복 방동 방지
                    self._cache = pd.DataFrame(columns=["ticker", "name", "market", "type"])
                    self._last_fail_time = now
            except Exception as e:
                self._fail_count += 1
                self._last_fail_time = now
                if self._fail_count > 5:
                    self._is_disabled = True
                    logging.error(f"[{self.name}] Too many failures ({self._fail_count}). Provider DISABLED.")
                else:
                    logging.error(f"[{self.name}] Critical error in update_cache: {e}")
                
                if self._cache is None:
                    self._cache = pd.DataFrame(columns=["ticker", "name", "market", "type"])

    def _get_last_trading_date(self):
        """최근 영업일 구하기 (데이터가 실제로 존재하는 날짜 확인)"""
        dt = datetime.now()
        # 오늘이 일요일(6)이면 금요일(어저께 그저께)부터 확인하도록 안전하게 1부터 시작
        for i in range(1, 10):
            target = (dt - timedelta(days=i)).strftime("%Y%m%d")
            try:
                # 특정 시장의 티커 리스트가 비어있지 않은지 확인
                tickers = stock.get_market_ticker_list(target, market="KOSPI")
                if tickers and len(tickers) > 100:
                    # 보수적으로 OHLCV 데이터도 한 종목 찔러서 데이터가 오는지 확인 (주말/휴일 필터링)
                    # 삼성전자(005930) 테스트
                    df = stock.get_market_ohlcv_by_date(target, target, "005930")
                    if not df.empty and df.iloc[0]['종가'] > 0:
                        return target
            except (IndexError, TypeError):
                # pykrx 내부 에러 발생 시 해당 날짜 건너뜀
                continue
            except Exception as e:
                logging.debug(f"[{self.name}] Error checking date {target}: {e}")
                continue
        return None

    def search_ticker(self, query: str):
        self._update_cache_if_needed()
        
        query = query.strip()
        if not query:
            return []

        if self._cache is None or self._cache.empty:
            return []

        # 검색 로직
        query_upper = query.upper()
        
        # 1. 종목명 부분 일치 검색
        matched_name = self._cache[self._cache['name'].str.contains(query, case=False, na=False)]
        
        # 2. 티커(코드) 일치 검색 (숫자 6자리인 경우 접미사 없이 검색 지원)
        if query.isdigit() and len(query) == 6:
            matched_ticker = self._cache[self._cache['ticker'].str.startswith(query)]
        else:
            matched_ticker = self._cache[self._cache['ticker'].str.contains(query_upper, case=False, na=False)]
            
        # 결과 합치기 및 중복 제거
        results_df = pd.concat([matched_name, matched_ticker]).drop_duplicates(subset=['ticker'])
        
        # 정렬: 정확히 일치하는 종목 우선
        def sort_priority(row):
            # 정확히 이름 일치
            if row['name'] == query: return 0
            # 티커가 쿼리로 시작
            if row['ticker'].startswith(query_upper): return 1
            # 이름이 쿼리로 시작
            if row['name'].startswith(query): return 2
            return 3

        if not results_df.empty:
            results_df['priority'] = results_df.apply(sort_priority, axis=1)
            results_df['name_len'] = results_df['name'].str.len()
            results_df = results_df.sort_values(by=['priority', 'name_len', 'name'])
            
            # API 규격에 맞춰 리스트 반환
            return results_df.drop(columns=['priority', 'name_len']).head(50).to_dict('records')
        
        return []
