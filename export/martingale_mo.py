import sys
import os
import time
import logging
import json
from datetime import datetime, time as dt_time, timedelta
import pandas as pd
from cryptography.fernet import Fernet
from dotenv import load_dotenv, find_dotenv

# 프로젝트 루트 경로 추가 (core 등 모듈 참조 가능하게)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from core.broker.kis import KISBroker
from core.broker.kiwoom import KiwoomBroker
from core.strategy import TradingStrategy
from core.strategy_manager import StrategyManager
from core.provider.yahoo import YahooProvider

# === [설정] ===
STRATEGY_NAME = "COMPLEX_MARTINGALE_PYRAMID"
TICKER = "069500.KS"  # KODEX 200 (마틴게일 적용 기본 지수 ETF)
LOG_FILE = os.path.join(PROJECT_ROOT, "export", "mock_trading_martingale.log")
STATE_FILE = os.path.join(PROJECT_ROOT, "export", "martingale_mo_state.json")

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
class MockMartingaleTrader:
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
        self.server_type = server_type

        # 3. 브로커 초기화
        if server_type == "hankook":
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
            self.broker = KiwoomBroker(is_mock=True)
            if not self.broker.auth():
                logging.error("Kiwoom Gateway 연결 실패. 종료합니다.")
                sys.exit(1)
            logging.info(f"Kiwoom Mock Broker initialized. Account: {self.broker.acc_no}")

        # 4. 전략 매니저 및 전략 엔진 로드
        self.strat_mgr = StrategyManager(base_dir=PROJECT_ROOT)
        self.strategy = TradingStrategy(strategy_manager=self.strat_mgr)
        
        # 5. 리포트 초기화
        self.report_path = None
        self.trade_count = 0
        self.total_pnl = 0.0
        self._init_report()

        # 6. 데이터 제공자
        self.provider = YahooProvider()
        self.df_history = pd.DataFrame()

    def _init_report(self):
        """리포트 파일 초기화 - 전략 요약 섹션 작성"""
        report_dir = os.path.join(PROJECT_ROOT, "report")
        os.makedirs(report_dir, exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"{date_str}_mo_{self.strategy_name}_report.md"
        self.report_path = os.path.join(report_dir, filename)

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        header = (
            f"\n---\n\n"
            f"# 모의매매 리포트: {self.strategy_name}\n"
            f"**실행일시**: {now_str}\n\n"
            f"## 전략 요약\n\n"
            f"| 항목 | 값 |\n"
            f"|------|-----|\n"
            f"| 전략명 | {self.strategy_name} |\n"
            f"| 대상종목 | KODEX 200 ({TICKER}) |\n"
            f"| 서버종류 | {self.server_type.upper()} 모의투자 |\n\n"
            f"## 발생한 매매 내역\n\n"
        )
        with open(self.report_path, 'a', encoding='utf-8') as f:
            f.write(header)
        logging.info(f"[Report] 리포트 파일: {self.report_path}")

    def _append_report(self, text):
        if not self.report_path: return
        try:
            with open(self.report_path, 'a', encoding='utf-8') as f:
                f.write(text)
        except Exception as e:
            logging.warning(f"[Report] 파일 쓰기 오류: {e}")

    def _save_positions(self):
        """전략 엔진의 랏 구조(step/매수가/시각/최고가)를 파일로 영속화 (재시작 시 복원용)"""
        try:
            pos_list = self.strategy.positions.get(TICKER, [])
            data = {
                'ticker': TICKER,
                'strategy': self.strategy_name,
                'saved_at': datetime.now().isoformat(),
                'positions': [
                    {
                        'price': p.get('price'),
                        'qty': p.get('qty'),
                        'time': p['time'].isoformat() if isinstance(p.get('time'), datetime) else None,
                        'step': p.get('step', 1),
                        'highest_price': p.get('highest_price', 0),
                    }
                    for p in pos_list
                ]
            }
            with open(STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.warning(f"[State] 포지션 상태 저장 실패: {e}")

    def _load_positions(self):
        """저장된 랏 구조 로드. 파일이 없거나 티커/전략이 현재 설정과 다르면 None"""
        if not os.path.exists(STATE_FILE):
            return None
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get('ticker') != TICKER or data.get('strategy') != self.strategy_name:
                logging.warning("[State] 상태 파일의 티커/전략이 현재 설정과 달라 무시합니다.")
                return None
            positions = []
            for p in data.get('positions', []):
                pos = {
                    'price': float(p.get('price', 0)),
                    'qty': int(p.get('qty', 0)),
                    'step': int(p.get('step', 1)),
                    'time': datetime.fromisoformat(p['time']) if p.get('time') else datetime.now(),
                }
                if p.get('highest_price'):
                    pos['highest_price'] = float(p['highest_price'])
                positions.append(pos)
            return positions or None
        except Exception as e:
            logging.warning(f"[State] 포지션 상태 로드 실패: {e}")
            return None

    @staticmethod
    def _latest_confirmed_row(df, now=None):
        """진행 중인 미완성 봉(현재 분에 속한 봉)을 제외한 마지막 확정봉 행 반환 (없으면 None).

        1분봉의 타임스탬프 T는 T:00~T:59 구간을 커버하므로,
        현재 분(now의 초 절사)보다 앞선 타임스탬프만 확정된 봉이다.
        """
        now = now or datetime.now()
        cutoff = now.replace(second=0, microsecond=0)
        confirmed = df[df['datetime'] < cutoff]
        if confirmed.empty:
            return None
        return confirmed.iloc[-1].to_dict()

    def fetch_initial_data(self):
        """최근 데이터를 가져와 지표 웜업"""
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=7)

        logging.info(f"Warming up indicators for {TICKER}...")
        df = self.provider.fetch_data(TICKER, "1m", start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"))
        if df is None or df.empty:
            logging.error("초기 데이터 수집 실패.")
            return False

        df['datetime'] = df.index
        df.reset_index(drop=True, inplace=True)
        # 진행 중인 미완성 봉 제외 — 웜업에 포함되면 이후 루프의 중복 차단에 걸려
        # 완성본으로 갱신되지 않은 채 남게 됨
        cutoff = datetime.now().replace(second=0, microsecond=0)
        df = df[df['datetime'] < cutoff]
        if df.empty:
            logging.error("확정된 봉이 없어 웜업에 실패했습니다.")
            return False
        df = df.sort_values('datetime').tail(200)
        
        # 엔진에 기존 봉 데이터 미리 흘려서 계산 유도
        for _, row in df.iterrows():
            self.strategy.update_data(TICKER, row.to_dict())
            
        self.df_history = df
        logging.info(f"Warm-up complete. History rows: {len(df)}")
        return True

    def sync_position(self):
        """계좌 잔고와 내부 포지션 동기화 (저장된 랏 구조 우선 복원)"""
        balance_info = self.broker.get_balance()
        if not balance_info:
            logging.warning("잔고 정보를 가져올 수 없습니다.")
            return

        logging.info(f"Balance (KRW): {balance_info['balance']:,}")

        target = TICKER.split('.')[0]
        broker_qty = 0
        broker_avg = 0.0
        for h in balance_info['holdings']:
            if h['ticker'] == target:
                broker_qty = h['qty']
                broker_avg = h['avg_price']
                logging.info(f"Holding: {h['ticker']} {h['qty']} shares (@ {h['avg_price']:,.0f})")

        if broker_qty <= 0:
            # 계좌에 보유분이 없으면 이전 상태 파일은 무효 (외부 매도/청산 등)
            if os.path.exists(STATE_FILE):
                logging.info("계좌에 보유분이 없어 저장된 포지션 상태를 초기화합니다.")
            self.strategy.positions.pop(TICKER, None)
            self._save_positions()
            return

        # 1. 저장된 랏 구조 복원 시도 — step/매수가/최고가 이력이 유지되어야
        #    재시작 후에도 물타기/불타기 단계 판정(position_qty, last_buy_price)이 정상 동작함
        saved = self._load_positions()
        if saved:
            saved_qty = sum(p.get('qty', 0) for p in saved)
            if saved_qty == broker_qty:
                self.strategy.positions[TICKER] = saved
                logging.info(
                    f"저장된 랏 구조 복원: {len(saved)}개 랏 / {saved_qty}주 "
                    f"(마지막 매수가: {saved[-1].get('price', 0):,.0f}, 다음 매수 단계: {len(saved) + 1})"
                )
                return
            logging.warning(
                f"상태 파일 수량({saved_qty})과 계좌 수량({broker_qty})이 불일치하여 단일 랏으로 폴백합니다. "
                f"재시작 전 외부 주문이 있었는지 확인하세요."
            )

        # 2. 폴백: 평단가 기준 단일 랏 (step 이력 소실 — 추가 매수 단계 판정이 왜곡될 수 있음)
        self.strategy.positions[TICKER] = [{
            'price': broker_avg,
            'qty': broker_qty,
            'time': datetime.now(),
            'step': 1
        }]
        self._save_positions()
        logging.info(f"Synced {target} position to strategy engine (single-lot fallback).")

    def run(self):
        """메인 실행 루프"""
        if not self.fetch_initial_data():
            return
            
        self.sync_position()
        logging.info(f"Starting mock-trading loop for {self.strategy_name}...")
        
        first_loop = True
        while True:
            try:
                now = datetime.now()
                # 한국 주식 시장 시간 체크 (09:00 ~ 15:40)
                if not (dt_time(9, 0) <= now.time() <= dt_time(15, 40)):
                    if first_loop or (now.minute % 10 == 0 and now.second < 30):
                        logging.info(f"현재 장 운영 시간이 아닙니다. (현재: {now.strftime('%H:%M:%S')})")
                        first_loop = False
                    time.sleep(30)
                    continue
                
                first_loop = False

                wait_sec = 62 - now.second if now.second < 60 else 2
                time.sleep(wait_sec)
                
                # 데이터 갱신
                current_dt = datetime.now()
                latest_df = self.provider.fetch_data(TICKER, "1m", (current_dt - timedelta(days=1)).strftime("%Y-%m-%d"), current_dt.strftime("%Y-%m-%d"))
                if latest_df is None or latest_df.empty:
                    continue
                
                latest_df['datetime'] = latest_df.index
                latest_df.reset_index(drop=True, inplace=True)

                # 미완성 봉(현재 분) 제외 후 마지막 확정봉만 신호 판정에 사용
                last_row = self._latest_confirmed_row(latest_df)
                if last_row is None:
                    continue
                ts = last_row['datetime']
                
                # 중복 갱신 차단
                if not self.df_history.empty and ts == self.df_history['datetime'].iloc[-1]:
                    continue
                
                self.df_history = pd.concat([self.df_history, pd.DataFrame([last_row])], ignore_index=True).tail(200)
                self.strategy.update_data(TICKER, last_row)
                
                # 신호 판단
                buy_sig = self.strategy.check_buy_signal(TICKER, self.strategy_name)
                if buy_sig:
                    logging.info(f"BUY Signal Detected: {buy_sig}")
                    self.execute_order(last_row, "BUY", buy_sig)
                else:
                    sell_sig = self.strategy.check_sell_signal(TICKER, self.strategy_name)
                    if sell_sig:
                        logging.info(f"SELL Signal Detected: {sell_sig}")
                        self.execute_order(last_row, "SELL", sell_sig)
                    else:
                        if len(self.df_history) % 10 == 0:
                            details = self.strategy.get_status_details(TICKER)
                            logging.info(f"Heartbeat - Price: {last_row['close']:.0f} | {details}")

            except Exception as e:
                logging.error(f"Loop Error: {e}", exc_info=True)
                time.sleep(10)

    def execute_order(self, row, side, signal):
        """실제 모의 주문 실행 및 리포팅"""
        price = float(row['close'])
        ticker_short = TICKER.split('.')[0]
        
        if side == "BUY":
            raw_size = float(signal.get('size', 1))
            qty = int(raw_size)
            if qty != raw_size:
                logging.warning(f"국내 주식은 소수점 주문 불가: size={raw_size} -> {qty}주로 절사")
        else:
            # SELL
            pos_list = self.strategy.positions.get(TICKER, [])
            if not pos_list: return

            if signal.get('type') == 'SELL_ALL':
                qty = sum(p.get('qty', 0) for p in pos_list)
            else:
                qty = int(signal.get('size', 1))

        if qty <= 0:
            logging.warning(f"주문 수량이 0 이하라 건너뜁니다 ({side}, signal={signal})")
            return

        # PnL 미리 산출
        pnl_info = None
        if side == "SELL" and self.strategy.positions.get(TICKER):
            pos_list = self.strategy.positions[TICKER]
            total_qty = sum(p.get('qty', 0) for p in pos_list)
            total_cost = sum(p.get('price', 0) * p.get('qty', 0) for p in pos_list)
            avg_price = total_cost / total_qty if total_qty > 0 else 0
            
            sell_gross = qty * price
            # 수수료율 가정 (매수+매도 0.015% * 2). KODEX 200은 ETF로 증권거래세 면제
            sell_fee = sell_gross * 0.0003
            net_revenue = sell_gross - sell_fee
            
            # 비례 원금 계산
            pro_rata_cost = (qty / total_qty) * total_cost
            pnl = net_revenue - pro_rata_cost
            pnl_rate = (net_revenue / pro_rata_cost - 1) * 100
            pnl_info = {'pnl': pnl, 'pnl_rate': pnl_rate}

        # KIS / Kiwoom API 주문 호출
        res = self.broker.order(ticker_short, qty, price, side=side)
        
        if res and res.get("rt_cd", "0") == "0":
            now_str = datetime.now().strftime('%H:%M:%S')
            logging.info(f"Mock Order Success: {side} {TICKER} {qty} shares @ {price:,.0f}")
            
            # 전략 엔진 포지션 업데이트
            if side == "BUY":
                if TICKER not in self.strategy.positions:
                    self.strategy.positions[TICKER] = []
                self.strategy.positions[TICKER].append({
                    'price': price,
                    'qty': qty,
                    'time': datetime.now(),
                    'step': signal.get('step', 1)
                })
                self._append_report(
                    f"**[{now_str}] 추가 매수 (Step {signal.get('step')})**\n"
                    f"- 수량: {qty}주 @ {price:,.0f}원\n\n"
                )
            else:
                # SELL
                if signal.get('type') == 'SELL_ALL':
                    self.strategy.positions[TICKER] = []
                else:
                    # 매도된 주 수만큼 최근 매수분(LIFO)에서 차감
                    remaining = qty
                    while remaining > 0 and self.strategy.positions[TICKER]:
                        last_pos = self.strategy.positions[TICKER][-1]
                        if last_pos.get('qty', 0) <= remaining:
                            remaining -= last_pos.get('qty', 0)
                            self.strategy.positions[TICKER].pop()
                        else:
                            last_pos['qty'] -= remaining
                            remaining = 0
                            
                if pnl_info is not None:
                    self.trade_count += 1
                    self.total_pnl += pnl_info['pnl']
                    self._append_report(
                        f"**[{now_str}] 포지션 청산 (SELL)**\n"
                        f"- 수량: {qty}주 @ {price:,.0f}원\n"
                        f"- 손익: {pnl_info['pnl']:+,.0f}원 (수익률: {pnl_info['pnl_rate']:+.2f}%)\n"
                        f"- 누적 손익: {self.total_pnl:+,.0f}원\n\n"
                    )

            self._save_positions()
        else:
            logging.error(f"Mock Order Failed: {res.get('msg1') if res else 'Unknown Error'}")

import socket
def check_singleton(port=9999):
    try:
        global _lock_socket
        _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _lock_socket.bind(('127.0.0.1', port))
        return True
    except socket.error:
        return False

if __name__ == "__main__":
    if not check_singleton(9877):
        print(" [오류] 이미 다른 인스턴스가 실행 중입니다.")
        sys.exit(1)

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", type=str, default="kiwoom", choices=["kiwoom", "hankook"], help="Stock server type")
    args = parser.parse_args()

    app = MockMartingaleTrader(STRATEGY_NAME, server_type=args.server)
    
    print("="*60)
    print(f"   3차 최종 마틴게일 복합 전략 [MOCK(모의) 계좌] 자동매매 시작")
    print(f"   대상 종목: {TICKER}")
    print(f"   서버: {args.server.upper()}")
    print(f"   전략명: {STRATEGY_NAME}")
    print(f"   리포트: {app.report_path}")
    print("="*60)
    
    app.run()
