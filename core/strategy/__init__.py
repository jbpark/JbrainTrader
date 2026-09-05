import pandas as pd
import logging
from datetime import datetime
from threading import Lock
from core.indicators import (
    calculate_atr, calculate_vwap, calculate_ema, calculate_macd, 
    is_fractal_low, calculate_rsi, calculate_bb, calculate_uptick_ratio
)
import re
import configparser
import io

class TradingStrategy:
    def __init__(self, strategy_manager=None):
        self.positions = {}  # {ticker: [list of purchase objects]} - LIFO 관리를 위함
        self.ohlcv_data = {} # {ticker: dataframe}
        self.lock = Lock()
        self.params = {
            'atr_period': 14,
            'ema_period': 20,
        }
        self.strategy_mgr = strategy_manager
        self.strategy_configs = {} # Cached strategy configs
        self.compiled_rules = {}   # Cached compiled conditions: {rule_name: {section: code_object}}

    def _get_strategy_config(self, rule_name):
        if rule_name in self.strategy_configs:
            return self.strategy_configs[rule_name]
        
        if self.strategy_mgr:
            strat_data = self.strategy_mgr.get_strategy(rule_name)
            if strat_data:
                try:
                    config = configparser.ConfigParser()
                    config.read_string(strat_data['content'])
                    self.strategy_configs[rule_name] = config
                    # 전략 로드 시 규칙 컴파일
                    self._compile_rules(rule_name, config)
                    return config
                except Exception as e:
                    logging.error(f"Error parsing strategy {rule_name}: {e}")
        return None

    def _compile_rules(self, rule_name, config):
        """전략 설정을 파이썬 코드 객체로 사전 컴파일"""
        compiled = {}
        # 컨텍스트 변수들을 파이썬 구문에 맞게 매핑
        # (문자열 치환 대신 실제 지역 변수로 사용할 수 있도록 템플릿화 준비)
        
        for section in config.sections():
            if 'condition' in config[section]:
                condition_str = config.get(section, 'condition').replace('\n', ' ').replace('\r', ' ')

                # 대소문자 구분 없이 처리하기 위해 소문자로 변환 후 컴파일
                # (컨텍스트 변수들은 _evaluate_compiled_condition의 eval 시점에 locals로 주입됨)
                processed_cond = condition_str.lower()
                
                try:
                    # 컴파일된 코드를 저장
                    compiled[section] = compile(processed_cond, '<string>', 'eval')
                except Exception as e:
                    logging.error(f"Failed to compile rule [{section}] in {rule_name}: {e}")
        
        self.compiled_rules[rule_name] = compiled

    def update_data(self, ticker_name, new_row):
        """
        새로운 봉 데이터 추가 및 지표 업데이트
        """
        with self.lock:
            try:
                if ticker_name not in self.ohlcv_data:
                    # columns에 지표들도 포함되도록 확장 (데이터프레임 생성 시)
                    self.ohlcv_data[ticker_name] = pd.DataFrame()
                
                # 중복 제거 및 시간순 정렬
                self.ohlcv_data[ticker_name] = pd.concat([self.ohlcv_data[ticker_name], pd.DataFrame([new_row])]).drop_duplicates('datetime').sort_values('datetime').iloc[-200:]
                df = self.ohlcv_data[ticker_name]
                
                # 지표 계산 (각 지표별 최소 요구 봉 수 확인)
                if len(df) >= 20:
                    df['ema20'] = calculate_ema(df, 20)
                    df['bb_upper'], df['bb_middle'], df['bb_lower'] = calculate_bb(df)
                    
                if len(df) >= 60:
                    df['ema60'] = calculate_ema(df, 60)
                    df['macd'], df['signal'], df['hist'] = calculate_macd(df)
                    df['atr'] = calculate_atr(df, self.params['atr_period'])
                    df['vwap'] = calculate_vwap(df)
                    df['rsi'] = calculate_rsi(df)
            except Exception as e:
                logging.error(f"Strategy update_data error for {ticker_name}: {str(e)}")
            
    # _check_first_buy 메서드는 제거되었습니다. 
    # 전략 파일 시스템을 사용하는 check_buy_signal 메서드(186번째 줄)를 사용하세요.
    # (Note: check_buy_signal is at line 123)

    def get_status_details(self, ticker_name):
        """
        현재 종목의 지표 상태 상세 반환
        """
        with self.lock:
            df = self.ohlcv_data.get(ticker_name)
            if df is None:
                return "데이터 수집 시작 중..."
                
            if len(df) < 60 or 'macd' not in df.columns:
                return f"데이터 수집 중 ({len(df)}/60)... 잠시만 기다려주세요."
                
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            # 포지션 정보 확인
            position_info = ""
            if ticker_name in self.positions and self.positions[ticker_name]:
                total_qty = sum(p.get('qty', 0) for p in self.positions[ticker_name])
                total_cost = sum(p.get('price', 0) * p.get('qty', 0) for p in self.positions[ticker_name])
                avg_price = total_cost / total_qty if total_qty > 0 else 0
                position_info = f" | 보유: {total_qty}주 @ ₩{int(avg_price):,}"
            
            details = (
                f"EMA(20):{curr['ema20']:.1f} {'<' if curr['ema20'] <= curr['ema60'] else '>'} EMA(60):{curr['ema60']:.1f} | "
                f"MACD:{curr['macd']:.2f} {'<' if curr['macd'] <= curr['signal'] else '>'} Sig:{curr['signal']:.2f} | "
                f"Hist:{curr['hist']:.2f} ({'↑' if curr['hist'] > prev['hist'] else '↓'}){position_info}"
            )
            return details

    def get_analysis_data(self, ticker_name):
        """
        현재 종목의 실시간 분석 데이터 반환
        """
        with self.lock:
            df = self.ohlcv_data.get(ticker_name)
            if df is None or len(df) < 1:
                return None
            
            curr = df.iloc[-1]
            
            # 최소한의 데이터라도 반환 (EMA만 있는 경우)
            if 'ema20' in df.columns and 'ema60' in df.columns:
                result = {
                    "ema20": round(float(curr['ema20']), 2) if not pd.isna(curr['ema20']) else 0,
                    "ema60": round(float(curr['ema60']), 2) if not pd.isna(curr['ema60']) else 0,
                    "ema_status": "UP" if (not pd.isna(curr['ema20']) and not pd.isna(curr['ema60']) and curr['ema20'] > curr['ema60']) else "DOWN",
                }
                
                # MACD 데이터가 있으면 추가
                if 'macd' in df.columns and len(df) >= 2:
                    prev = df.iloc[-2]
                    result.update({
                        "macd": round(float(curr['macd']), 3) if not pd.isna(curr['macd']) else 0,
                        "signal": round(float(curr['signal']), 3) if not pd.isna(curr['signal']) else 0,
                        "hist": round(float(curr['hist']), 3) if not pd.isna(curr['hist']) else 0,
                        "prev_hist": round(float(prev['hist']), 3) if not pd.isna(prev['hist']) else 0,
                        "macd_status": "UP" if (not pd.isna(curr['macd']) and not pd.isna(curr['signal']) and curr['macd'] > curr['signal']) else "DOWN",
                        "hist_status": "INCREASE" if (not pd.isna(curr['hist']) and not pd.isna(prev['hist']) and curr['hist'] > prev['hist']) else "DECREASE"
                    })
                else:
                    # MACD 데이터가 아직 없으면 기본값
                    result.update({
                        "macd": 0,
                        "signal": 0,
                        "hist": 0,
                        "prev_hist": 0,
                        "macd_status": "DOWN",
                        "hist_status": "DECREASE"
                    })
                
                return result
            
            return None

    def check_buy_signal(self, ticker_name, rule_name='DEFAULT'):
        """
        매수 알고리즘 구현
        """
        with self.lock:
            df = self.ohlcv_data.get(ticker_name)
            if df is None or len(df) < 2:
                logging.debug(f"[DEBUG] check_buy_signal: {ticker_name} 데이터 부족 (len={len(df) if df is not None else 0})")
                return None

            # Get Strategy Config
            config = self._get_strategy_config(rule_name)
            if not config:
                # If no config found, try to load DEFAULT from file if rule_name is DEFAULT
                if rule_name == 'DEFAULT':
                     # The StrategyManager should have loaded it if it exists.
                     # If not, we can't do anything.
                     logging.warning(f"Strategy config for {rule_name} not found.")
                     return None
                return None

            # Multi-step Buy Logic
            pos_list = self.positions.get(ticker_name, [])
            current_step = len(pos_list) + 1
            
            # 중복 진입 방지
            for pos in pos_list:
                if pos.get('step') == current_step:
                    return None

            max_steps = int(config.get('BUY', 'max_steps', fallback='1'))
            if current_step > max_steps:
                return None

            section = f'BUY_STEP_{current_step}'
            if section in config.sections():
                if self._evaluate_compiled_condition(df, ticker_name, rule_name, section):
                    if config.has_option(section, 'size_expr'):
                        size_expr = config.get(section, 'size_expr')
                        try:
                            size = float(self._evaluate_complex_condition(df, ticker_name, size_expr))
                        except Exception as e:
                            logging.error(f"Error evaluating size_expr '{size_expr}': {e}")
                            size = 0.0
                        if size <= 0:
                            # 평가 실패 시 임의 수량(1주) 매수 대신 신호 자체를 무효화
                            logging.error(f"size_expr '{size_expr}' 평가 결과가 유효하지 않아 매수 신호를 건너뜁니다 (size={size})")
                            return None
                    else:
                        size_str = config.get(section, 'size')
                        size = 1.0 if size_str.lower() == 'all' else float(size_str)
                    return {
                        'type': 'BUY',
                        'step': current_step,
                        'price': df['close'].iloc[-1],
                        'size': size
                    }

            return None

    def _check_default_buy(self, df, ticker_name):
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        if 'macd' not in df.columns: return None
        
        # 이미 포지션이 있으면 기본 전략에서는 추가 매수 안함
        if ticker_name in self.positions and self.positions[ticker_name]:
            return None

        cond1 = curr['ema20'] > curr['ema60']
        cond2 = curr['macd'] > curr['signal']
        cond3 = curr['hist'] > prev['hist']
        
        if cond1 and cond2 and cond3:
            return {'type': 'BUY', 'step': 1, 'price': curr['close']}
        return None

    def _check_custom_buy_simple(self, df, rule_text):
        # 이 메서드는 더 이상 사용되지 않습니다.
        # 전략 파일 시스템을 사용하세요.
        logging.warning(f"_check_custom_buy_simple is deprecated. Use strategy files instead.")
        return None

    def check_sell_signal(self, ticker_name, rule_name='DEFAULT'):
        """
        매도 알고리즘 구현
        """
        with self.lock:
            df = self.ohlcv_data.get(ticker_name)
            if ticker_name not in self.positions or not self.positions[ticker_name] or df is None:
                return None

            curr = df.iloc[-1]
            pos_list = self.positions[ticker_name]
            
            # Get Strategy Config
            config = self._get_strategy_config(rule_name)
            if not config:
                 # The StrategyManager should have loaded it if it exists.
                 # If not, we can't do anything.
                 logging.warning(f"Strategy config for {rule_name} not found (Sell).")
                 return None

            # 1. Stop Loss
            if 'STOP_LOSS' in config.sections():
                if self._evaluate_compiled_condition(df, ticker_name, rule_name, 'STOP_LOSS'):
                    return {'type': 'SELL_ALL', 'reason': 'STOP_LOSS'}

            # 2. Time Stop
            if 'TIME_STOP' in config.sections():
                if config.getboolean('TIME_STOP', 'enabled', fallback=False):
                    max_min = int(config.get('TIME_STOP', 'max_minutes', fallback='10'))
                    first_buy_time = pos_list[0].get('time')
                    if first_buy_time:
                        elapsed = (datetime.now() - first_buy_time).total_seconds() / 60
                        if elapsed >= max_min:
                            return {'type': 'SELL_ALL', 'reason': 'TIME_STOP'}

            # 3. Multi-step Sell
            # We assume sell steps are checked sequentially or based on condition
            # For simplicity, we check them in order. If one matches, we return.
            max_sell_steps = int(config.get('SELL', 'max_steps', fallback='1'))
            for i in range(1, max_sell_steps + 1):
                section = f'SELL_STEP_{i}'
                if section in config.sections():
                    # We might need to track which sell steps have already been executed
                    # But the requirement is simple: if condition matches, sell 'size'.
                    # LIFO will be handled by the executor.
                    size_str = config.get(section, 'size')

                    if self._evaluate_compiled_condition(df, ticker_name, rule_name, section):
                        # size=all 은 전량 청산이므로 실행기들이 공통 처리하는 SELL_ALL 타입으로 반환
                        if size_str.lower() == 'all':
                            return {
                                'type': 'SELL_ALL',
                                'step': i,
                                'price': curr['close'],
                                'reason': f'SELL_STEP_{i}'
                            }
                        return {
                            'type': 'SELL',
                            'step': i,
                            'price': curr['close'],
                            'size': float(size_str)
                        }

            return None

    def _check_default_sell_logic(self, df, ticker_name):
        curr = df.iloc[-1]
        atr = curr.get('atr', 0)
        pos_list = self.positions[ticker_name]
        last_buy_price = pos_list[-1]['price']
        diff = curr['close'] - last_buy_price

        # 1. 구조 붕괴 (-1.2 ATR) 전량 청산
        if atr > 0 and curr['close'] <= pos_list[0]['price'] - 1.2 * atr:
            return {'type': 'SELL_ALL', 'reason': 'STRUCTURAL_BREAK'}

        # 2. 하락 흐름 판단
        is_down_trend = (
            curr['close'] < curr.get('ema20', curr['close']) or 
            is_fractal_low(df.iloc[-3:])
        )

        if is_down_trend and atr > 0:
            if diff <= -1.0 * atr:
                return {'type': 'SELL', 'amount_pct': 0.5, 'reason': 'DOWN_TREND_1.0'}
            elif diff <= -0.5 * atr:
                return {'type': 'SELL', 'amount_pct': 0.3, 'reason': 'DOWN_TREND_0.5'}
            
            if 'vwap' in curr and curr['close'] < curr['vwap']:
                return {'type': 'SELL', 'amount_pct': 1.0, 'reason': 'VWAP_BREAK'}

        return None

    def check_overnight_condition(self, ticker):
        """
        익일 보유 허용 조건 검사
        1) 종가 > 당일 VWAP
        2) 종가 > 5분봉 20EMA
        3) 종가가 당일 고점 대비 -0.5 ATR 이내
        """
        df = self.ohlcv_data.get(ticker)
        if df is None: return False
        
        curr = df.iloc[-1]
        day_high = df['high'].max()
        atr = curr['atr']
        
        cond1 = curr['close'] > curr['vwap']
        cond2 = curr['close'] > curr['ema20']
        cond3 = curr['close'] >= day_high - (0.5 * atr)
        
        return cond1 and cond2 and cond3

    def _evaluate_complex_condition(self, df, ticker_name, condition):
        """
        Structured condition evaluation.
        Supported variables: price, ma_5, volume, avg_volume, prev_volume, avg_price
        Supported operators: >, <, >=, <=, ==, and, or
        """
        try:
            if len(df) < 2:
                return False

            # Prepare context
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            # Indicators
            ma_5 = df['close'].rolling(5).mean().iloc[-1] if len(df) >= 5 else float('nan')
            avg_volume = df['volume'].rolling(20).mean().iloc[-1] if len(df) >= 20 else float('nan')
            
            pos_list = self.positions.get(ticker_name, [])
            position_qty = sum(p.get('qty', 0) for p in pos_list)
            if pos_list:
                avg_price = sum(p['price'] * p.get('qty', 1) for p in pos_list) / position_qty if position_qty > 0 else 0
                entry_price = avg_price  # 포지션이 있을 때는 평균 진입가
            else:
                avg_price = 0
                entry_price = curr['close']  # 포지션이 없을 때는 현재가
            
            # 진입 후 최고가 계산 (df는 최근 200봉만 유지하므로 포지션에 누적 기록하여 이력 보존)
            highest_price = 0
            if pos_list and len(df) > 0:
                highest_price = pos_list[0].get('highest_price', 0)
                first_buy_time = pos_list[0].get('time')
                if first_buy_time:
                    # first_buy_time 이후의 고가 중 최대값
                    mask = df['datetime'] >= first_buy_time
                    if mask.any():
                        highest_price = max(highest_price, float(df.loc[mask, 'high'].max()))
                pos_list[0]['highest_price'] = highest_price
            
            # 티커에 따른 시장 특성 정의 (US vs KR)
            is_us = not str(ticker_name).split('.')[0].isdigit()
            
            # 장 종료 시간 확인 (KR: 15:20, US: 15:50 이후) - 빽테스트를 위해 데이터의 시간을 사용
            now = curr['datetime'] if 'datetime' in curr else datetime.now()
            if is_us:
                is_market_close = now.hour > 15 or (now.hour == 15 and now.minute >= 50)
                tick_size = 0.01 # 미국 주식 기본 틱 사이즈 (센트)
            else:
                is_market_close = now.hour > 15 or (now.hour == 15 and now.minute >= 20)
                tick_size = 50 # 한국 주식 기본 틱 사이즈 (가변적이지만 기본값)

            # Fractal Low (Last 3 candles)
            is_fractal = is_fractal_low(df.iloc[-3:]) if len(df) >= 3 else False

            context = {
                'true': True,
                'false': False,
                'price': curr['close'],
                'prev_price': prev['close'],
                'entry_price': entry_price,
                'tick_size': tick_size,
                'is_market_close': is_market_close,
                'ma_5': ma_5,
                'volume': curr['volume'],
                'avg_volume': avg_volume,
                'prev_volume': prev['volume'],
                'avg_price': avg_price,
                'ema20': curr.get('ema20', float('nan')),
                'ema60': curr.get('ema60', float('nan')),
                'macd': curr.get('macd', float('nan')),
                'signal': curr.get('signal', float('nan')),
                'hist': curr.get('hist', float('nan')),
                'prev_hist': prev.get('hist', float('nan')),
                'vwap': curr.get('vwap', float('nan')),
                'atr': curr.get('atr', float('nan')),
                'rsi': curr.get('rsi', float('nan')),
                'bb_upper': curr.get('bb_upper', float('nan')),
                'bb_middle': curr.get('bb_middle', float('nan')),
                'bb_lower': curr.get('bb_lower', float('nan')),
                'first_buy_price': pos_list[0]['price'] if pos_list else 0,
                'last_buy_price': pos_list[-1]['price'] if pos_list else 0,
                'highest_price': highest_price,
                'position_qty': position_qty,
                'is_fractal_low': is_fractal
            }
            
            # Replace variables in condition string
            # Handle multi-line conditions from configparser (it keeps newlines)
            eval_str = condition.replace('\n', ' ').replace('\r', ' ').lower()
            
            # Sort context keys by length to prevent partial replacements (e.g. 'avg_price' vs 'price')
            sorted_keys = sorted(context.keys(), key=len, reverse=True)
            for var in sorted_keys:
                eval_str = re.sub(rf'\b{var}\b', str(context[var]), eval_str)
            
            # Safety check: allow only numbers, operators, parenthesises and whitespace
            # Actually, since we replaced words, \w might not be needed except for 'and', 'or', 'not'
            # Let's just use eval but it's risky in production. 
            # For this task, it's the most flexible way to support arbitrary conditions.
            
            # Define nan and inf for eval to avoid NameError
            eval_globals = {
                "__builtins__": {},
                "nan": float('nan'),
                "inf": float('inf'),
                "true": True,
                "false": False
            }
            
            return eval(eval_str, eval_globals)
        except Exception as e:
            logging.error(f"Error evaluating condition '{condition}': {e}")
            return False

    def _evaluate_compiled_condition(self, df, ticker_name, rule_name, section):
        """사전 컴파일된 코드를 사용하여 고속으로 조건 평가"""
        try:
            if rule_name not in self.compiled_rules or section not in self.compiled_rules[rule_name]:
                return False
            
            code_obj = self.compiled_rules[rule_name][section]
            
            # 데이터 추출
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            # 지표 준비 (rolling 등은 필요할 때만 계산하도록 최적화 가능하지만 일단 context 생성)
            ma_5 = df['close'].rolling(5).mean().iloc[-1] if len(df) >= 5 else float('nan')
            avg_volume = df['volume'].rolling(20).mean().iloc[-1] if len(df) >= 20 else float('nan')
            
            pos_list = self.positions.get(ticker_name, [])
            position_qty = sum(p.get('qty', 0) for p in pos_list)
            if pos_list:
                avg_price = sum(p['price'] * p.get('qty', 1) for p in pos_list) / position_qty if position_qty > 0 else 0
                entry_price = avg_price
            else:
                avg_price = 0
                entry_price = float(curr['close'])
            
            now = curr['datetime'] if 'datetime' in curr else datetime.now()
            hour = now.hour
            minute = now.minute
            
            is_us = not str(ticker_name).split('.')[0].isdigit()
            if is_us:
                is_market_close = hour > 15 or (hour == 15 and minute >= 50)
                tick_size = 0.01
            else:
                is_market_close = hour > 15 or (hour == 15 and minute >= 20)
                tick_size = 50
            is_fractal = is_fractal_low(df.iloc[-3:]) if len(df) >= 3 else False

            # 당일 매수 횟수 계산 (step 1 진입 기준)
            daily_buy_count = 0
            if ticker_name in self.positions:
                # 현재 보유 중인 포지션 중 오늘 진입한 step 1 개수
                today_str = now.strftime('%Y-%m-%d')
                # (참고: 엔진이 종료되지 않았다면 매도 시점에 별도 history에 기록할 수도 있으나, 
                # 현재 구조상 보유 중인 step 정보를 활용하거나 로그/DB 기반으로 확장 가능)
                # 우선은 현재 진입 시도 중인 단계가 1단계라면 이전 기록 유무를 체크하는 식으로 활용


            # 진입 후 최고가 계산 (df는 최근 200봉만 유지하므로 포지션에 누적 기록하여 이력 보존)
            highest_price = 0
            if pos_list and len(df) > 0:
                highest_price = pos_list[0].get('highest_price', 0)
                first_buy_time = pos_list[0].get('time')
                if first_buy_time:
                    # first_buy_time 이후의 고가 중 최대값
                    mask = df['datetime'] >= first_buy_time
                    if mask.any():
                        highest_price = max(highest_price, float(df.loc[mask, 'high'].max()))
                pos_list[0]['highest_price'] = highest_price
            
            uptick_10 = calculate_uptick_ratio(df, 10)

            context = {
                'price': float(curr['close']),
                'prev_price': float(prev['close']),
                'entry_price': float(entry_price),
                'tick_size': tick_size,
                'is_market_close': is_market_close,
                'ma_5': float(ma_5),
                'volume': float(curr['volume']),
                'avg_volume': float(avg_volume),
                'prev_volume': float(prev['volume']),
                'avg_price': float(avg_price),
                'ema20': float(curr.get('ema20', float('nan'))),
                'ema60': float(curr.get('ema60', float('nan'))),
                'macd': float(curr.get('macd', float('nan'))),
                'signal': float(curr.get('signal', float('nan'))),
                'hist': float(curr.get('hist', float('nan'))),
                'prev_hist': float(prev.get('hist', float('nan'))),
                'vwap': float(curr.get('vwap', float('nan'))),
                'atr': float(curr.get('atr', float('nan'))),
                'rsi': float(curr.get('rsi', float('nan'))),
                'bb_upper': float(curr.get('bb_upper', float('nan'))),
                'bb_middle': float(curr.get('bb_middle', float('nan'))),
                'bb_lower': float(curr.get('bb_lower', float('nan'))),
                'first_buy_price': float(pos_list[0]['price'] if pos_list else 0),
                'last_buy_price': float(pos_list[-1]['price'] if pos_list else 0),
                'highest_price': highest_price,
                'uptick_10': uptick_10,
                'hour': hour,
                'minute': minute,
                'daily_buy_count': len(pos_list), # 현재는 현재 포지션 내의 step 수로 대체 (1번 진입 제한용)
                'position_qty': position_qty,
                'is_fractal_low': is_fractal,
                'true': True,
                'false': False
            }
            
            # 컴파일된 객체 실행 (훨씬 빠름)
            return eval(code_obj, {"__builtins__": {}}, context)
            
        except Exception as e:
            logging.error(f"Error in _evaluate_compiled_condition: {e}")
            return False

    def clear_strategy_cache(self, name=None):
        with self.lock:
            if name:
                self.strategy_configs.pop(name, None)
                self.compiled_rules.pop(name, None)
            else:
                self.strategy_configs.clear()
                self.compiled_rules.clear()
