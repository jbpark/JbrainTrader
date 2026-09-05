import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import base64
import logging
from datetime import datetime, time

class IntradaySpreadTrader:
    def __init__(self, ticker1="069500", ticker2="114800", threshold=1.5, start_cash=10000000.0, strategy_mgr=None, strategy_name=None, name1=None, name2=None):
        self.ticker1 = ticker1
        self.ticker2 = ticker2
        self.name1 = name1 or ticker1.split('.')[0]
        self.name2 = name2 or ticker2.split('.')[0]
        self.threshold = threshold
        self.start_cash = start_cash
        self.cash = start_cash
        self.scaling_ratios = [0.4, 0.3, 0.3]  # 40%, 30%, 30%
        
        # Risk & Limits
        self.target_profit = 0.005  # +0.5%
        self.stop_loss = -0.007     # -0.7%
        self.max_daily_trades = 3
        
        # Advanced Parameters (Configurable via TXT)
        self.strategy_name = strategy_name
        self.window_size = 15
        self.exit_z = 0.1
        self.use_ema = False
        self.start_time_limit = time(9, 0) # 기본값
        self.end_time_limit = time(15, 15) # 기본값
        
        # US Stock Detection
        self.is_us = not (str(ticker1).split('.')[0].isdigit())
        if self.is_us:
            # US 데이터는 현지 시간(US Date) 기준으로 저장 및 백테스트 진행
            self.start_time_limit = time(9, 30) # US 표준 개장 시간
            self.end_time_limit = time(16, 0)  # US 표준 폐장 시간
            logging.info(f"[IntradaySpreadTrader] US Ticker detected. Setting local hours to {self.start_time_limit} ~ {self.end_time_limit}")
        
        # 수수료 설정 (미국 주식 vs 한국 주식)
        if self.is_us:
            self.buy_fee_rate = 0.0025       # 한투 매수 수수료 0.25%
            self.sell_fee_rate = 0.0025      # 한투 매도 수수료 0.25%
            self.sec_fee_rate = 0.0000278    # SEC Fee: 매도 대금의 0.00278%
            self.taf_per_share = 0.000166    # TAF: 주당 $0.000166
            self.taf_max = 8.30             # TAF 최대 $8.30
        else:
            self.buy_fee_rate = 0.00015     # 키움 매수 수수료 0.015%
            self.sell_fee_rate = 0.00015    # 키움 매도 수수료 0.015%
            self.sell_tax_rate = 0.002      # 매도 거래세 0.2%
            self.sec_fee_rate = 0.0
            self.taf_per_share = 0.0
            self.taf_max = 0.0
        
        # Load from Strategy File if exists
        if strategy_mgr and strategy_name:
            self._apply_strategy_config(strategy_mgr, strategy_name)
            
        # Internal State
        self.position = None  # {ticker, qty, entry_price, count, total_cost}
        self.daily_trade_count = 0
        self.trade_log = []
        self.history = []
        self.max_pnl_rate = 0.0  # 트레일링 스톱용 최고 수익률 추적


    def _apply_strategy_config(self, mgr, name):
        """전략 파일에서 파라미터 로드"""
        try:
            import configparser
            import re
            
            # configparser 강제 임포트 및 설정 (interpolation=None으로 % 오류 방지)
            config = configparser.ConfigParser(interpolation=None)
            
            strat = mgr.get_strategy(name)
            if not strat:
                logging.warning(f"[_apply_strategy_config] Strategy not found: {name}")
                return
            
            config.read_string(strat['content'])
            
            # 섹션 찾기 ([설정] 또는 [INFO] 또는 첫 번째 섹션)
            section = None
            if '설정' in config: section = '설정'
            elif 'INFO' in config: section = 'INFO'
            elif config.sections(): section = config.sections()[0]
            
            if not section:
                logging.warning(f"[_apply_strategy_config] No valid section found in strategy: {name}")
                return

            logging.info(f"[_apply_strategy_config] Loading config from section '{section}' of strategy '{name}'")
            
            # 임계값
            if '임계값' in config[section]:
                self.threshold = float(config.get(section, '임계값'))
            
            # 목표수익
            if '목표수익' in config[section]:
                val = config.get(section, '목표수익')
                match = re.search(r'([-+]?\d*\.?\d+)', val)
                if match: self.target_profit = float(match.group(1)) / 100.0
                
            # 손절기준
            if '손절기준' in config[section]:
                val = config.get(section, '손절기준')
                match = re.search(r'([-+]?\d*\.?\d+)', val)
                if match: self.stop_loss = float(match.group(1)) / 100.0
                
            # 최대거래
            if '최대거래' in config[section]:
                val = config.get(section, '최대거래')
                match = re.search(r'(\d+)', val)
                if match: self.max_daily_trades = int(match.group(1))
                
            # 분할매수비율
            if '분할매수' in config[section]:
                val = config.get(section, '분할매수')
                ratios = re.findall(r'(\d+)%', val)
                if ratios:
                    self.scaling_ratios = [float(r)/100.0 for r in ratios]
            
            # 매수금액 (투자 원금)
            if '매수금액' in config[section]:
                val = config.get(section, '매수금액')
                # 콤마, 공백 등 제거하고 숫자만 추출
                num_str = re.sub(r'[^\d]', '', val)
                if num_str:
                    old_cash = self.start_cash
                    self.start_cash = float(num_str)
                    self.cash = self.start_cash
                    logging.info(f"[_apply_strategy_config] Updated start_cash: {old_cash:,.0f} -> {self.start_cash:,.0f}")
                else:
                    logging.warning(f"[_apply_strategy_config] Invalid '매수금액' format: {val}")
            
            # v2 개선 파라미터들
            if '윈도우' in config[section]:
                self.window_size = int(re.search(r'(\d+)', config.get(section, '윈도우')).group(1))
            
            if '익절Z' in config[section]:
                self.exit_z = float(re.search(r'([-+]?\d*\.?\d+)', config.get(section, '익절Z')).group(1))
            
            # 전략명이나 내용에 따라 EMA 사용 여부 결정
            if '2' in str(name) or 'EWMA' in strat['content'].upper():
                self.use_ema = True
                logging.info(f"[_apply_strategy_config] EMA(EWMA) mode enabled for {name}")

            # 시작시간 필터
            if '시작시간' in config[section]:
                t_str = config.get(section, '시작시간')
                match = re.search(r'(\d{2}):(\d{2})', t_str)
                if match:
                    self.start_time_limit = time(int(match.group(1)), int(match.group(2)))
                    logging.info(f"[_apply_strategy_config] Start time limit set to {self.start_time_limit}")

            # 종료시간(강제청산) 필터
            if '강제청산' in config[section]:
                t_str = config.get(section, '강제청산')
                match = re.search(r'(\d{2}):(\d{2})', t_str)
                if match:
                    self.end_time_limit = time(int(match.group(1)), int(match.group(2)))
                    logging.info(f"[_apply_strategy_config] End time limit set to {self.end_time_limit}")
                elif '종료' in t_str or '없음' in t_str:
                    # US 주식이고 강제청산이 없으면 오전 4:00 (US 현지 기준 장마감 후 넉넉히) 또는 KR 15:30
                    self.end_time_limit = time(16, 0) if self.is_us else time(15, 30)
                    logging.info(f"[_apply_strategy_config] Force exit disabled (default to {self.end_time_limit})")

            # 수수료 우대율 (예: 0.09% 우대 적용)
            if '수수료' in config[section]:
                val = config.get(section, '수수료')
                match = re.search(r'([-+]?\d*\.?\d+)', val)
                if match:
                    fee_rate = float(match.group(1)) / 100.0
                    self.buy_fee_rate = fee_rate
                    self.sell_fee_rate = fee_rate
                    logging.info(f"[_apply_strategy_config] Fee rate override: {fee_rate*100:.4f}%")

            logging.info(f"✅ [_apply_strategy_config] SUCCESS: Strategy '{name}' parameters applied.")
            logging.info(f"   -> start_cash={self.start_cash:,.0f}, threshold={self.threshold}")
            logging.info(f"   -> target={self.target_profit*100:.2f}%, stop={self.stop_loss*100:.2f}%")
            logging.info(f"   -> window={self.window_size}, exit_z={self.exit_z}, is_us={self.is_us}")
            logging.info(f"   -> time_limit={self.start_time_limit} ~ {self.end_time_limit}")
            
            # 🔒 안전장치: 미국 종목에 한국형 시간 제한이 적용되면 US 장마감 시간으로 보정
            if self.is_us:
                # 한국 시장 종료 시간(14:00~16:00)이 설정된 경우 → US 현지 시간으로 복원
                if time(14, 0) <= self.end_time_limit <= time(16, 0):
                    # 만약 이미 16:00이면 정상이지만 다른 한국 시간대면 16:00으로 강제
                    if self.end_time_limit != time(16, 0):
                        logging.warning(f"[_apply_strategy_config] ⚠️ US ticker detected but Korean time limit ({self.end_time_limit}) was set. Overriding to US Closing: 16:00.")
                        self.end_time_limit = time(16, 0)
                        self.start_time_limit = time(9, 30)
                    logging.info(f"   -> time_limit CORRECTED: {self.start_time_limit} ~ {self.end_time_limit}")

        except Exception as e:
            logging.error(f"[_apply_strategy_config] Error parsing strategy config: {e}", exc_info=True)

    def log(self, dt, message):
        timestamp = dt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(dt, 'strftime') else str(dt)
        log_msg = f"[{timestamp}] {message}"
        self.trade_log.append(log_msg)
        logging.info(log_msg)

    def load_data(self, db, start_date, end_date=None):
        """DB에서 두 ETF의 1분봉 데이터를 가져와 병합 (날짜 범위 지원)"""
        if end_date is None:
            end_date = start_date
            
        df1 = self._get_ohlcv(df=db, ticker=self.ticker1, start_date=start_date, end_date=end_date)
        df2 = self._get_ohlcv(df=db, ticker=self.ticker2, start_date=start_date, end_date=end_date)
        
        if df1.empty or df2.empty:
            logging.warning(f"[load_data] Data missing: {self.ticker1}({len(df1)} rows), {self.ticker2}({len(df2)} rows)")
            return pd.DataFrame()
            
        # 시간대를 기준으로 병합
        combined = pd.merge(df1, df2, on='datetime', suffixes=('_etf1', '_etf2'))
        combined.sort_values('datetime', inplace=True)
        return combined

    def _get_ohlcv(self, df, ticker, start_date, end_date):
        """DB에서 특정 기간의 OHLCV 데이터 조회"""
        # db 객체가 DatabaseManager 인스턴스라고 가정 (df 변수명은 호환성 유지용)
        db = df
        conn = db.get_connection()
        # 티커 정규화 (DB 저장 형식에 맞춰 .KS 등 제거)
        norm_ticker = ticker.split('.')[0] if '.' in ticker else ticker
        try:
            with conn.cursor() as cur:
                sql = """
                    SELECT datetime, open, high, low, close, volume 
                    FROM ohlcv_1m 
                    WHERE ticker = %s AND DATE(datetime) BETWEEN %s AND %s
                    ORDER BY datetime ASC
                """
                cur.execute(sql, (norm_ticker, start_date, end_date))
                rows = cur.fetchall()
                df = pd.DataFrame(rows)
                if not df.empty:
                    df['datetime'] = pd.to_datetime(df['datetime'])
                    for col in ['open', 'high', 'low', 'close']:
                        df[col] = df[col].apply(float)
                else:
                    # 정규화하지 않은 티커로도 시도
                    cur.execute(sql, (ticker, start_date, end_date))
                    rows = cur.fetchall()
                    df = pd.DataFrame(rows)
                    if not df.empty:
                        df['datetime'] = pd.to_datetime(df['datetime'])
                        for col in ['open', 'high', 'low', 'close']:
                            df[col] = df[col].apply(float)
                return df
        finally:
            conn.close()

    def calculate_indicators(self, df):
        """수익률, 상대 스프레드, Z-Score 계산"""
        if df.empty: return df
        
        # 1. 상대적 가격 지수 (Relative Price Index)
        df['idx1'] = df['close_etf1'] / df['close_etf1'].iloc[0]
        df['idx2'] = df['close_etf2'] / df['close_etf2'].iloc[0]
        
        # 2. Spread 계산
        if self.is_us:
            # 미국 ETF: 로그 수익률 기반 스프레드
            # QQQ(1X) vs SQQQ(-3X)의 경우, 레버리지 비율(3:1)을 고려하여 스프레드 계산
            # 3 * log_ret(QQQ) + 1 * log_ret(SQQQ) ≈ 0 이 되어야 함
            df['log_ret1'] = np.log(df['idx1']).diff().fillna(0)
            df['log_ret2'] = np.log(df['idx2']).diff().fillna(0)
            
            # 티커별 레버리지 배율에 맞춰 가중치 결정
            t1u, t2u = str(self.ticker1).upper(), str(self.ticker2).upper()
            if 'TQQQ' in t1u and 'SQQQ' in t2u:
                # TQQQ(+3x) vs SQQQ(-3x): 레버리지가 동일하므로 1:1
                df['spread'] = (df['log_ret1'] + df['log_ret2']).cumsum()
            elif 'SQQQ' in t2u:
                # QQQ(+1x) vs SQQQ(-3x): 3:1 가중 (3*log_ret(QQQ) + log_ret(SQQQ) ≈ 0)
                df['spread'] = (3 * df['log_ret1'] + df['log_ret2']).cumsum()
            else:
                df['spread'] = (df['log_ret1'] + df['log_ret2']).cumsum()
        else:
            # 한국 ETF: 티커별 레버리지 비율을 고려한 스프레드 계산
            # KODEX 200(069500), KODEX 레버리지(122630), KODEX 200선물인버스2X(252670) 등 대응
            df['log_ret1'] = np.log(df['idx1']).diff().fillna(0)
            df['log_ret2'] = np.log(df['idx2']).diff().fillna(0)
            
            t1, t2 = str(self.ticker1), str(self.ticker2)
            
            # Case 1: KODEX 200(069500) vs 인버스 2X(252670) -> 2:1 비율
            if '069500' in t1 and '252670' in t2:
                df['spread'] = (2 * df['log_ret1'] + df['log_ret2']).cumsum()
            elif '252670' in t1 and '069500' in t2:
                df['spread'] = (df['log_ret1'] + 2 * df['log_ret2']).cumsum()
                
            # Case 2: 레버리지(122630) vs 인버스 2X(252670) -> 1:1 비율 (부합)
            elif '122630' in t1 and '252670' in t2:
                df['spread'] = (df['log_ret1'] + df['log_ret2']).cumsum()
                
            # Case 3: KODEX 200(069500) vs 인버스(114800) -> 1:1 비율
            elif ('069500' in t1 or '122630' in t1) and '114800' in t2:
                df['spread'] = (df['log_ret1'] + df['log_ret2']).cumsum()
                
            else:
                # 기본값: 가격 지수 차이 (동종 종목 간 차익거래용)
                df['spread'] = df['idx1'] - df['idx2']
        
        # 데이터가 완전 일치하는 경우 (가상으로 인버스화 시도 - 데모용)
        if (df['spread'] == 0).all():
            logging.warning("DATA IDENTITY DETECTED: Synthetic Inverse Applied for Backtest.")
            df['idx2'] = 1.0 / df['idx1']
            df['spread'] = df['idx1'] - df['idx2']
            self.log(df['datetime'].iloc[0], "⚠️ 주의: 데이터가 동일하여 2번 종목을 가상 인버스로 계산합니다.")

        # 3. Z-Score (민감도 조절)
        window = self.window_size
        if self.use_ema:
            df['spread_mean'] = df['spread'].ewm(span=window, adjust=False).mean()
            df['spread_std'] = df['spread'].ewm(span=window, adjust=False).std()
        else:
            df['spread_mean'] = df['spread'].rolling(window=window).mean()
            df['spread_std'] = df['spread'].rolling(window=window).std()
        
        # 가변 변동성 대응
        safe_std = df['spread_std'].replace(0, np.nan).fillna(0.0001)
        df['zscore'] = (df['spread'] - df['spread_mean']) / safe_std
        
        df.fillna(0, inplace=True)
        return df

    def generate_signal(self, row):
        """진입 신호 생성"""
        z = row['zscore']
        if z > self.threshold:
            return self.ticker2  # 인버스 매수
        elif z < -self.threshold:
            return self.ticker1  # 코스피 ETF 매수
        return None

    def manage_position(self, row, pos):
        """보유 포지션 관리 (수익/손절/추매/회귀청산/트레일링)"""
        ticker = pos['ticker']
        current_price = row[f'close_etf1'] if ticker == self.ticker1 else row[f'close_etf2']
        avg_price = pos['avg_price']
        pnl_rate = (current_price / avg_price) - 1
        
        # 트레일링 스톱 최고 수익률 갱신
        if pnl_rate > self.max_pnl_rate:
            self.max_pnl_rate = pnl_rate
        
        # 1. 손절 조건
        if pnl_rate <= self.stop_loss:
            return "STOP_LOSS"
            
        # 2. 익절 조건
        if pnl_rate >= self.target_profit:
            return "TAKE_PROFIT"
        
        # 3. 트레일링 스톱 (수수료 커버 이상의 수익 후 되돌아오면 청산)
        # 최고 수익률 대비 20% 이상 하락 시 청산 (이익 보전 강화)
        min_trailing_profit = (self.buy_fee_rate + self.sell_fee_rate) * 4  # 수수료의 4배 이상 수익 시
        if self.max_pnl_rate >= min_trailing_profit and pnl_rate > 0:
            # 예: 1.0% 수익 후 0.8%로 떨어지면 청산 (20% 하락)
            if pnl_rate <= self.max_pnl_rate * 0.8:
                return "TRAILING_STOP"
            
        # 4. Z-Score 회귀 시 청산 (수수료 감안)
        z = row['zscore']
        ez = self.exit_z
        should_revert = False
        if pos['ticker'] == self.ticker2 and z <= ez:
            should_revert = True
        if pos['ticker'] == self.ticker1 and z >= -ez:
            should_revert = True
        
        if should_revert:
            # 수수료를 감안하여 수익이 양수일 때만 회귀 청산
            total_fee_rate = self.buy_fee_rate + self.sell_fee_rate
            if self.is_us:
                total_fee_rate += self.sec_fee_rate  # SEC Fee 추가
            if pnl_rate > total_fee_rate * 2.5:
                return "MEAN_REVERSION"
            # 수수료 미만 수익이면 회귀 청산하지 않고 대기

        # 5. 분할 매수 (추매)
        # 미국 ETF는 변동이 크므로 추매 간격을 동적 조정
        scale_gap = 1.0 if self.is_us else 0.5  # 미국: 1.0, 한국: 0.5
        if pos['count'] < len(self.scaling_ratios):
            if ticker == self.ticker2 and z > self.threshold + (scale_gap * pos['count']):
                return "SCALE_IN"
            if ticker == self.ticker1 and z < -self.threshold - (scale_gap * pos['count']):
                return "SCALE_IN"
                
        return None

    def execute_trade(self, row, action, detail=None):
        """매매 실행 및 자산 업데이트"""
        dt = row['datetime']
        
        if action == "ENTRY":
            ticker = detail # detail is ticker string
            price = row[f'close_etf1'] if ticker == self.ticker1 else row[f'close_etf2']
            
            # 1차 매수
            allocation = self.start_cash * self.scaling_ratios[0]
            qty = int(allocation / price)
            if qty <= 0:
                self.log(dt, f"⚠️ 매수 불가: 가격({price:,.2f})이 너무 높아 매수 수량이 0입니다.")
                return
            cost = qty * price
            
            # 매수 수수료 차감
            buy_fee = cost * self.buy_fee_rate
            self.cash -= (cost + buy_fee)
            # max_pnl_rate 초기화는 아래로 이동 (로그용)
            self.position = {
                'ticker': ticker,
                'qty': qty,
                'avg_price': (cost + buy_fee) / qty,  # 수수료 포함 평균단가 (실제 원가)
                'count': 1,
                'total_cost': cost + buy_fee
            }
            self.max_pnl_rate = 0.0
            name = self.name1 if ticker == self.ticker1 else self.name2
            fee_str = f", 수수료: {buy_fee:,.2f}" if self.is_us else ""
            self.log(dt, f"신규 진입: {name} {qty}주 @ {price:,.2f} (매수금액: {cost:,.2f}{fee_str}, zscore: {row['zscore']:.2f})")
            
        elif action == "SCALE_IN":
            ticker = self.position['ticker']
            price = row[f'close_etf1'] if ticker == self.ticker1 else row[f'close_etf2']
            count = self.position['count']
            
            # n차 매수
            ratio = self.scaling_ratios[count]
            allocation = self.start_cash * ratio
            qty_add = int(allocation / price)
            cost_add = qty_add * price
            
            # 매수 수수료 차감
            buy_fee = cost_add * self.buy_fee_rate
            self.cash -= (cost_add + buy_fee)
            new_total_cost = self.position['total_cost'] + cost_add + buy_fee
            new_qty = self.position['qty'] + qty_add
            
            self.position.update({
                'qty': new_qty,
                'avg_price': new_total_cost / new_qty,
                'count': count + 1,
                'total_cost': new_total_cost
            })
            name = self.name1 if ticker == self.ticker1 else self.name2
            fee_str = f", 수수료: {buy_fee:,.2f}" if self.is_us else ""
            self.log(dt, f"추가 매수({count+1}차): {name} {qty_add}주 @ {price:,.2f} (매수금액: {cost_add:,.2f}{fee_str}, zscore: {row['zscore']:.2f})")

        elif action in ["TAKE_PROFIT", "STOP_LOSS", "MEAN_REVERSION", "FORCE_EXIT", "TRAILING_STOP"]:
            ticker = self.position['ticker']
            price = row[f'close_etf1'] if ticker == self.ticker1 else row[f'close_etf2']
            qty = self.position['qty']
            gross_revenue = qty * price
            
            # 매도 수수료 계산
            sell_fee = gross_revenue * self.sell_fee_rate
            if self.is_us:
                sec_fee = gross_revenue * self.sec_fee_rate
                taf = min(qty * self.taf_per_share, self.taf_max)
                total_sell_cost = sell_fee + sec_fee + taf
            else:
                sell_tax = gross_revenue * getattr(self, 'sell_tax_rate', 0.002)
                total_sell_cost = sell_fee + sell_tax
            
            net_revenue = gross_revenue - total_sell_cost
            pnl = net_revenue - self.position['total_cost']
            pnl_rate = (net_revenue / self.position['total_cost'] - 1) * 100
            
            self.cash += net_revenue
            name = self.name1 if ticker == self.ticker1 else self.name2
            fee_str = f", 총비용: {total_sell_cost:,.4f}" if self.is_us else ""
            trail_str = f", 최고수익: {self.max_pnl_rate*100:.2f}%" if action == "TRAILING_STOP" else ""
            self.log(dt, f"전량 청산({action}): {name} {qty}주 @ {price:,.2f} (수익률: {pnl_rate:.2f}%{fee_str}{trail_str})")
            
            # 로그 출력 후 초기화
            self.max_pnl_rate = 0.0 
            self.position = None

    def backtest(self, db, start_date, end_date=None):
        """특정 기간에 대한 백테스트 실행"""
        if end_date is None:
            end_date = start_date
            
        df = self.load_data(db, start_date, end_date)
        if df.empty:
            return {"status": "ERROR", "message": f"데이터가 없습니다: {start_date} ~ {end_date}"}
            
        df = self.calculate_indicators(df)
        
        # 초기화
        self.cash = self.start_cash
        self.position = None
        self.daily_trade_count = 0
        self.trade_log = []
        self.history = []
        
        self.log(start_date, f"백테스트 시작: {self.name1} vs {self.name2} ({start_date} ~ {end_date})")

        last_dt = None
        last_gap_time = None

        for i, row in df.iterrows():
            current_dt = row['datetime']
            current_time = current_dt.time()
            # US 교차 세션 대응 시간 체크 (start > end 인 경우)
            is_in_time_window = False
            if self.start_time_limit < self.end_time_limit:
                # 일반적인 주간 세션 (9:00 ~ 15:30)
                if self.start_time_limit <= current_time < self.end_time_limit:
                    is_in_time_window = True
                elif current_time >= self.end_time_limit:
                    if self.position: self.execute_trade(row, "FORCE_EXIT")
                    # 다음 날 데이터가 있을 수 있으므로 break 대신 continue
                    last_dt = current_dt
                    continue
            else:
                # 야간/교차 세션 (23:00 ~ 06:00)
                if current_time >= self.start_time_limit or current_time < self.end_time_limit:
                    is_in_time_window = True
                # 강제청산 시간: self.end_time_limit (오전) 직후
                # 예: 06:00 ~ 23:00 사이엔 매매 금지 영역
                if self.end_time_limit <= current_time < self.start_time_limit:
                    if self.position: self.execute_trade(row, "FORCE_EXIT")
                    # break는 하지 않고(다음 날 밤 데이터가 있을 수 있으므로) continue
                    last_dt = current_dt
                    continue

            if not is_in_time_window:
                last_dt = current_dt
                continue

            # 시간 갭 체크 (개장 시 갭 등)
            if last_dt is not None:
                # 1. 날짜가 바뀌었으면 일일 상태 초기화
                if current_dt.date() != last_dt.date():
                    self.daily_trade_count = 0
                    self.max_pnl_rate = 0.0
                    self.log(current_dt, f"--- New Day: {current_dt.date()} (Daily trade count reset) ---")

                diff = (current_dt - last_dt).total_seconds()
                if diff > 3600: # 1시간 이상의 갭 발생 (예: 밤과 낮의 경계)
                    last_gap_time = current_dt
                    self.log(current_dt, f"⚠️ 시간 갭 감지({diff/3600:.1f}h). 지표 안정화를 위해 30분간 신규 진입을 제한합니다.")
            
            last_dt = current_dt

            # 갭 발생 후 30분 동안은 신규 진입 제한 (Indicator Warm-up)
            is_warming_up = False
            if last_gap_time is not None:
                if (current_dt - last_gap_time).total_seconds() < 1800: # 30분
                    is_warming_up = True

            if self.position:
                decision = self.manage_position(row, self.position)
                if decision == "SCALE_IN":
                    self.execute_trade(row, decision)
                elif decision:
                    self.execute_trade(row, decision)
            else:
                # 진입 조건 체크 (최대 거래 횟수 제한 + Warm-up 기간 제외)
                if self.daily_trade_count < self.max_daily_trades and not is_warming_up:
                    signal_ticker = self.generate_signal(row)
                    if signal_ticker:
                        self.execute_trade(row, "ENTRY", detail=signal_ticker)
                        self.daily_trade_count += 1

            
            # 상태 기록
            current_val = self.cash
            if self.position:
                ticker = self.position['ticker']
                price = row[f'close_etf1'] if ticker == self.ticker1 else row[f'close_etf2']
                current_val += self.position['qty'] * price
                
            self.history.append({
                'datetime': row['datetime'],
                'cash': self.cash,
                'total_value': current_val,
                'zscore': row['zscore'],
                'spread': row['spread'],
                'close_etf1': row['close_etf1'],
                'close_etf2': row['close_etf2']
            })

        # [추가] 백테스트 종료 시점에 아직 포지션이 남아있다면 마지막 데이터로 강제 청산 처리
        if self.position and not df.empty:
            last_row = df.iloc[-1]
            # self.log(last_row['datetime'], "⚠️ 백테스트 종료로 인한 포지션 최종 강제 청산")
            self.execute_trade(last_row, "FORCE_EXIT")
            
            # 최종 total_value 다시 기록 (이미 history엔 들어가있지만 청산 후 자산 상태로 업데이트하고 싶은 경우)
            # 여기서는 마지막 history 항목의 total_value가 이미 반영되어 있으므로 로그만 남기고 넘어가도 되지만, 
            # trade_count 등을 위해 execute_trade 호출이 필수적임.

        return self.get_summary()

    def get_summary(self):
        if not self.history:
            return {"status": "ERROR", "message": "실행 이력이 없습니다."}
            
        hist_df = pd.DataFrame(self.history)
        final_value = hist_df['total_value'].iloc[-1]
        pnl = final_value - self.start_cash
        pnl_rate = (pnl / self.start_cash) * 100
        
        # MDD 계산
        hist_df['cum_max'] = hist_df['total_value'].cummax()
        hist_df['drawdown'] = (hist_df['total_value'] - hist_df['cum_max']) / hist_df['cum_max']
        max_dd = hist_df['drawdown'].min() * 100
        
        # 승률 계산 (청산 기록 기반 로그 파싱)
        import re
        exits = [l for l in self.trade_log if "전량 청산" in l]
        win_count = 0
        for e in exits:
            match = re.search(r'수익률: ([-+]?\d*\.?\d+)', e)
            if match:
                if float(match.group(1)) > 0:
                    win_count += 1
        
        trade_count = len(exits)
        win_rate = (win_count / trade_count * 100) if trade_count > 0 else 0
        
        summary = {
            "status": "SUCCESS",
            "metrics": {
                "start_cash": self.start_cash,
                "final_value": final_value,
                "pnl": pnl,
                "pnl_rate": round(pnl_rate, 2),
                "max_dd": round(max_dd, 2),
                "trade_count": trade_count,
                "win_count": win_count,
                "win_rate": round(win_rate, 2)
            },
            "logs": self.trade_log,
            "chart": self.create_plot(hist_df)
        }
        return summary

    def create_plot(self, df):
        """Matplotlib 차트 생성 및 Base64 인코딩"""
        plt.figure(figsize=(12, 10))
        
        # 1. 가격 차트
        plt.subplot(3, 1, 1)
        plt.plot(df['datetime'], df['close_etf1'], label=f'{self.name1} ({self.ticker1})', color='royalblue')
        plt.plot(df['datetime'], df['close_etf2'], label=f'{self.name2} ({self.ticker2})', color='orange')
        plt.title(f"Price Chart ({self.name1} vs {self.name2})")
        plt.legend()
        plt.grid(True, alpha=0.3)

        # 2. Spread & Z-Score
        plt.subplot(3, 1, 2)
        plt.plot(df['datetime'], df['zscore'], label='Z-Score', color='forestgreen')
        plt.axhline(y=self.threshold, color='red', linestyle='--', alpha=0.5, label='Threshold (+)')
        plt.axhline(y=-self.threshold, color='blue', linestyle='--', alpha=0.5, label='Threshold (-)')
        plt.axhline(y=0, color='black', linestyle='-', alpha=0.2)
        plt.title("Z-Score (Spread Reversion Signal)")
        plt.legend()
        plt.grid(True, alpha=0.3)

        # 3. 자산 곡선
        plt.subplot(3, 1, 3)
        plt.plot(df['datetime'], df['total_value'], label='Total Value', color='purple', linewidth=2)
        plt.title("Equity Curve")
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # 이미지 변환
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        return f"data:image/png;base64,{img_base64}"
