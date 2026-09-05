import sys
import os
import argparse
import pandas as pd
import backtrader as bt
import logging
from datetime import datetime

# Add current directory to sys.path to allow imports from core and backend
sys.path.append(os.getcwd())

from core.database import DatabaseManager
from backend.simulator.datafeed import prepare_bt_dataframe, CustomPandasData
from backend.simulator.strategy import ScenarioAwareStrategy
from core.indicators import (
    calculate_atr, calculate_vwap, calculate_ema, calculate_macd, 
    calculate_rsi, calculate_bb
)
from core.strategy.dual.spread_trader import IntradaySpreadTrader
from core.strategy_manager import StrategyManager

# 로깅 설정
def setup_logging(verbose):
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        force=True # 기존 설정 덮어쓰기
    )

# 미국 주식 여부 판별 (티커가 숫자가 아니면 미국 주식)
def is_us_ticker(ticker):
    """티커가 미국 주식인지 판별 (숫자로만 구성 = 한국, 그 외 = 미국)"""
    base = str(ticker).split('.')[0]
    return not base.isdigit()

# Kiwoom Commission Logic (한국 주식)
class KiwoomCommInfo(bt.CommInfoBase):
    params = (
        ('stocklike', True),
        ('commtype', bt.CommInfoBase.COMM_PERC),
        ('commission', 0.00015), # 0.015%
        ('tax', 0.002),          # 0.2%
    )
    def _getcommission(self, size, price, pseudoexec):
        if size > 0: # Buy
            return size * price * self.p.commission
        # Sell
        return abs(size) * price * (self.p.commission + self.p.tax)

# US Stock Commission Logic (미국 주식 - 한국투자증권 기준)
class USStockCommInfo(bt.CommInfoBase):
    params = (
        ('stocklike', True),
        ('commtype', bt.CommInfoBase.COMM_PERC),
        ('commission', 0.0025),   # 한투 온라인 수수료 0.25% (매수/매도 동일)
        ('sec_fee_rate', 0.0000278),  # SEC Fee: 매도 대금의 0.00278%
        ('taf_per_share', 0.000166),  # TAF: 주당 $0.000166
        ('taf_max', 8.30),            # TAF 최대 $8.30
    )
    def _getcommission(self, size, price, pseudoexec):
        qty = abs(size)
        total = qty * price
        
        # 매수 수수료: 한투 수수료만
        kis_fee = total * self.p.commission
        
        if size > 0:  # Buy
            return kis_fee
        
        # 매도 수수료: 한투 수수료 + SEC Fee + TAF
        sec_fee = total * self.p.sec_fee_rate
        taf = min(qty * self.p.taf_per_share, self.p.taf_max)
        return kis_fee + sec_fee + taf


def precalculate_indicators(df):
    """모든 지표를 한 번에 계산하여 DataFrame에 추가 (속도 최적화)"""
    if df.empty: return df
    
    # 지표 계산에 필요한 최소 데이터 수 확인
    if len(df) < 60:
        return df

    # OHLCV 기반 지표 계산
    df['ema20'] = calculate_ema(df, 20)
    df['ema60'] = calculate_ema(df, 60)
    df['macd'], df['signal'], df['hist'] = calculate_macd(df)
    df['atr'] = calculate_atr(df, 14)
    df['vwap'] = calculate_vwap(df)
    df['rsi'] = calculate_rsi(df)
    df['bb_upper'], df['bb_middle'], df['bb_lower'] = calculate_bb(df)
    
    # NaN 값은 0으로 채움 (Backtrader 오류 방지)
    df.fillna(0, inplace=True)
    return df

