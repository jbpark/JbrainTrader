import pandas as pd
import numpy as np

def calculate_atr(df, period=14):
    """
    ATR (Average True Range) 계산
    """
    high_low = df['high'] - df['low']
    high_cp = np.abs(df['high'] - df['close'].shift())
    low_cp = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def calculate_vwap(df):
    """
    VWAP (Volume Weighted Average Price) 계산
    """
    v = df['volume']
    p = (df['high'] + df['low'] + df['close']) / 3
    
    # volume이 0인 경우 division by zero 방지
    cumsum_v = v.cumsum()
    cumsum_pv = (p * v).cumsum()
    
    # cumsum_v가 0인 경우 NaN 반환
    vwap = cumsum_pv / cumsum_v.replace(0, np.nan)
    return vwap

def calculate_ema(df, period=20):
    """
    EMA (Exponential Moving Average) 계산
    """
    if len(df) < period:
        return pd.Series(index=df.index, dtype='float64')
    return df['close'].ewm(span=period, adjust=False).mean()

def calculate_macd(df, fast=12, slow=26, signal=9):
    """
    MACD (Moving Average Convergence Divergence) 계산
    """
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def is_fractal_low(df):
    """
    프랙탈 저점 여부 확인 (최근 3개 봉 기준)
    - 중앙 봉의 저점이 좌우 봉보다 낮음
    """
    if len(df) < 3:
        return False
    
    prev_low = df['low'].iloc[-3]
    curr_low = df['low'].iloc[-2]
    next_low = df['low'].iloc[-1]
    
    return curr_low < prev_low and curr_low < next_low

def calculate_rsi(df, period=14):
    """
    RSI (Relative Strength Index) 계산
    """
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_bb(df, period=20, std=2):
    """
    Bollinger Bands 계산 (Upper, Middle, Lower)
    """
    middle = df['close'].rolling(window=period).mean()
    std_dev = df['close'].rolling(window=period).std()
    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)
    return upper, middle, lower

def calculate_uptick_ratio(df, period=10):
    """
    최근 n개 봉 중 종가가 상승한 비율 계산
    """
    if len(df) < period + 1:
        return 0
    diff = df['close'].diff()
    upticks = (diff > 0).rolling(window=period).sum()
    return upticks.iloc[-1] / period

def check_trend_failure(highs, fractal_lows):
    """
    하락 흐름 판단 조건:
    1) 5분봉 프랙탈 저점 갱신
    2) 반등 시 직전 고점 돌파 실패 (2회)
    3) 5분봉 종가 < 5분봉 20EMA
    """
    # 이 함수는 전략 클래스에서 지표 데이터를 바탕으로 호출될 예정입니다.
    pass
