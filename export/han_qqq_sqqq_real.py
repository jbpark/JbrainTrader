import sys
import os
import time
import logging
import json
import requests
from datetime import datetime, time as dt_time, timedelta
import pandas as pd
import numpy as np
from cryptography.fernet import Fernet
from dotenv import load_dotenv, find_dotenv

# 프로젝트 루트 경로 추가 (부모 폴더의 core 등 모듈 참조 가능하게)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from core.broker.kis import KISBroker
from core.strategy.dual.spread_trader import IntradaySpreadTrader
from core.provider.yahoo import YahooProvider
from core.strategy_manager import StrategyManager

# === [설정] ===
STRATEGY_NAME = "DUAL_US_QQQ_SQQQ"
TICKER1 = "QQQ"
TICKER2 = "SQQQ"
LOG_FILE = os.path.join(PROJECT_ROOT, "export", "real_trading.log")

# === [암호화 복호화 유틸리티] ===
def get_fernet():
    key_path = os.path.join(PROJECT_ROOT, "secret.key")
    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            return Fernet(f.read())
    return None

def decrypt_val(val):
    if not val: return val
    f = get_fernet()
    if not f: return val
    try:
        return f.decrypt(val.encode()).decode()
    except Exception as e:
        logging.warning(f"decrypt_val: 복호화 실패로 원본 값을 그대로 사용합니다 ({e})")
        return val

# === [KIS US 브로커 확장] ===
class KISBrokerUS(KISBroker):
    """미국 주식 전용 KIS 브로커 확장"""
    
    def get_balance_us(self):
        """미국 주식 잔고/예수금 조회 (실전용)"""
        if not self._ensure_token(): return None
            
        tr_id = "VTTS3012R" if self.is_mock else "TTTS3012R"
        url = f"{self.base_url}/uapi/overseas-stock/v1/trading/inquire-balance"
        
        temp_acc = self.acc_no.replace("-", "")
        acc_main = temp_acc[:8]
        acc_sub = temp_acc[8:] if len(temp_acc) > 8 else "01"
        
        params = {
            "CANO": acc_main,
            "ACNT_PRDT_CD": acc_sub,
            "OVRS_EXCH_CD": "NASD", 
            "TR_CRCY_CD": "USD",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": ""
        }
        
        headers = self._get_headers(tr_id=tr_id)
        
        try:
            res = requests.get(url, headers=headers, params=params)
            if res.status_code == 200:
                data = res.json()
                if data.get("rt_cd") == "0":
                    summary = data.get("output2", {})
                    # exty_csh_amt: 외화종합예수금
                    balance = float(summary.get("exty_csh_amt", 0))
                    holdings = data.get("output1", [])
                    
                    parsed_holdings = []
                    for h in holdings:
                        qty = int(h.get("ovrs_ccl_qty", h.get("hldg_qty", 0)))
                        if qty > 0:
                            parsed_holdings.append({
                                "ticker": h.get("ovrs_pdno"),
                                "name": h.get("ovrs_item_name"),
                                "qty": qty,
                                "price": float(h.get("now_pric2", 0)),
                                "avg_price": float(h.get("pchs_avg_pric", 0)),
                            })
                    return {"balance": balance, "holdings": parsed_holdings}
                else:
                    logging.error(f"KIS US Balance Error: {data.get('msg1')}")
            return None
        except Exception as e:
            logging.error(f"KIS US Balance Exception: {e}")
            return None

    def order_us(self, ticker, qty, price, side="BUY"):
        """미국 주식 주문 (나스닥 지정가)"""
        if not self._ensure_token(): return None
            
        # [주의] US 실전 API TR IDs
        if self.is_mock:
            tr_id = "VTTT1002U" if side == "BUY" else "VTTT1001U"
        else:
            tr_id = "JTTT1002U" if side == "BUY" else "JTTT1006U" # NASD 기준 매도 JTTT1006U
            
        url = f"{self.base_url}/uapi/overseas-stock/v1/trading/order"
        
        temp_acc = self.acc_no.replace("-", "")
        acc_main = temp_acc[:8]
        acc_sub = temp_acc[8:] if len(temp_acc) > 8 else "01"
        
        # QQQ/SQQQ는 나스닥(NASD) 상장
        payload = {
            "CANO": acc_main,
            "ACNT_PRDT_CD": acc_sub,
            "OVRS_EXCH_CD": "NASD",
            "PDNO": ticker,
            "ORD_QTY": str(int(qty)),
            "OVRS_ORD_UNPR": str(round(price, 2)),
            "ORD_SVR_DVSN_CD": "0",
            "ORD_DVSN": "00" # 00: 지정가
        }
        
        headers = self._get_headers(tr_id=tr_id)
        
        try:
            res = requests.post(url, headers=headers, data=json.dumps(payload))
            if res.status_code == 200:
                data = res.json()
                if data.get("rt_cd") == "0":
                    logging.info(f"✅ KIS US Order Success: {side} {ticker} {qty} @ {price}")
                else:
                    logging.error(f"❌ KIS US Order Error: {data.get('msg1')} (ticker: {ticker})")
                return data
            return None
        except Exception as e:
            logging.error(f"KIS US Order Exception: {e}")
            return None

