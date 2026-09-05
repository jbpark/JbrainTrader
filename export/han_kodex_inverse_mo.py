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

# 프로젝트 루트 경로 추가 (core 등 모듈 참조 가능하게)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from core.broker.kis import KISBroker
from core.broker.kiwoom import KiwoomBroker
from core.strategy.dual.spread_trader import IntradaySpreadTrader
from core.provider.yahoo import YahooProvider
from core.strategy_manager import StrategyManager

# === [설정] ===
STRATEGY_NAME = "DUAL_200_1X_INVERSE"
TICKER1 = "069500.KS"  # KODEX 200
TICKER2 = "114800.KS"  # KODEX 인버스
LOG_FILE = os.path.join(PROJECT_ROOT, "export", "mock_trading_kodex.log")

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

# === [실행 클래스] ===
class MockDualTrader:
    def __init__(self, strategy_name, server_type="kiwoom"):
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
        
        self.strategy_name = strategy_name

        if server_type == "hankook":
            # 3. KIS 브로커 초기화 (모의 계좌 모드)
            app_key = decrypt_val(os.getenv("KIS_MOCK_APP_KEY"))
            app_secret = decrypt_val(os.getenv("KIS_MOCK_APP_SECRET"))
            acc_no = os.getenv("KIS_MOCK_ACC_NO")
            
            config_path = os.path.join(PROJECT_ROOT, "backend", "settings", "account_config.json")
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        mock_cfg = cfg.get("MOCK", {}).get("kis_config", {})
                        if not app_key: app_key = decrypt_val(mock_cfg.get("app_key"))
                        if not app_secret: app_secret = decrypt_val(mock_cfg.get("app_secret"))
                        if not acc_no: acc_no = mock_cfg.get("acc_no")
                except Exception as e:
                    logging.warning(f"설정 파일 로드 실패: {e}")

            self.broker = KISBroker(key=app_key, secret=app_secret, acc_no=acc_no, is_mock=True)
            if not self.broker.auth():
                logging.error("KIS API 인증 실패. 종료합니다.")
                sys.exit(1)
            logging.info(f"KIS Mock Broker initialized. Account: {self.broker.acc_no}")
        else:
            # 3. Kiwoom 브로커 초기화
            self.broker = KiwoomBroker(is_mock=True)
            if not self.broker.auth():
                logging.error("Kiwoom Gateway 연결 실패. 종료합니다.")
                sys.exit(1)
            logging.info(f"Kiwoom Mock Broker initialized. Account: {self.broker.acc_no}")

        # 4. 전략 매니저 및 전략 데이터 로드
        self.strat_mgr = StrategyManager()
        
        # 5. 내부 인스턴스 (백테스트 로직 재사용)
        self.trader = IntradaySpreadTrader(
            ticker1=TICKER1, ticker2=TICKER2,
            strategy_mgr=self.strat_mgr, strategy_name=strategy_name
        )
        
        # 6. 리포트 초기화 (trader 객체 생성 후 수행)
        self.report_path = None
        self.trade_count = 0
        self.total_pnl = 0.0
        self._init_report()

        # 7. 데이터 제공자
        self.provider = YahooProvider()
        self.df_history = pd.DataFrame()

    def _init_report(self):
        """리포트 파일 초기화 - 전략 요약 섹션 작성"""
        report_dir = os.path.join(PROJECT_ROOT, "report")
        os.makedirs(report_dir, exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"{date_str}_mo_{self.strategy_name}_report.md"
        self.report_path = os.path.join(report_dir, filename)

        t = self.trader
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        header = (
            f"\n---\n\n"
            f"# 모의매매 리포트: {self.strategy_name}\n"
            f"**실행일시**: {now_str}\n\n"
            f"## 전략 요약\n\n"
            f"| 항목 | 값 |\n"
            f"|------|-----|\n"
            f"| 전략명 | {self.strategy_name} |\n"
            f"| 종목1 | KODEX 200 ({TICKER1}) |\n"
            f"| 종목2 | KODEX 인버스 ({TICKER2}) |\n"
            f"| 매수금액 | {t.start_cash:,.0f}원 |\n"
            f"| 임계값(Z) | {t.threshold} |\n"
            f"| 윈도우 | {t.window_size} |\n"
            f"| 목표수익 | {t.target_profit*100:+.2f}% |\n"
            f"| 손절기준 | {t.stop_loss*100:+.2f}% |\n"
            f"| 분할비율 | {', '.join([f'{r*100:.0f}%' for r in t.scaling_ratios])} |\n"
            f"| 최대거래 | {t.max_daily_trades}회/일 |\n"
            f"| 운영시간 | {t.start_time_limit.strftime('%H:%M')} ~ {t.end_time_limit.strftime('%H:%M')} |\n\n"
            f"## 발생한 일\n\n"
        )
        with open(self.report_path, 'a', encoding='utf-8') as f:
            f.write(header)
        logging.info(f"[Report] 리포트 파일: {self.report_path}")

    def _append_report(self, text):
        """리포트 파일에 내용 추가 (append)"""
        if not self.report_path:
            return
        try:
            with open(self.report_path, 'a', encoding='utf-8') as f:
                f.write(text)
        except Exception as e:
            logging.warning(f"[Report] 파일 쓰기 오류: {e}")

    def fetch_initial_data(self):
        """시작 시 최근 데이터를 가져와 지표 웜업"""
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=7) # 주말/연휴 고려하여 7일치로 확대
        
        logging.info(f"Warming up indicators for {TICKER1}, {TICKER2}...")
        
        df1 = self.provider.fetch_data(TICKER1, "1m", start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"))
        df2 = self.provider.fetch_data(TICKER2, "1m", start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"))
        
        if df1 is None or df2 is None or df1.empty or df2.empty:
            logging.error("초기 데이터 수집 실패.")
            return False
            
        # 병합
        df1 = df1.rename(columns={'close': 'close_etf1'})
        df2 = df2.rename(columns={'close': 'close_etf2'})
        
        # 인덱스(datetime) 기준으로 병합
        combined = pd.merge(df1[['close_etf1']], df2[['close_etf2']], left_index=True, right_index=True)
        combined['datetime'] = combined.index
        combined.reset_index(drop=True, inplace=True)
        combined = combined.sort_values('datetime').tail(500) # 지표 계산을 위해 충분한 데이터 유지
        
        self.df_history = combined
        logging.info(f"Warm-up complete. History rows: {len(self.df_history)}")
        return True

    def sync_position(self):
        """실제 계좌 잔고와 내부 포지션 동기화 (단순화)"""
        balance_info = self.broker.get_balance()
        if not balance_info:
            logging.warning("잔고 정보를 가져올 수 없습니다.")
            return
            
        logging.info(f"Balance (KRW): {balance_info['balance']:,}")
        for h in balance_info['holdings']:
            # Yahoo 티커와 KIS 티커(6자리) 일치 확인용 정규화
            kis_ticker = h['ticker']
            target1 = TICKER1.split('.')[0]
            target2 = TICKER2.split('.')[0]
            
            if kis_ticker in [target1, target2]:
                logging.info(f"Holding: {h['ticker']} {h['qty']} shares (@ {h['avg_price']:,.0f})")
                
                # 이미 보유 중인 종목이 전략 대상이면 내부 상태 업데이트 (단순화: 1차 매수 상태로 가정)
                if not self.trader.position:
                   self.trader.position = {
                       'ticker': TICKER1 if kis_ticker == target1 else TICKER2,
                       'qty': h['qty'],
                       'avg_price': h['avg_price'],
                       'count': 1,
                       'total_cost': h['qty'] * h['avg_price']
                   }
                   logging.info(f"Synced {kis_ticker} position to internal state.")

    def run(self):
        """메인 실행 루프"""
        if not self.fetch_initial_data():
            return
            
        self.sync_position()
        logging.info(f"Starting mock-trading loop for {self.strategy_name}...")
        
        first_loop = True
        while True:
            try:
                # 1. 분 단위 데이터 업데이트 대기 (0~5초 대기 후 실행)
                now = datetime.now()
                # 한국 시장 시간 체크 (09:00 ~ 15:40)
                if not (dt_time(9, 0) <= now.time() <= dt_time(15, 40)):
                    if first_loop or (now.minute % 10 == 0 and now.second < 30):
                        start_time = self.trader.start_time_limit.strftime('%H:%M')
                        logging.info(f"현재 장 운영 시간이 아닙니다. (현재: {now.strftime('%H:%M:%S')}, 시작예정: {start_time})")
                        first_loop = False
                    time.sleep(30)
                    continue
                
                first_loop = False

                wait_sec = 62 - now.second if now.second < 60 else 2
                time.sleep(wait_sec)
                
                # 2. 최신 데이터 1분봉 가져오기
                current_dt = datetime.now()
                # 최신 1분봉 가져오기 (Yahoo)
                latest_df1 = self.provider.fetch_data(TICKER1, "1m", (current_dt - timedelta(days=1)).strftime("%Y-%m-%d"), current_dt.strftime("%Y-%m-%d"))
                latest_df2 = self.provider.fetch_data(TICKER2, "1m", (current_dt - timedelta(days=1)).strftime("%Y-%m-%d"), current_dt.strftime("%Y-%m-%d"))
                
                if latest_df1 is None or latest_df2 is None or latest_df1.empty or latest_df2.empty:
                    continue
                
                # 두 데이터프레임 병합하여 시점 맞추기 (데이터 누락 방지)
                latest_df1 = latest_df1.rename(columns={'close': 'close_etf1'})
                latest_df2 = latest_df2.rename(columns={'close': 'close_etf2'})
                
                # 공통된 인덱스(시간)만 남기기 위해 inner join
                common_df = pd.merge(latest_df1[['close_etf1']], latest_df2[['close_etf2']], left_index=True, right_index=True)
                
                if common_df.empty:
                    continue
                
                # 마지막 확정 행 추출
                last_common = common_df.iloc[-1]
                p1 = last_common['close_etf1']
                p2 = last_common['close_etf2']
                ts = common_df.index[-1]
                
                # 중복 데이터 체크
                if not self.df_history.empty and ts == self.df_history['datetime'].iloc[-1]:
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
                today_str = ts.strftime('%Y-%m-%d')
                if getattr(self, '_trade_date', None) != today_str:
                    self._trade_date = today_str
                    self.trader.daily_trade_count = 0

                # 현재 시간 제한 체크 (전략 파일 기준)
                is_active_time = self.trader.start_time_limit <= ts.time() < self.trader.end_time_limit
                
                if self.trader.position:
                    # 강제 청산 시간 도달 여부
                    if ts.time() >= self.trader.end_time_limit:
                        action = "FORCE_EXIT"
                    else:
                        action = self.trader.manage_position(last_row, self.trader.position)
                else:
                    # 신규 진입 체크
                    if is_active_time and self.trader.daily_trade_count < self.trader.max_daily_trades:
                        signal_ticker = self.trader.generate_signal(last_row)
                        if signal_ticker:
                            action = "ENTRY"
                            detail = signal_ticker
                
                # 5. 주문 집행
                if action:
                    logging.info(f"Signal Detected: {action} (Detail: {detail}, Z-Score: {last_row['zscore']:.2f})")
                    self.execute_mock_trade(last_row, action, detail)
                else:
                    if len(self.df_history) % 10 == 0:
                        logging.info(f"Heartbeat - Z-Score: {last_row['zscore']:.2f}, KODEX200: {p1:,.0f}, Inverse: {p2:,.0f}")

            except Exception as e:
                logging.error(f"Loop Error: {e}", exc_info=True)
                time.sleep(10)

    def execute_mock_trade(self, row, action, detail=None):
        """실제 주문 전송 및 내부 상태 업데이트"""
        dt = row['datetime']
        ticker_full = detail if action == "ENTRY" else (self.trader.position['ticker'] if self.trader.position else None)
        if not ticker_full: return

        # KIS용 6자리 티커
        ticker_short = ticker_full.split('.')[0]
        ticker_name = "KODEX 200" if ticker_full == TICKER1 else "KODEX 인버스"

        price = row[f'close_etf1'] if ticker_full == TICKER1 else row[f'close_etf2']

        qty = 0
        if action == "ENTRY":
            # 1차 매수비율 적용
            allocation = self.trader.start_cash * self.trader.scaling_ratios[0]
            qty = int(allocation / price)
        elif action == "SCALE_IN":
            # 추가 매수비율 적용
            count = self.trader.position['count']
            if count < len(self.trader.scaling_ratios):
                ratio = self.trader.scaling_ratios[count]
                allocation = self.trader.start_cash * ratio
                qty = int(allocation / price)
        elif action in ["TAKE_PROFIT", "STOP_LOSS", "MEAN_REVERSION", "FORCE_EXIT", "TRAILING_STOP"]:
            qty = self.trader.position['qty']

        if qty <= 0:
            logging.warning(f"Quantity is 0 for {action}. price={price}, allocation={self.trader.start_cash}. Skipping.")
            return

        side = "BUY" if action in ["ENTRY", "SCALE_IN"] else "SELL"

        # SELL 전에 PnL 미리 계산 (execute_trade 후 position이 초기화되므로)
        pnl_info = None
        if side == "SELL" and self.trader.position:
            pos = self.trader.position
            sell_gross = qty * price
            sell_fee = sell_gross * self.trader.sell_fee_rate
            sell_tax = sell_gross * getattr(self.trader, 'sell_tax_rate', 0.002)
            net_revenue = sell_gross - sell_fee - sell_tax
            pnl = net_revenue - pos['total_cost']
            pnl_rate = (net_revenue / pos['total_cost'] - 1) * 100
            pnl_info = {'pnl': pnl, 'pnl_rate': pnl_rate}

        # --- [KIS 주문 호출] ---
        res = self.broker.order(ticker_short, qty, price, side=side)

        if res and res.get("rt_cd") == "0":
            now_str = datetime.now().strftime('%H:%M:%S')

            # 성공 시 내부 상태 업데이트
            self.trader.execute_trade(row, action, detail)
            logging.info(f"Mock Order Success: {side} {ticker_short} {qty} @ {price:,.0f}")

            if action == "ENTRY":
                self.trader.daily_trade_count += 1
                self._append_report(
                    f"---\n\n"
                    f"**[{now_str}] 신규 진입 (ENTRY)**\n\n"
                    f"- 종목: {ticker_name} ({ticker_short})\n"
                    f"- 수량: {qty}주 @ {price:,.0f}원\n"
                    f"- 매수금액: {qty * price:,.0f}원\n"
                    f"- Z-Score: {row['zscore']:.2f}\n\n"
                )
            elif action == "SCALE_IN":
                self._append_report(
                    f"---\n\n"
                    f"**[{now_str}] 추가 매수 (SCALE_IN)**\n\n"
                    f"- 종목: {ticker_name} ({ticker_short})\n"
                    f"- 수량: {qty}주 @ {price:,.0f}원\n"
                    f"- Z-Score: {row['zscore']:.2f}\n\n"
                )
            elif pnl_info is not None:
                action_labels = {
                    "TAKE_PROFIT": "익절 청산",
                    "STOP_LOSS": "손절 청산",
                    "MEAN_REVERSION": "회귀 청산",
                    "FORCE_EXIT": "강제 청산",
                    "TRAILING_STOP": "트레일링 청산",
                }
                label = action_labels.get(action, action)
                self.trade_count += 1
                self.total_pnl += pnl_info['pnl']
                pnl_str = f"{pnl_info['pnl']:+,.0f}원"
                rate_str = f"{pnl_info['pnl_rate']:+.2f}%"
                cumul_rate = self.total_pnl / self.trader.start_cash * 100

                self._append_report(
                    f"---\n\n"
                    f"**[{now_str}] {label} ({action})**\n\n"
                    f"- 종목: {ticker_name} ({ticker_short})\n"
                    f"- 수량: {qty}주 @ {price:,.0f}원\n"
                    f"- 손익: {pnl_str} (수익률: {rate_str})\n"
                    f"- Z-Score: {row['zscore']:.2f}\n\n"
                    f"## 수익률 요약 ({now_str} 기준)\n\n"
                    f"| 항목 | 값 |\n"
                    f"|------|-----|\n"
                    f"| 완료 거래 | {self.trade_count}회 |\n"
                    f"| 이번 손익 | {pnl_str} ({rate_str}) |\n"
                    f"| 누적 손익 | {self.total_pnl:+,.0f}원 |\n"
                    f"| start_cash 대비 누적 수익률 | {cumul_rate:+.4f}% |\n\n"
                    f"## 발생한 일\n\n"
                )
        else:
            logging.error(f"Mock Order Failed: {res.get('msg1') if res else 'Unknown Error'}")

import socket

def check_singleton(port=9999):
    try:
        # 전역 변수로 선언하여 가비지 컬렉션 방지
        global _lock_socket
        _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _lock_socket.bind(('127.0.0.1', port))
        return True
    except socket.error:
        return False

if __name__ == "__main__":
    if not check_singleton(9876):  # 고유 포트 사용
        print("="*60)
        print(" [오류] 이미 다른 인스턴스가 실행 중입니다.")
        print(" 기존 프로그램을 종료한 뒤 다시 실행해 주세요.")
        print("="*60)
        sys.exit(1)

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", type=str, default="kiwoom", choices=["kiwoom", "hankook"], help="Stock server type")
    args = parser.parse_args()

    app = MockDualTrader(STRATEGY_NAME, server_type=args.server)
    t = app.trader
    
    print("="*60)
    print(f"   KODEX 200/Inverse [MOCK(모의) 계좌] 자동매매 시작")
    print(f"   서버: {args.server.upper()}")
    print(f"   전략명: {STRATEGY_NAME}")
    print(f"   매수금액: {t.start_cash:,.0f}원")
    print(f"   임계값(Z): {t.threshold} | 윈도우: {t.window_size}")
    print(f"   목표수익: {t.target_profit*100:+.2f}% | 손절기준: {t.stop_loss*100:+.2f}%")
    print(f"   운영시간: {t.start_time_limit.strftime('%H:%M')} ~ {t.end_time_limit.strftime('%H:%M')}")
    print(f"   리포트: {app.report_path}")
    print("="*60)
    
    app.run()
