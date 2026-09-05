import pymysql
import logging
import os
import pandas as pd
from datetime import datetime

# DB 접속 정보는 .env에서 로드 (소스 코드에 비밀번호 하드코딩 금지)
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv())
except ImportError:
    pass

class DatabaseManager:
    def __init__(self, host=None, port=None, user=None, password=None, dbname=None):
        self.conn_params = {
            "host": host or os.getenv("DB_HOST", "localhost"),
            "port": int(port or os.getenv("DB_PORT", "3306")),
            "user": user or os.getenv("DB_USER", "jbuser"),
            "password": password if password is not None else os.getenv("DB_PASSWORD", ""),
            "database": dbname or os.getenv("DB_NAME", "jbstock"),
            "connect_timeout": 3,  # 3초 후 타임아웃
            "charset": "utf8mb4",
            "cursorclass": pymysql.cursors.DictCursor
        }
        self.init_db()

    # 한국 종목(6자리 숫자)인 경우 .KS 접미사 자동 추가
    def normalize_ticker(self, ticker):
        """티커 포맷 정규화 (예: 005930.KS -> 005930)"""
        if not ticker: return ""
        # .KS, .KQ 등 접미사 제거
        if '.' in ticker:
            ticker = ticker.split('.')[0]
        return str(ticker).strip()

    def to_yfinance_ticker(self, ticker):
        """정규화된 티커를 yfinance 형식으로 변환 (예: 005930 -> 005930.KS)"""
        ticker = self.normalize_ticker(ticker)
        if not ticker: return ""
        # 한국 종목(6자리 숫자)인 경우 .KS 접미사 추가
        import re
        if re.match(r'^\d{6}$', ticker):
            return f"{ticker}.KS"
        return ticker

    def map_interval(self, ui_interval):
        """UI 인터벌 문자열을 DB 규격으로 변환"""
        # 틱/Tick 변환
        if ui_interval in ["틱", "Tick", "tick"]:
            return "tick"
        
        # 분봉 변환
        interval_map = {
            "1분": "1m",
            "5분": "5m",
            "15분": "15m",
            "30분": "30m",
            "60분": "60m",
            "일봉": "1d"
        }
        return interval_map.get(ui_interval, ui_interval)

    def get_connection(self):
        try:
            return pymysql.connect(**self.conn_params)
        except Exception as e:
            logging.error(f"DB connection failed: {str(e)}")
            raise

    def init_db(self):
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS tickers (
                            ticker VARCHAR(10) PRIMARY KEY,
                            name VARCHAR(100),
                            market VARCHAR(20),
                            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    # 기존 테이블에 컬럼이 없는 경우 추가
                    try:
                        cur.execute("ALTER TABLE tickers ADD COLUMN name VARCHAR(100)")
                        logging.info("Added 'name' column to tickers table")
                    except:
                        pass  # 이미 존재하는 경우 무시
                    
                    try:
                        cur.execute("ALTER TABLE tickers ADD COLUMN market VARCHAR(20)")
                        logging.info("Added 'market' column to tickers table")
                    except:
                        pass  # 이미 존재하는 경우 무시
                        
                    try:
                        cur.execute("ALTER TABLE tickers MODIFY COLUMN buy_rule VARCHAR(500) DEFAULT 'DEFAULT'")
                        logging.info("Extended 'buy_rule' column size to 500")
                    except Exception as e:
                        # If MODIFY fails (e.g. column doesn't exist yet), try ADD
                        try:
                            cur.execute("ALTER TABLE tickers ADD COLUMN buy_rule VARCHAR(500) DEFAULT 'DEFAULT'")
                            logging.info("Added 'buy_rule' column with size 500")
                        except:
                            pass 

                        
                    try:
                        cur.execute("ALTER TABLE tickers ADD COLUMN is_active TINYINT(1) DEFAULT 1")
                        logging.info("Added 'is_active' column to tickers table")
                    except:
                        pass
                        
                conn.commit()
                logging.info("Database initialized successfully")
                
                # OHLCV 테이블 초기화
                self.init_ohlcv_tables()
                
                # 가상 틱 데이터 테이블 초기화
                self.init_tick_tables()
                
                # 백테스트 결과 테이블 초기화
                self.init_backtest_tables()
                
                # 매매일지(체결 내역) 테이블 초기화
                self.init_trade_tables()
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Database initialization error: {str(e)}")

    def init_ohlcv_tables(self):
        """OHLCV 데이터를 저장할 테이블 생성 (주기별 분리)"""
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    # 1분, 5분, 일봉 테이블 각각 생성
                    tables = ['ohlcv_1m', 'ohlcv_5m', 'ohlcv_1d', 'ohlcv_tick']
                    for table_name in tables:
                        # ohlcv_tick은 microsecond 지원 (datetime(6))
                        dt_type = "DATETIME(6)" if table_name == 'ohlcv_tick' else "DATETIME"
                        cur.execute(f"""
                            CREATE TABLE IF NOT EXISTS {table_name} (
                                ticker VARCHAR(10),
                                datetime {dt_type},
                                open DECIMAL(20, 4),
                                high DECIMAL(20, 4),
                                low DECIMAL(20, 4),
                                close DECIMAL(20, 4),
                                volume BIGINT,
                                scenario VARCHAR(50) DEFAULT 'NONE',
                                PRIMARY KEY (ticker, datetime)
                            )
                        """)
                    
                    # 요약 테이블 생성
                    sum_tables = ['ohlcv_1m_sum', 'ohlcv_5m_sum', 'ohlcv_tick_sum']
                    for table_name in sum_tables:
                        time_type = "TIME(6)" if "tick" in table_name else "TIME"
                        count_col = "tick_count" if "tick" in table_name else "bar_count"
                        cur.execute(f"""
                            CREATE TABLE IF NOT EXISTS {table_name} (
                                ticker VARCHAR(10),
                                date DATE,
                                start_time {time_type},
                                end_time {time_type},
                                open DECIMAL(20, 4),
                                high DECIMAL(20, 4),
                                low DECIMAL(20, 4),
                                close DECIMAL(20, 4),
                                volume BIGINT,
                                {count_col} INT,
                                scenario VARCHAR(50),
                                timezone VARCHAR(20),
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                                PRIMARY KEY (ticker, date)
                            )
                        """)
                conn.commit()
                logging.info("OHLCV tables and Summaries initialized")
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"OHLCV table initialization error: {str(e)}")

    def _get_ohlcv_table(self, interval):
        """인터벌에 따른 테이블 이름 반환"""
        db_interval = self.map_interval(interval)
        if db_interval == '1m': return 'ohlcv_1m'
        if db_interval == '5m': return 'ohlcv_5m'
        if db_interval == '1d': return 'ohlcv_1d'
        if db_interval == 'tick': return 'ohlcv_tick'
        return 'ohlcv_1d'

    def _get_summary_table(self, interval):
        """인터벌에 따른 요약 테이블 이름 반환"""
        db_interval = self.map_interval(interval)
        if db_interval == '1m': return 'ohlcv_1m_sum'
        if db_interval == '5m': return 'ohlcv_5m_sum'
        if db_interval == 'tick': return 'ohlcv_tick_sum'
        return None

    def update_ohlcv_summary(self, ticker, interval, date_val):
        """특정 날짜의 데이터를 집계하여 요약 테이블(sum) 업데이트"""
        sum_table = self._get_summary_table(interval)
        if not sum_table:
            return False
            
        raw_table = self._get_ohlcv_table(interval)
        ticker = self.normalize_ticker(ticker)
        
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    # 1. 데이터 집계 (OHLCV, 시간, 건수)
                    count_col = "tick_count" if "tick" in sum_table else "bar_count"
                    
                    # 틱 데이터의 경우 필드명 및 scenario 처리
                    scenario_str = ""
                    if "tick" in sum_table:
                        # 틱 테이블에 scenario 컬럼이 있는지 확인 (현재 ohlcv_tick엔 scenario가 없음 - ohlcv 구조로 변경됨)
                        # 이전 요구사항에서 ohlcv_tick_sum엔 scenario가 있었으므로 기본값 처리
                        scenario_str = 'COLLECTED'

                    sql_agg = f"""
                        SELECT 
                            MIN(TIME(datetime)) as start_time,
                            MAX(TIME(datetime)) as end_time,
                            MIN(low) as low,
                            MAX(high) as high,
                            SUM(volume) as total_volume,
                            COUNT(*) as total_count
                        FROM {raw_table}
                        WHERE ticker = %s AND DATE(datetime) = %s
                    """
                    cur.execute(sql_agg, (ticker, date_val))
                    agg = cur.fetchone()
                    
                    if not agg or agg['total_count'] == 0:
                        # 데이터가 하나도 없으면 요약 테이블에서도 삭제
                        cur.execute(f"DELETE FROM {sum_table} WHERE ticker = %s AND date = %s", (ticker, date_val))
                        conn.commit()
                        return True
                    
                    # Open/Close는 별도 쿼리로 (최초/최후 시점 봉)
                    cur.execute(f"SELECT open FROM {raw_table} WHERE ticker=%s AND DATE(datetime)=%s ORDER BY datetime ASC LIMIT 1", (ticker, date_val))
                    res_open = cur.fetchone()
                    open_val = res_open['open'] if res_open else 0
                    
                    cur.execute(f"SELECT close FROM {raw_table} WHERE ticker=%s AND DATE(datetime)=%s ORDER BY datetime DESC LIMIT 1", (ticker, date_val))
                    res_close = cur.fetchone()
                    close_val = res_close['close'] if res_close else 0
                    
                    # Timezone 결정
                    is_us = not str(ticker).split('.')[0].isdigit()
                    timezone = "America/New_York" if is_us else "Asia/Seoul"

                    # 2. 요약 테이블 INSERT/UPDATE
                    sql_upsert = f"""
                        INSERT INTO {sum_table} 
                        (ticker, date, start_time, end_time, open, high, low, close, volume, {count_col}, scenario, timezone)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            start_time = VALUES(start_time),
                            end_time = VALUES(end_time),
                            open = VALUES(open),
                            high = VALUES(high),
                            low = VALUES(low),
                            close = VALUES(close),
                            volume = VALUES(volume),
                            {count_col} = VALUES({count_col}),
                            scenario = VALUES(scenario),
                            timezone = VALUES(timezone)
                    """
                    cur.execute(sql_upsert, (
                        ticker, date_val, 
                        str(agg['start_time']), str(agg['end_time']),
                        float(open_val), float(agg['high']), float(agg['low']), float(close_val), 
                        int(agg['total_volume']), int(agg['total_count']), scenario_str, timezone
                    ))
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error updating summary for {ticker} ({interval}, {date_val}): {str(e)}")
            return False

    def init_tick_tables(self):
        """삭제됨 - init_ohlcv_tables에서 통합됨"""
        pass

    def save_tick_data(self, ticker, ticks_df):
        """틱 데이터 벌크 저장"""
        ticker = self.normalize_ticker(ticker)
        if ticks_df is None or ticks_df.empty:
            return 0
        
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    data_list = []
                    for _, row in ticks_df.iterrows():
                        dt = row['ts']
                        data_list.append((
                            ticker, dt,
                            float(row['price']),
                            int(row['volume']),
                            row.get('scenario', 'NONE')
                        ))
                    
                    sql = """
                        INSERT INTO ohlcv_tick (ticker, datetime, close, volume, open, high, low, scenario)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            close = VALUES(close), 
                            volume = VALUES(volume),
                            open = VALUES(open),
                            high = VALUES(high),
                            low = VALUES(low),
                            scenario = VALUES(scenario)
                    """
                    # 틱 데이터의 경우 ohlcv 구조를 따르도록 필드 맞춤 (price -> close)
                    # 데이터 매핑: (ticker, dt, price, volume, price, price, price, scenario)
                    formatted_list = [(d[0], d[1], d[2], d[3], d[2], d[2], d[2], d[4]) for d in data_list]
                    cur.executemany(sql, formatted_list)
                conn.commit()
                
                # 요약 테이블 업데이트
                dates = set([d[1].date() if hasattr(d[1], 'date') else str(d[1])[:10] for d in data_list])
                for date_val in dates:
                    self.update_ohlcv_summary(ticker, 'tick', date_val)
                    
                return len(data_list)
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error saving tick data for {ticker}: {str(e)}")
            return 0

    def get_tick_data(self, ticker, date_str=None, limit=5000):
        """특정 날짜의 틱 데이터 조회"""
        ticker = self.normalize_ticker(ticker)
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    if date_str:
                        sql = """
                            SELECT datetime, close as price, volume, scenario 
                            FROM ohlcv_tick 
                            WHERE ticker = %s AND DATE(datetime) = %s 
                            ORDER BY datetime ASC
                        """
                        cur.execute(sql, (ticker, date_str))
                    else:
                        sql = """
                            SELECT datetime, close as price, volume, scenario 
                            FROM ohlcv_tick 
                            WHERE ticker = %s 
                            ORDER BY datetime DESC LIMIT %s
                        """
                        cur.execute(sql, (ticker, limit))
                    
                    return cur.fetchall()
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error fetching tick data for {ticker}: {str(e)}")
            return []

    def save_ohlcv_data(self, ticker, interval, df):
        """OHLCV 데이터를 DB에 벌크 저장 (pandas DataFrame 기준)"""
        ticker = self.normalize_ticker(ticker)
        if df is None or df.empty:
            return 0
        
        try:
            # 컬럼 대소문자 무관하게 매핑 (Open -> open 등)
            col_map = {str(c).lower(): c for c in df.columns}
            
            expected = ['open', 'high', 'low', 'close', 'volume']
            missing = [c for c in expected if c not in col_map]
            if missing:
                logging.error(f"Error saving ohlcv data for {ticker}: Missing columns {missing}")
                return 0

            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    data_list = []
                    
                    # Check if datetime is in columns or index
                    has_datetime_col = 'datetime' in [str(c).lower() for c in df.columns]
                    
                    has_scenario_col = 'scenario' in [str(c).lower() for c in df.columns]
                    
                    table_name = self._get_ohlcv_table(interval)
                    for idx, row in df.iterrows():
                        # Extract datetime from column if available, otherwise from index
                        if has_datetime_col:
                            dt_col = [c for c in df.columns if str(c).lower() == 'datetime'][0]
                            dt = row[dt_col]
                            if hasattr(dt, 'to_pydatetime'):
                                dt = dt.to_pydatetime()
                        else:
                            dt = idx.to_pydatetime() if hasattr(idx, 'to_pydatetime') else idx
                        
                        scenario = 'NONE'
                        if has_scenario_col:
                            scenario_col = [c for c in df.columns if str(c).lower() == 'scenario'][0]
                            scenario = row[scenario_col]

                        data_list.append((
                            ticker, dt,
                            row[col_map['open']], 
                            row[col_map['high']], 
                            row[col_map['low']], 
                            row[col_map['close']], 
                            row[col_map['volume']],
                            scenario
                        ))
                    
                    # Debug logging
                    if len(data_list) > 0:
                        logging.info(f"Saving {len(data_list)} rows for {ticker}, table={table_name}, first_dt={data_list[0][1]}")
                    
                    sql = f"""
                        INSERT INTO {table_name} (ticker, datetime, open, high, low, close, volume, scenario)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            open = VALUES(open), high = VALUES(high), low = VALUES(low), 
                            close = VALUES(close), volume = VALUES(volume), scenario = VALUES(scenario)
                    """
                    cur.executemany(sql, data_list)
                conn.commit()

                # 요약 테이블 업데이트 (주기별 요약 테이블이 있는 경우만)
                if self._get_summary_table(interval):
                    dates = set([d[1].date() if hasattr(d[1], 'date') else str(d[1])[:10] for d in data_list])
                    for date_val in dates:
                        self.update_ohlcv_summary(ticker, interval, date_val)

                return len(data_list)
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error saving ohlcv data for {ticker}: {str(e)}")
            return 0

    def delete_ohlcv_data(self, ticker, interval, start_date=None, end_date=None):
        """OHLCV 데이터 삭제"""
        ticker = self.normalize_ticker(ticker)
        db_interval = self.map_interval(interval)
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    table_name = self._get_ohlcv_table(interval)
                    sql = f"DELETE FROM {table_name} WHERE ticker = %s"
                    params = [ticker]
                    if start_date and end_date and start_date == end_date:
                        # 단일 날짜 삭제 시
                        sql += " AND DATE(datetime) = %s"
                        params.append(start_date)
                    else:
                        if start_date:
                            sql += " AND datetime >= %s"
                            params.append(start_date)
                        if end_date:
                            # 해당 날짜의 끝까지 포함하도록 23:59:59 형태나 DATE() 사용이 좋음
                            # 여기서는 날짜만 들어올 경우를 대비해 DATE()로 처리
                            sql += " AND DATE(datetime) <= %s"
                            params.append(end_date)
                    cur.execute(sql, tuple(params))
                    
                    # 요약 테이블에서도 삭제
                    sum_table = self._get_summary_table(interval)
                    if sum_table:
                        sum_sql = f"DELETE FROM {sum_table} WHERE ticker = %s"
                        sum_params = [ticker]
                        if start_date and end_date and start_date == end_date:
                            sum_sql += " AND date = %s"
                            sum_params.append(start_date)
                        else:
                            if start_date:
                                sum_sql += " AND date >= %s"
                                sum_params.append(start_date)
                            if end_date:
                                sum_sql += " AND date <= %s"
                                sum_params.append(end_date)
                        cur.execute(sum_sql, tuple(sum_params))
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error deleting ohlcv data for {ticker}: {str(e)}")
            return False

    def get_collected_dates(self, ticker, interval, start_date, end_date):
        """특정 기간 동안 데이터가 수집된 날짜 목록 조회"""
        ticker = self.normalize_ticker(ticker)
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    sum_table = self._get_summary_table(interval)
                    if sum_table:
                        # 요약 테이블이 있으면 요약 테이블에서 고속 조회
                        sql = f"""
                            SELECT date as collected_date
                            FROM {sum_table}
                            WHERE ticker = %s
                            AND date >= %s AND date <= %s
                            ORDER BY date DESC
                        """
                        cur.execute(sql, (ticker, start_date, end_date))
                    else:
                        # 요약 테이블 없는 경우 (일봉 등) 원본에서 조회
                        table_name = self._get_ohlcv_table(interval)
                        sql = f"""
                            SELECT DISTINCT DATE(datetime) as collected_date
                            FROM {table_name}
                            WHERE ticker = %s
                            AND datetime >= %s AND DATE(datetime) <= %s
                            ORDER BY collected_date DESC
                        """
                        cur.execute(sql, (ticker, start_date, end_date))
                    
                    rows = cur.fetchall()
                    return [str(r['collected_date']) for r in rows]
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error fetching collected dates for {ticker}: {str(e)}")
            return []

    def get_ohlcv_summaries(self, ticker, interval, limit=100):
        """특정 종목의 일별 요약 정보 목록 조회 (start_time, end_time 포함)"""
        ticker = self.normalize_ticker(ticker)
        sum_table = self._get_summary_table(interval)
        
        if not sum_table:
            # 요약 테이블 없으면 빈 리스트 (일봉 등은 추후 지원 가능)
            return []
            
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    sql = f"""
                        SELECT *, DATE_FORMAT(date, '%%Y-%%m-%%d') as date_str
                        FROM {sum_table}
                        WHERE ticker = %s
                        ORDER BY date DESC LIMIT %s
                    """
                    cur.execute(sql, (ticker, limit))
                    rows = cur.fetchall()
                    
                    # JSON 직렬화 지원을 위한 타입 변환 (timedelta, datetime, Decimal 등)
                    import decimal
                    from datetime import timedelta, datetime, date
                    
                    for r in rows:
                        for key, value in r.items():
                            if isinstance(value, (timedelta, datetime, date, decimal.Decimal)):
                                if key == 'date' and 'date_str' in r:
                                    r[key] = r['date_str']
                                else:
                                    r[key] = str(value)
                    return rows
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error fetching summaries for {ticker}: {str(e)}")
            return []

    def get_tick_generated_dates(self, ticker, start_date, end_date):
        """특정 기간 동안 가상 틱 데이터가 생성된 날짜 목록 조회"""
        ticker = self.normalize_ticker(ticker)
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    sql = """
                        SELECT DISTINCT DATE(datetime) as gen_date
                        FROM ohlcv_tick
                        WHERE ticker = %s
                        AND datetime >= %s AND DATE(datetime) <= %s
                    """
                    cur.execute(sql, (ticker, start_date, end_date))
                    rows = cur.fetchall()
                    return [str(r['gen_date']) for r in rows]
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error fetching generated tick dates for {ticker}: {str(e)}")
            return []

    def get_collected_dates_with_tickers(self, interval, start_date, end_date):
        """전체 종목에 대해 수집 완료된 날짜와 종목 목록 조회"""
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    sum_table = self._get_summary_table(interval)
                    if sum_table:
                        sql = f"""
                            SELECT date as collected_date, ticker
                            FROM {sum_table}
                            WHERE date >= %s AND date <= %s
                        """
                    else:
                        table_name = self._get_ohlcv_table(interval)
                        sql = f"""
                            SELECT DISTINCT DATE(datetime) as collected_date, ticker
                            FROM {table_name}
                            WHERE datetime >= %s AND DATE(datetime) <= %s
                        """
                    cur.execute(sql, (start_date, end_date))
                    rows = cur.fetchall()
                    
                    res = {}
                    for r in rows:
                        dt_str = str(r['collected_date'])
                        if dt_str not in res: res[dt_str] = []
                        res[dt_str].append(r['ticker'])
                    return res
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error fetching collected dates for ALL: {str(e)}")
            return {}

    def get_tick_generated_dates_with_tickers(self, start_date, end_date):
        """전체 종목에 대해 틱 데이터가 생성된 날짜와 종목 목록 조회"""
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    sql = """
                        SELECT DISTINCT DATE(datetime) as gen_date, ticker
                        FROM ohlcv_tick
                        WHERE datetime >= %s AND DATE(datetime) <= %s
                    """
                    cur.execute(sql, (start_date, end_date))
                    rows = cur.fetchall()
                    
                    res = {}
                    for r in rows:
                        dt_str = str(r['gen_date'])
                        if dt_str not in res: res[dt_str] = []
                        res[dt_str].append(r['ticker'])
                    return res
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error fetching generated tick dates for ALL: {str(e)}")
            return {}


    def get_tick_data_df(self, ticker, date_str):
        """특정 날짜의 틱 데이터를 Pandas DataFrame으로 고속 조회"""
        ticker = self.normalize_ticker(ticker)
        try:
            # DictCursor 대신 일반 커서 사용 (오버헤드 감소)
            conn_params = self.conn_params.copy()
            conn_params['cursorclass'] = pymysql.cursors.Cursor
            
            conn = pymysql.connect(**conn_params)
            try:
                sql = """
                    SELECT datetime as ts, close as price, volume, scenario
                    FROM ohlcv_tick
                    WHERE ticker = %s AND DATE(datetime) = %s
                    ORDER BY datetime ASC
                """
                # read_sql을 사용하여 고속 로드
                df = pd.read_sql(sql, conn, params=(ticker, date_str))
                # 데이터 타입 최적화
                df['price'] = df['price'].astype(float)
                df['volume'] = df['volume'].astype(int)
                return df
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error fetching tick data df for {ticker}: {str(e)}")
            return pd.DataFrame()

    def get_tick_data_df_range(self, ticker, start_date, end_date):
        """특정 기간의 틱 데이터를 Pandas DataFrame으로 고속 조회"""
        ticker = self.normalize_ticker(ticker)
        try:
            conn_params = self.conn_params.copy()
            conn_params['cursorclass'] = pymysql.cursors.Cursor
            
            conn = pymysql.connect(**conn_params)
            try:
                sql = """
                    SELECT datetime as ts, close as price, volume, scenario
                    FROM ohlcv_tick
                    WHERE ticker = %s AND DATE(datetime) BETWEEN %s AND %s
                    ORDER BY datetime ASC
                """
                df = pd.read_sql(sql, conn, params=(ticker, start_date, end_date))
                df['price'] = df['price'].astype(float)
                df['volume'] = df['volume'].astype(int)
                return df
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error fetching tick data range for {ticker}: {str(e)}")
            return pd.DataFrame()


    def get_ohlcv_data(self, ticker, interval, limit=100):
        """최신 OHLCV 데이터 조회"""
        ticker = self.normalize_ticker(ticker)
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    table_name = self._get_ohlcv_table(interval)
                    cur.execute(f"""
                        SELECT datetime, open, high, low, close, volume 
                        FROM {table_name} 
                        WHERE ticker = %s 
                        ORDER BY datetime DESC LIMIT %s
                    """, (ticker, limit))
                    return cur.fetchall()
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error fetching ohlcv data for {ticker}: {str(e)}")
            return []

    def add_ticker(self, ticker, name=None, market=None, buy_rule='DEFAULT'):
        ticker = self.normalize_ticker(ticker)
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    # MySQL/MariaDB compatible syntax
                    cur.execute("""
                        INSERT INTO tickers (ticker, name, market, buy_rule, is_active) 
                        VALUES (%s, %s, %s, %s, 1)
                        ON DUPLICATE KEY UPDATE 
                            name = VALUES(name),
                            market = VALUES(market),
                            buy_rule = VALUES(buy_rule)
                    """, (ticker, name, market, buy_rule))
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error adding ticker {ticker} to DB: {str(e)}")

    def update_ticker_rule(self, ticker, rule_name):
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    # Update rule and set is_active = 1
                    cur.execute("UPDATE tickers SET buy_rule = %s, is_active = 1 WHERE ticker = %s", (rule_name, ticker))
                conn.commit()
                logging.info(f"Updated buy_rule for {ticker} to {rule_name} (Active)")
                return True
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error updating rule for {ticker}: {str(e)}")
            return False

    def update_ticker_status(self, ticker, is_active):
        # ticker는 normalized 형태(000660) 또는 raw 형태(000660.KS)일 수 있음
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    val = 1 if is_active else 0
                    # 먼저 normalize된 ticker로 시도
                    norm_ticker = self.normalize_ticker(ticker)
                    cur.execute("UPDATE tickers SET is_active = %s WHERE ticker = %s", (val, norm_ticker))
                    if cur.rowcount == 0:
                        # .KS 형식으로도 시도
                        cur.execute("UPDATE tickers SET is_active = %s WHERE ticker = %s", (val, ticker))
                    if cur.rowcount == 0:
                        # .KS 접미사 추가해서 다시 시도
                        kr_ticker = f"{norm_ticker}.KS"
                        cur.execute("UPDATE tickers SET is_active = %s WHERE ticker = %s", (val, kr_ticker))
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error updating status for {ticker}: {str(e)}")
            return False

    def deactivate_all_tickers(self):
        """본체의 모든 종목을 비활성(일시정지) 상태로 변경"""
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE tickers SET is_active = 0")
                conn.commit()
                logging.info("All tickers deactivated in database.")
                return True
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error deactivating all tickers: {str(e)}")
            return False



    def get_tickers(self):
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT ticker, name, market, buy_rule, is_active FROM tickers ORDER BY added_at ASC")
                    rows = cur.fetchall()
                    # DictCursor returns list of dicts
                    return rows
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error fetching tickers from DB: {str(e)}")
            return []

    def resolve_ticker(self, query):
        """종목 코드 또는 이름으로 실제 종목 코드를 찾아 반환"""
        if not query: return None
        
        # 0. 5자리 숫자만 들어온 경우(한국 주식 앞자리 0 누락) 0을 채워서 시도
        query_str = str(query).strip()
        if query_str.isdigit() and len(query_str) == 5:
            query_str = "0" + query_str

        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    # 1. 먼저 코드로 직접 매칭되는지 확인
                    cur.execute("SELECT ticker FROM tickers WHERE ticker = %s", (query_str,))
                    row = cur.fetchone()
                    if row:
                        return row['ticker']
                    
                    # 2. 이름으로 매칭되는지 확인
                    cur.execute("SELECT ticker FROM tickers WHERE name = %s", (query_str,))
                    row = cur.fetchone()
                    if row:
                        return row['ticker']
                    
                    # 3. 만약 tickers 테이블에 없더라도 ohlcv_tick에 직접 있을 수 있음 (코드로)
                    cur.execute("SELECT DISTINCT ticker FROM ohlcv_tick WHERE ticker = %s", (query_str,))
                    row = cur.fetchone()
                    if row:
                        return row['ticker']
                    
                return None
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error resolving ticker '{query}': {str(e)}")
            return None


    def remove_ticker(self, ticker):
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM tickers WHERE ticker = %s", (ticker,))
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error removing ticker {ticker} from DB: {str(e)}")

    def _ensure_strategy_folder(self):
        """strategy 폴더가 없으면 생성"""
        strategy_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'strategy')
        if not os.path.exists(strategy_dir):
            os.makedirs(strategy_dir)
            logging.info(f"Created strategy directory: {strategy_dir}")
        return strategy_dir

    def save_strategy(self, name, content):
        """전략을 strategy 폴더에 .txt 파일로 저장"""
        try:
            strategy_dir = self._ensure_strategy_folder()
            file_path = os.path.join(strategy_dir, f"{name}.txt")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logging.info(f"Strategy '{name}' saved to {file_path}")
            return True
        except Exception as e:
            logging.error(f"Error saving strategy {name}: {str(e)}")
            return False

    def get_strategies(self):
        """strategy 폴더의 모든 전략 파일 목록 반환"""
        try:
            strategy_dir = self._ensure_strategy_folder()
            strategies = []
            
            if os.path.exists(strategy_dir):
                for filename in os.listdir(strategy_dir):
                    if filename.endswith('.txt'):
                        name = filename[:-4]  # .txt 제거
                        file_path = os.path.join(strategy_dir, filename)
                        
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # 파일 수정 시간
                        mtime = os.path.getmtime(file_path)
                        from datetime import datetime
                        updated_at = datetime.fromtimestamp(mtime)
                        
                        strategies.append({
                            'name': name,
                            'content': content,
                            'updated_at': updated_at
                        })
            
            # 최신순 정렬
            strategies.sort(key=lambda x: x['updated_at'], reverse=True)
            return strategies
        except Exception as e:
            logging.error(f"Error fetching strategies: {str(e)}")
            return []

    def get_strategy(self, name):
        """특정 전략 파일 읽기"""
        try:
            strategy_dir = self._ensure_strategy_folder()
            file_path = os.path.join(strategy_dir, f"{name}.txt")
            
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return {'name': name, 'content': content}
            else:
                logging.warning(f"Strategy file not found: {file_path}")
                return None
        except Exception as e:
            logging.error(f"Error fetching strategy {name}: {str(e)}")
            return None

    def delete_strategy(self, name):
        """전략 파일 삭제"""
        try:
            strategy_dir = self._ensure_strategy_folder()
            file_path = os.path.join(strategy_dir, f"{name}.txt")
            
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f"Strategy '{name}' deleted from {file_path}")
                return True
            else:
                logging.warning(f"Strategy file not found for deletion: {file_path}")
                return False
        except Exception as e:
            logging.error(f"Error deleting strategy {name}: {str(e)}")
            return False

    def delete_tick_data(self, ticker, date_str=None):
        """특정 종목 또는 특정 날짜의 틱 데이터 삭제"""
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    sql = "DELETE FROM ohlcv_tick WHERE ticker = %s"
                    params = [ticker]
                    if date_str:
                        sql += " AND DATE(datetime) = %s"
                        params.append(date_str)
                    cur.execute(sql, tuple(params))
                    
                    # 요약 테이블(ohlcv_tick_sum)에서도 삭제 필요
                    sum_sql = "DELETE FROM ohlcv_tick_sum WHERE ticker = %s"
                    sum_params = [ticker]
                    if date_str:
                        sum_sql += " AND date = %s"
                        sum_params.append(date_str)
                    cur.execute(sum_sql, tuple(sum_params))
                    
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error deleting tick data for {ticker}: {str(e)}")
            return False

    def delete_ticker_data(self, ticker):
        """특정 종목의 모든 데이터(정보 및 시세) 삭제"""
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    for table_name in ['ohlcv_1m', 'ohlcv_5m', 'ohlcv_1d', 'ohlcv_tick', 'ohlcv_1m_sum', 'ohlcv_5m_sum', 'ohlcv_tick_sum']:
                        try:
                            cur.execute(f"DELETE FROM {table_name} WHERE ticker = %s", (ticker,))
                        except:
                            pass
                    # 3. 종목 정보 삭제
                    cur.execute("DELETE FROM tickers WHERE ticker = %s", (ticker,))
                conn.commit()
                logging.info(f"All data for ticker '{ticker}' deleted successfully")
                return True
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error deleting ticker data for {ticker}: {str(e)}")
            return False
    def init_backtest_tables(self):
        """백테스트 결과를 저장할 테이블 생성"""
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS backtest_results (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            ticker VARCHAR(20),
                            strategy_name VARCHAR(100),
                            data_date VARCHAR(20),
                            profit_rate DECIMAL(20, 4),
                            total_trades INT,
                            max_dd DECIMAL(10, 4),
                            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            result_data LONGTEXT
                        )
                    """)
                conn.commit()
                logging.info("Backtest result tables initialized")
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Backtest table initialization error: {str(e)}")

    def save_backtest_result(self, ticker, strategy_name, data_date, profit_rate, total_trades, max_dd, result_data_json):
        """백테스트 결과 저장"""
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    sql = """
                        INSERT INTO backtest_results 
                        (ticker, strategy_name, data_date, profit_rate, total_trades, max_dd, result_data)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    cur.execute(sql, (ticker, strategy_name, data_date, profit_rate, total_trades, max_dd, result_data_json))
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error saving backtest result: {str(e)}")
            return False

    def get_backtest_results(self, limit=100):
        """백테스트 결과 목록 조회 (내용은 제외하고 메타데이터만)"""
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    sql = """
                        SELECT b.id, b.ticker, b.strategy_name, b.data_date, b.profit_rate, b.total_trades, b.max_dd, b.executed_at, t.name as ticker_name
                        FROM backtest_results b
                        LEFT JOIN tickers t ON SUBSTRING_INDEX(b.ticker, '.', 1) = SUBSTRING_INDEX(t.ticker, '.', 1)
                        ORDER BY b.executed_at DESC LIMIT %s
                    """
                    cur.execute(sql, (limit,))
                    return cur.fetchall()
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error fetching backtest results: {str(e)}")
            return []

    def get_backtest_result_detail(self, result_id):
        """특정 백테스트 결과의 상세 JSON 데이터 조회"""
        try:
            # 상세 조회 시에는 DictCursor가 필요할 수 있으나, 
            # 이 클래스 생성 시 이미 DictCursor를 기본으로 함(line 15)
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    sql = "SELECT result_data FROM backtest_results WHERE id = %s"
                    cur.execute(sql, (result_id,))
                    row = cur.fetchone()
                    return row['result_data'] if row else None
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error fetching backtest detail {result_id}: {str(e)}")
            return None

    def delete_backtest_result(self, result_id):
        """백테스트 결과 삭제"""
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM backtest_results WHERE id = %s", (result_id,))
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error deleting backtest result {result_id}: {str(e)}")
            return False
    def init_trade_tables(self):
        """매매 내역(체결 내역)을 저장할 테이블 생성"""
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS trades (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            ticker VARCHAR(20),
                            ticker_name VARCHAR(100),
                            side VARCHAR(10), -- BUY, SELL
                            price DECIMAL(20, 4),
                            qty INT,
                            amount DECIMAL(20, 4),
                            buy_amount DECIMAL(20, 4) DEFAULT 0,
                            buy_price DECIMAL(20, 4) DEFAULT 0,
                            fee DECIMAL(20, 4) DEFAULT 0,
                            tax DECIMAL(20, 4) DEFAULT 0,
                            profit DECIMAL(20, 4) DEFAULT 0,
                            profit_rate DECIMAL(10, 4) DEFAULT 0,
                            execution_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                            acc_no VARCHAR(20),
                            order_no VARCHAR(50),
                            memo TEXT,
                            INDEX idx_ticker (ticker),
                            INDEX idx_time (execution_time),
                            UNIQUE INDEX idx_unique_trade (order_no, ticker, execution_time, side)
                        )
                    """)
                conn.commit()

                # 신규 컬럼 마이그레이션 (ALTER TABLE - 이미 컬럼이 있으면 무시)
                migration_cols = [
                    ("buy_amount", "DECIMAL(20,4) DEFAULT 0"),
                    ("buy_price", "DECIMAL(20,4) DEFAULT 0"),
                    ("profit_rate", "DECIMAL(10,4) DEFAULT 0"),
                    ("acc_no", "VARCHAR(20)")
                ]
                for col_name, col_def in migration_cols:
                    try:
                        with conn.cursor() as cur2:
                            cur2.execute(f"ALTER TABLE trades ADD COLUMN {col_name} {col_def}")
                        conn.commit()
                        logging.info(f"Trade table migration: added column {col_name}")
                    except Exception:
                        pass # 이미 존재하면 무시

                # 일자별 정산 기준 실현손익 (키움 opt10074)
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS daily_profit_totals (
                            date DATE,
                            acc_no VARCHAR(20),
                            buy_amount DECIMAL(20, 4) DEFAULT 0,
                            sell_amount DECIMAL(20, 4) DEFAULT 0,
                            profit DECIMAL(20, 4) DEFAULT 0,
                            fee DECIMAL(20, 4) DEFAULT 0,
                            tax DECIMAL(20, 4) DEFAULT 0,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            PRIMARY KEY (date, acc_no)
                        )
                    """)
                conn.commit()

                logging.info("Trade tables initialized")
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Trade table initialization error: {str(e)}")

    def save_trade(self, ticker, side, price, qty, amount, execution_time=None, ticker_name=None, profit=0, fee=0, tax=0, order_no=None, buy_amount=0, buy_price=0, profit_rate=0, acc_no=None, memo=None):
        """매매 내역 저장"""
        try:
            conn = self.get_connection()
            try:
                # execution_time이 없으면 현재 시간 사용
                if not execution_time:
                    execution_time = datetime.now()

                with conn.cursor() as cur:
                    sql = """
                        INSERT INTO trades
                        (ticker, ticker_name, side, price, qty, amount, profit, fee, tax, execution_time, order_no, buy_amount, buy_price, profit_rate, acc_no, memo)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        profit = VALUES(profit),
                        buy_amount = VALUES(buy_amount),
                        buy_price = VALUES(buy_price),
                        profit_rate = VALUES(profit_rate),
                        ticker_name = VALUES(ticker_name),
                        price = VALUES(price),
                        qty = VALUES(qty),
                        amount = VALUES(amount),
                        fee = VALUES(fee),
                        tax = VALUES(tax),
                        acc_no = VALUES(acc_no),
                        memo = VALUES(memo)
                    """
                    cur.execute(sql, (ticker, ticker_name, side, price, qty, amount, profit, fee, tax, execution_time, order_no, buy_amount, buy_price, profit_rate, acc_no, memo))
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error saving trade: {str(e)}")
            return False

    def delete_trades_by_date(self, date_str, acc_no=None):
        """특정 날짜의 모든 매매 내역 삭제 (동기화 전용)"""
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    # DATE(execution_time)이 해당 날짜인 것들 삭제
                    if acc_no:
                        sql = "DELETE FROM trades WHERE DATE(execution_time) = %s AND acc_no = %s"
                        cur.execute(sql, (date_str, acc_no))
                    else:
                        sql = "DELETE FROM trades WHERE DATE(execution_time) = %s"
                        cur.execute(sql, (date_str,))
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error deleting trades for {date_str}: {str(e)}")
            return False

    def get_trades_by_date(self, date_str, acc_no=None):
        """특정 날짜의 매매 내역 조회"""
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    if acc_no:
                        sql = """
                            SELECT *, DATE_FORMAT(execution_time, '%%Y-%%m-%%d %%H:%%i:%%s') as time_str
                            FROM trades 
                            WHERE DATE(execution_time) = %s AND acc_no = %s
                            ORDER BY execution_time ASC
                        """
                        cur.execute(sql, (date_str, acc_no))
                    else:
                        sql = """
                            SELECT *, DATE_FORMAT(execution_time, '%%Y-%%m-%%d %%H:%%i:%%s') as time_str
                            FROM trades 
                            WHERE DATE(execution_time) = %s 
                            ORDER BY execution_time ASC
                        """
                        cur.execute(sql, (date_str,))
                    return cur.fetchall()
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error fetching trades for {date_str}: {str(e)}")
            return []

    def get_monthly_trade_summary(self, year, month, acc_no=None):
        """특정 월의 일별 매매 요약 (수익금 합계 등)"""
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    where_clause = "WHERE YEAR(execution_time) = %s AND MONTH(execution_time) = %s"
                    params = [year, month]
                    if acc_no:
                        where_clause += " AND acc_no = %s"
                        params.append(acc_no)
                    
                    sql = f"""
                        SELECT 
                            DATE(execution_time) as date,
                            COUNT(*) as trade_count,
                            SUM(profit) as total_profit,
                            SUM(CASE WHEN side IN ('SELL','SUMMARY') THEN COALESCE(amount,0) ELSE 0 END) as total_amount
                        FROM trades 
                        {where_clause}
                        GROUP BY DATE(execution_time)
                    """
                    cur.execute(sql, tuple(params))
                    rows = cur.fetchall()
                    
                    res = {}
                    for r in rows:
                        date_str = str(r['date'])
                        res[date_str] = {
                            "trade_count": r['trade_count'],
                            "profit": float(r['total_profit']),
                            "amount": float(r['total_amount'])
                        }
                    return res
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error fetching monthly trade summary: {str(e)}")
            return {}

    def save_daily_profit_total(self, date_str, acc_no, buy_amount=0, sell_amount=0, profit=0, fee=0, tax=0):
        """일자별 정산 기준 실현손익(키움 opt10074) 저장"""
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO daily_profit_totals
                        (date, acc_no, buy_amount, sell_amount, profit, fee, tax)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        buy_amount = VALUES(buy_amount),
                        sell_amount = VALUES(sell_amount),
                        profit = VALUES(profit),
                        fee = VALUES(fee),
                        tax = VALUES(tax)
                    """, (date_str, acc_no, buy_amount, sell_amount, profit, fee, tax))
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error saving daily profit total: {str(e)}")
            return False

    def get_daily_profit_total(self, date_str, acc_no=None):
        """특정 날짜의 정산 기준 실현손익 조회 (없으면 None)"""
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    if acc_no:
                        cur.execute("SELECT * FROM daily_profit_totals WHERE date = %s AND acc_no = %s",
                                    (date_str, acc_no))
                    else:
                        cur.execute("SELECT * FROM daily_profit_totals WHERE date = %s", (date_str,))
                    row = cur.fetchone()
                    if not row:
                        return None
                    return {
                        "date": str(row["date"]), "acc_no": row["acc_no"],
                        "buy_amount": float(row["buy_amount"]), "sell_amount": float(row["sell_amount"]),
                        "profit": float(row["profit"]), "fee": float(row["fee"]), "tax": float(row["tax"]),
                    }
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error fetching daily profit total: {str(e)}")
            return None

    def get_daily_profit_totals_by_month(self, year, month, acc_no=None):
        """특정 월의 정산 기준 실현손익 목록 {date: {profit, sell_amount}}"""
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    where_clause = "WHERE YEAR(date) = %s AND MONTH(date) = %s"
                    params = [year, month]
                    if acc_no:
                        where_clause += " AND acc_no = %s"
                        params.append(acc_no)
                    cur.execute(f"SELECT * FROM daily_profit_totals {where_clause}", tuple(params))
                    res = {}
                    for row in cur.fetchall():
                        res[str(row["date"])] = {
                            "profit": float(row["profit"]),
                            "sell_amount": float(row["sell_amount"]),
                        }
                    return res
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error fetching monthly daily profit totals: {str(e)}")
            return {}