# === [실전 실행 클래스] ===
class RealUSDualTrader:
    def __init__(self, strategy_name):
        # 1. 환경 설정 로드
        load_dotenv(find_dotenv())
        
        # 2. 로깅 설정
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(LOG_FILE, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        # 3. KIS 브로커 초기화 (실전 모드)
        app_key = decrypt_val(os.getenv("KIS_REAL_APP_KEY"))
        app_secret = decrypt_val(os.getenv("KIS_REAL_APP_SECRET"))
        # 계좌번호가 .env에 직접 없을 수 있으므로 설정 파일 확인 시도
        acc_no = os.getenv("KIS_ACC_NO") 
        if not acc_no:
            # backend/settings/account_config.json 확인
            config_path = os.path.join(PROJECT_ROOT, "backend", "settings", "account_config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    acc_no = cfg.get("REAL", {}).get("acc_no")
        
        self.broker = KISBrokerUS(key=app_key, secret=app_secret, acc_no=acc_no, is_mock=False)
        if not self.broker.auth():
            logging.error("KIS API 인증 실패. 종료합니다.")
            sys.exit(1)
            
        logging.info(f"KIS US Broker initialized. Account: {self.broker.acc_no}")

        # 4. 전략 로드
        self.strat_mgr = StrategyManager()
        self.strategy_name = strategy_name
        
        # 5. 내부 인스턴스 (백테스트 로직 재사용)
        self.trader = IntradaySpreadTrader(
            ticker1=TICKER1, ticker2=TICKER2,
            strategy_mgr=self.strat_mgr, strategy_name=strategy_name
        )
        
        # 6. 데이터 제공자
        self.provider = YahooProvider()
        self.df_history = pd.DataFrame()
        
    def fetch_initial_data(self):
        """시작 시 최근 2시간 데이터를 가져와 웜업"""
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=7) # 주말/연휴 고려하여 7일치로 확대
        
        logging.info(f"Warming up indicators for {TICKER1}, {TICKER2}...")
        
        # QQQ
        df1 = self.provider.fetch_data(TICKER1, "1m", start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"))
        # SQQQ
        df2 = self.provider.fetch_data(TICKER2, "1m", start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"))
        
        if df1 is None or df2 is None or df1.empty or df2.empty:
            logging.error("초기 데이터 수집 실패.")
            return False
            
        # 병합
        df1.rename(columns={'close': 'close_etf1', 'datetime': 'datetime'}, inplace=True)
        df2.rename(columns={'close': 'close_etf2', 'datetime': 'datetime'}, inplace=True)
        
        # datetime으로 merge
        combined = pd.merge(df1[['close_etf1']], df2[['close_etf2']], left_index=True, right_index=True)
        combined['datetime'] = combined.index
        combined.reset_index(drop=True, inplace=True)
        combined = combined.sort_values('datetime').tail(200) # 최근 200개 유지
        
        self.df_history = combined
        logging.info(f"Warm-up complete. History rows: {len(self.df_history)}")
        return True

    def sync_position(self):
        """실제 계좌 잔고와 내부 포지션 동기화 (간소화)"""
        balance_info = self.broker.get_balance_us()
        if not balance_info:
            return
            
        logging.info(f"Balance (USD): {balance_info['balance']:.2f}")
        for h in balance_info['holdings']:
            logging.info(f"Holding: {h['ticker']} {h['qty']} shares (@ {h['avg_price']:.2f})")
            
            # 이미 보유 중인 종목이 전략 대상이면 내부 상태 업데이트 (단순화: 1차 매수 상태로 가정)
            if h['ticker'] == TICKER1 or h['ticker'] == TICKER2:
                if not self.trader.position:
                   self.trader.position = {
                       'ticker': h['ticker'],
                       'qty': h['qty'],
                       'avg_price': h['avg_price'],
                       'count': 1,
                       'total_cost': h['qty'] * h['avg_price']
                   }
                   logging.info(f"Synced {h['ticker']} position to internal state.")

    def run(self):
        """메인 실행 루프"""
        if not self.fetch_initial_data():
            return
            
        self.sync_position()
        logging.info(f"Starting real-time loop for {self.strategy_name}...")
        
        while True:
            try:
                # 1. 1분 대기 (매 분 5초에 실행하여 데이터 갱신 보장)
                now = datetime.now()
                wait_sec = 65 - now.second if now.second < 60 else 5
                time.sleep(wait_sec)
                
                # 2. 최신 데이터 1분봉 가져오기
                current_dt = datetime.now()
                # US 시장 시간 체크 (23:30 ~ 06:00 KST, 서머타임 변동 가능성 있으나 여기선 단순화)
                # 실 운영 시 현지 시간 모듈이나 라이브러리 권장
                
                # 최신 1분봉 5개 정도 가져와서 마지막 확정된 봉 사용
                latest_df1 = self.provider.fetch_data(TICKER1, "1m", (current_dt - timedelta(days=1)).strftime("%Y-%m-%d"), current_dt.strftime("%Y-%m-%d"))
                latest_df2 = self.provider.fetch_data(TICKER2, "1m", (current_dt - timedelta(days=1)).strftime("%Y-%m-%d"), current_dt.strftime("%Y-%m-%d"))
                
                if latest_df1 is None or latest_df2 is None or latest_df1.empty or latest_df2.empty:
                    continue
                
                # 마지막 유효 행 추출
                p1 = latest_df1.iloc[-1]['close']
                p2 = latest_df2.iloc[-1]['close']
                ts = latest_df1.index[-1]
                
                # 중복 데이터 체크
                if ts == self.df_history['datetime'].iloc[-1]:
                    continue
                
                # 3. 히스토리 업데이트 및 지표 계산
                new_row = pd.DataFrame([{'datetime': ts, 'close_etf1': p1, 'close_etf2': p2}])
                self.df_history = pd.concat([self.df_history, new_row], ignore_index=True).tail(500)
                
                # 지표 계산 (IntradaySpreadTrader 내부 로직 활용)
                df_calc = self.trader.calculate_indicators(self.df_history.copy())
                last_row = df_calc.iloc[-1]
                
                # 4. 전략 판단
                action = None
                detail = None

                # 날짜가 바뀌면 일일 거래 횟수 리셋 (장기 실행 대응)
                today_str = current_dt.strftime('%Y-%m-%d')
                if getattr(self, '_trade_date', None) != today_str:
                    self._trade_date = today_str
                    self.trader.daily_trade_count = 0

                if self.trader.position:
                    action = self.trader.manage_position(last_row, self.trader.position)
                else:
                    # 일일 진입 한도 체크 (모의 버전과 동일한 안전장치 — 시그널 진동 시 무한 재진입 방지)
                    if self.trader.daily_trade_count < self.trader.max_daily_trades:
                        signal_ticker = self.trader.generate_signal(last_row)
                        if signal_ticker:
                            action = "ENTRY"
                            detail = signal_ticker
                
                # 5. 실전 주문 집행
                if action:
                    logging.info(f"Signal Detected: {action} (Detail: {detail}, Z-Score: {last_row['zscore']:.2f})")
                    self.execute_real_trade(last_row, action, detail)
                else:
                    if len(self.df_history) % 10 == 0:
                        logging.info(f"Heartbeat - Z-Score: {last_row['zscore']:.2f}, QQQ: {p1:.2f}, SQQQ: {p2:.2f}")

            except Exception as e:
                logging.error(f"Loop Error: {e}", exc_info=True)
                time.sleep(10)

    def execute_real_trade(self, row, action, detail=None):
        """실제 주문 전송 및 내부 상태 업데이트"""
        dt = row['datetime']
        ticker = detail if action == "ENTRY" else (self.trader.position['ticker'] if self.trader.position else None)
        if not ticker: return
        
        price = row[f'close_etf1'] if ticker == TICKER1 else row[f'close_etf2']
        
        # 주문 수량 계산 로직 (Trader 원본 로직 참조)
        qty = 0
        if action == "ENTRY":
            # 1차 매수 (50%)
            allocation = self.trader.start_cash * self.trader.scaling_ratios[0]
            qty = int(allocation / price)
        elif action == "SCALE_IN":
            # 추가 매수
            count = self.trader.position['count']
            if count < len(self.trader.scaling_ratios):
                ratio = self.trader.scaling_ratios[count]
                allocation = self.trader.start_cash * ratio
                qty = int(allocation / price)
        elif action in ["TAKE_PROFIT", "STOP_LOSS", "MEAN_REVERSION", "FORCE_EXIT", "TRAILING_STOP"]:
            # 전량 매도
            qty = self.trader.position['qty']
            side = "SELL"
        
        if qty <= 0:
            logging.warning(f"Quantity is 0 for {action}. Skipping.")
            return

        side = "BUY" if action in ["ENTRY", "SCALE_IN"] else "SELL"
        
        # --- [실제 KIS 주문 호출] ---
        res = self.broker.order_us(ticker, qty, price, side=side)
        
        if res and res.get("rt_cd") == "0":
            # 성공 시 내부 상태 업데이트 (Traders' backtest execute_trade logic mimics this)
            # 여기서는 내부 trader 인스턴스의 execute_trade를 호출하여 상태를 유지함
            # 이 때, trader 내부의 execute_trade는 '가정' 하에 동작하므로 실제 체결 시점과 약간의 차이는 있을 수 있음
            self.trader.execute_trade(row, action, detail)
            if action == "ENTRY":
                self.trader.daily_trade_count += 1
            logging.info(f"Real Order Placed Successfully: {side} {ticker} {qty}")
        else:
            logging.error(f"Real Order Failed: {res.get('msg1') if res else 'Unknown Error'}")

if __name__ == "__main__":
    # 전략명 확인 (커맨드라인 인자 등 확장 가능)
    target_strategy = STRATEGY_NAME
    if len(sys.argv) > 1 and sys.argv[1] == "--strategy":
        target_strategy = sys.argv[2]
        
    print(f"=== Starting QQQ/SQQQ Real Trading Engine [{target_strategy}] ===")
    app = RealUSDualTrader(target_strategy)
    app.run()