def run_backtest(ticker_query, strategy_name, start_date, end_date, verbose=False, threshold=None, cash=None):
    setup_logging(verbose)
    
    # 1. Database Connection
    db = DatabaseManager()
    
    # 2. Dual Ticker Check
    if "," in ticker_query:
        tickers = [t.strip() for t in ticker_query.split(",")]
        if len(tickers) == 2:
            if not start_date or not end_date:
                return run_multi_day_backtest(ticker_query, strategy_name, verbose, threshold, cash)
            return run_dual_backtest(tickers[0], tickers[1], strategy_name, start_date, end_date, verbose, threshold, cash)
    
    # 3. Handle Multi-day (Single Ticker)
    if not start_date or not end_date:
        return run_multi_day_backtest(ticker_query, strategy_name, verbose, threshold, cash)

    # 4. Resolve Ticker (Original)
    if not verbose: print(f"[*] 종목 조회 중: {ticker_query}...", end="\r")
    ticker = db.resolve_ticker(ticker_query)
    
    if not ticker:
        print(f"\n[!] 오류: '{ticker_query}'에 해당하는 종목을 찾을 수 없습니다.")
        return

    print(f"\n[*] 백테스트 시작: {ticker} ({ticker_query}), 전략={strategy_name}, 기간={start_date} ~ {end_date}")
    
    # 3. Fetch Data
    if not verbose: print(f"[*] DB에서 데이터 조회 중...", end="\r")
    df = db.get_tick_data_df_range(ticker, start_date, end_date)
    
    if df.empty:
        print(f"\n[!] 오류: 해당 기간({start_date} ~ {end_date})에 대한 {ticker}의 틱 데이터가 DB에 없습니다.")
        return

    if verbose: print(f"[*] 로드된 틱 데이터: {len(df):,} 건")
    
    # 4. Prepare Data for Backtrader (먼저 컬럼 매핑)
    if not verbose: print(f"[*] 데이터 포맷 변환 중...", end="\r")
    bt_df = prepare_bt_dataframe(df.copy())
    
    # 5. Pre-calculate Indicators (속도 최적화의 핵심)
    if not verbose: print(f"[*] 지표 사전 계산 중...", end="\r")
    bt_df = precalculate_indicators(bt_df)
    
    # 6. Setup Cerebro

    cerebro = bt.Cerebro(stdstats=False)
    
    # Add strategy
    cerebro.addstrategy(ScenarioAwareStrategy, strategy_name=strategy_name, ticker_name=ticker, printlog=verbose)
    
    # Add data feed
    data = CustomPandasData(dataname=bt_df)
    cerebro.adddata(data)
    
    # 미국 주식 여부 판별
    is_us = is_us_ticker(ticker)
    
    # Initial Cash (미국 주식은 USD 기준)
    start_cash = 100000.0 if is_us else 10000000.0
    cerebro.broker.setcash(start_cash)
    
    # 수수료 체계 적용 (미국 주식 vs 한국 주식)
    if is_us:
        cerebro.broker.addcommissioninfo(USStockCommInfo())
    else:
        cerebro.broker.addcommissioninfo(KiwoomCommInfo())
    
    # Analyzers
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='ta')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='dd')
    
    currency = "USD" if is_us else "원"
    if verbose:
        print(f"[*] 초기 자산: {start_cash:,.2f}{currency}")
        if is_us:
            print(f"[*] 수수료 체계: 미국 주식 (한투 {USStockCommInfo.params[2][1]*100:.2f}% + SEC Fee + TAF)")
        print(f"[*] 시뮬레이션 실행 중...")
    else:
        print(f"[*] 시뮬레이션 실행 중...", end="\r")
    
    try:
        start_time = datetime.now()
        results = cerebro.run()
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        if not results:
            print("\n[!] 오류: 시뮬레이션 결과가 없습니다.")
            return
            
        strat = results[0]
        final_value = cerebro.broker.getvalue()
        pnl = final_value - start_cash
        pnl_rate = (final_value / start_cash - 1) * 100
        
        ta = strat.analyzers.ta.get_analysis()
        dd = strat.analyzers.dd.get_analysis()
        
        total_trades = ta.total.total if 'total' in ta else 0
        max_dd = dd.max.drawdown if 'max' in dd else 0
        
        print("\n" + "="*50)
        if is_us:
            print("    백테스트 결과 요약 (US Stock Backtest)")
        else:
            print("          백테스트 결과 요약 (Backtest Summary)")
        print("="*50)
        print(f" 종목 정보 (Ticker)    : {ticker} ({ticker_query})")
        print(f" 적용 전략 (Strategy)  : {strategy_name}")
        print(f" 분석 기간 (Period)    : {start_date} ~ {end_date}")
        print(f" 실행 시간 (Duration)  : {duration:.2f}초")
        if is_us:
            print(f" 수수료 체계           : 미국 주식 (한투 수수료 + SEC + TAF)")
        print("-" * 50)
        print(f" 초기 자산 (Start Cash) : {start_cash:>15,.2f}{currency}")
        print(f" 최종 자산 (Final Value): {final_value:>15,.2f}{currency}")
        print(f" 실현 수익 (PnL)       : {pnl:>15,.2f}{currency} ({pnl_rate:.2f}%)")
        print(f" 최대 낙폭 (Max DD)    : {max_dd:>15.2f}%")
        print(f" 총 매매 횟수 (Trades) : {total_trades:>15}")
        print("="*50 + "\n")
        
        return {
            "pnl": pnl,
            "pnl_rate": pnl_rate,
            "trades": total_trades,
            "max_dd": max_dd
        }
        
    except Exception as e:
        print(f"\n[!] 시뮬레이션 실행 중 오류 발생: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return None

def run_dual_backtest(t1, t2, strategy_name, start_date, end_date, verbose=False, threshold=None, cash=None):
    """인트라데이 스프레드 전략 백테스트 실행 (듀얼 ETF 전용)"""
    db = DatabaseManager()
    sm = StrategyManager()
    
    # Resolve Tickers
    ticker1 = db.resolve_ticker(t1)
    ticker2 = db.resolve_ticker(t2)
    
    if not ticker1 or not ticker2:
        print(f"\n[!] 오류: 종목을 찾을 수 없습니다. ({t1}, {t2})")
        return

    # 전략 이름에 'dual/'가 포함되어 있지 않으면 추가 (관례)
    actual_strategy_name = strategy_name
    if not strategy_name.startswith("dual/"):
        actual_strategy_name = f"dual/{strategy_name}"

    print(f"\n[*] 듀얼 백테스트 시작: {ticker1} vs {ticker2}, 전략={actual_strategy_name}, 기간={start_date} ~ {end_date}")
    
    # IntradaySpreadTrader 초기화
    trader = IntradaySpreadTrader(
        ticker1=ticker1,
        ticker2=ticker2,
        strategy_mgr=sm,
        strategy_name=actual_strategy_name
    )
    
    # Overrides
    if threshold is not None:
        trader.threshold = threshold
        print(f"[*] 임계값 강제 적용: {threshold:.2f}")
    if cash is not None:
        trader.start_cash = cash
        trader.cash = cash
        print(f"[*] 매수금액 강제 적용: {cash:,.0f}")
    
    # 기간(Range)에 대해 한 번에 실행 (교차일 US 세션 지원)
    result = trader.backtest(db, start_date, end_date)
    
    if result["status"] != "SUCCESS":
        print(f"\n[!] 오류: {result['message']}")
        return

    m = result["metrics"]
    if verbose:
        for log in result["logs"]:
            print(f"  {log}")

    # 최종 요약
    final_pnl_rate = m["pnl_rate"]
    win_rate = m["win_rate"]
    total_pnl = m["pnl"]
    total_trades = m["trade_count"]
    
    currency = "USD" if trader.is_us else "원"
    
    print("\n" + "="*50)
    print("    듀얼 백테스트 결과 요약 (Dual Strategy Summary)")
    print("="*50)
    print(f" 종목 1 (Ticker 1)   : {ticker1}")
    print(f" 종목 2 (Ticker 2)   : {ticker2}")
    print(f" 적용 전략 (Strategy) : {actual_strategy_name}")
    print(f" 분석 기간 (Period)   : {start_date} ~ {end_date}")
    print("-" * 50)
    print(f" 시작 자산 (Start)    : {trader.start_cash:>15,.2f}{currency}")
    print(f" 실현 수익 (PnL)      : {total_pnl:>15,.2f}{currency} ({final_pnl_rate:.2f}%)")
    print(f" 총 매매 횟수 (Trades): {total_trades:>15}")
    print(f" 승률 (Win Rate)      : {win_rate:>15.2f}%")
    print("="*50 + "\n")

    return {
        "pnl": total_pnl,
        "pnl_rate": final_pnl_rate,
        "trades": total_trades,
        "win_rate": win_rate
    }

def run_multi_day_backtest(ticker_query, strategy_name, verbose=False, threshold=None, cash=None):
    """DB에 데이터가 있는 모든 날짜를 자동으로 찾아서 백테스트 실행"""
    db = DatabaseManager()
    is_dual = "," in ticker_query
    tickers = [t.strip() for t in ticker_query.split(",")] if is_dual else [ticker_query]
    
    # 테커 해결
    resolved_tickers = []
    for t in tickers:
        rt = db.resolve_ticker(t)
        if not rt:
            print(f"[!] 오류: 종목을 찾을 수 없습니다: {t}")
            return
        resolved_tickers.append(rt)
    
    # 인격별 인터벌 결정 (Dual=1m, Single=tick)
    interval = '1m' if is_dual else 'tick'
    
    # 공통 날짜 찾기
    all_dates_sets = []
    for rt in resolved_tickers:
        norm_t = db.normalize_ticker(rt)
        dates = db.get_collected_dates(norm_t, interval, '2020-01-01', '2030-12-31')
        all_dates_sets.append(set(dates))
    
    if not all_dates_sets:
        print(f"[!] 오류: 데이터를 찾을 수 없습니다.")
        return

    common_dates = sorted(list(set.intersection(*all_dates_sets)))
    
    if not common_dates:
        print(f"[!] 오류: 모든 종목의 데이터가 공통으로 존재하는 날짜가 없습니다.")
        return

    print(f"[*] 총 {len(common_dates)}일의 데이터를 발견했습니다. ({common_dates[0]} ~ {common_dates[-1]})")
    
    results = []
    for date in common_dates:
        # 개별 날짜 테스트 시에는 상세 로그가 너무 많을 수 있으므로 verbose가 아니면 출력을 제한하고 싶지만,
        # 기존 함수들이 print를 포함하고 있으므로 그대로 실행합니다.
        if is_dual:
            res = run_dual_backtest(tickers[0], tickers[1], strategy_name, date, date, verbose, threshold, cash)
        else:
            res = run_backtest(ticker_query, strategy_name, date, date, verbose, threshold, cash)
        
        if res:
            res['date'] = date
            results.append(res)
    
    if not results:
        print("[!] 모든 날짜의 테스트가 실패했습니다.")
        return

    # 종합 결과 출력
    print("\n" + "!"*50)
    print(f"      종합 백테스트 결과 ({len(results)}일)")
    print("!"*50)
    
    total_pnl_rate = 0
    win_days = 0
    total_trades = 0
    
    print(f"{'날짜 (Date)':<12} | {'수익률 (PnL)':<12} | {'매매횟수':<5}")
    print("-" * 40)
    for r in results:
        pnl_str = f"{r['pnl_rate']:>10.2f}%"
        print(f"{r['date']:<12} | {pnl_str:<12} | {r['trades']:>5}")
        total_pnl_rate += r['pnl_rate']
        total_trades += r['trades']
        if r['pnl_rate'] > 0:
            win_days += 1
            
    avg_pnl_rate = total_pnl_rate / len(results)
    day_win_rate = (win_days / len(results)) * 100
    
    print("-" * 40)
    print(f"전체 평균 수익률 : {avg_pnl_rate:>10.2f}%")
    print(f"일별 승률 (Win)  : {day_win_rate:>10.2f}% ({win_days}/{len(results)})")
    print(f"총 매매 횟수     : {total_trades:>10}")
    print("!"*50 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="백테스트 콘솔 실행 스크립트")
    parser.add_argument("--ticker", required=True, help="종목 코드 또는 이름 (예: 005930, 삼성전자)")
    parser.add_argument("--strategy", required=True, help="전략 이름 (예: DEFAULT, SCALP_01 등)")
    parser.add_argument("--start", help="시작 날짜 (YYYY-MM-DD)")
    parser.add_argument("--end", help="종료 날짜 (YYYY-MM-DD)")
    parser.add_argument("--threshold", type=float, help="임계값 (Z-Score) 강제 적용")
    parser.add_argument("--cash", "--start_cash", type=float, help="시작 자산 강제 적용")
    parser.add_argument("-v", "--verbose", action="store_true", help="상세 로그 출력")
    
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
        
    args = parser.parse_args()
    
    run_backtest(
        args.ticker, 
        args.strategy, 
        args.start, 
        args.end, 
        verbose=args.verbose, 
        threshold=args.threshold, 
        cash=args.cash
    )

