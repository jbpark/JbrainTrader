import backtrader as bt
import pandas as pd

SCENARIO_MAP = {
    'UPTREND': 1,
    'DOWNTREND': 2,
    'SIDEWAYS': 3,
    'VOLATILE': 4,
    'FLASH_CRASH': 5
}

class CustomPandasData(bt.feeds.PandasData):
    """
    틱 단위 데이터를 Backtrader에서 사용하기 위한 커스텀 데이터 피드.
    지표들을 추가 라인으로 포함하여 속도를 최적화합니다.
    """
    lines = ('scenario', 'ema20', 'ema60', 'macd', 'signal', 'hist', 'atr', 'vwap', 'rsi', 'bb_upper', 'bb_middle', 'bb_lower')
    params = (
        ('datetime', None),
        ('open', -1),
        ('high', -1),
        ('low', -1),
        ('close', 'price'),
        ('volume', 'volume'),
        ('openinterest', -1),
        ('scenario', 'scenario'),
        ('ema20', 'ema20'),
        ('ema60', 'ema60'),
        ('macd', 'macd'),
        ('signal', 'signal'),
        ('hist', 'hist'),
        ('atr', 'atr'),
        ('vwap', 'vwap'),
        ('rsi', 'rsi'),
        ('bb_upper', 'bb_upper'),
        ('bb_middle', 'bb_middle'),
        ('bb_lower', 'bb_lower'),
    )

def prepare_bt_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tick DataFrame을 Backtrader PandasData에 적합한 포맷으로 변환합니다.
    """
    # ts(datetime)를 index로 변환
    if 'ts' in df.columns:
        df['datetime'] = pd.to_datetime(df['ts'])
        df.set_index('datetime', inplace=True)
    
    # OHLC 및 기타 필수 컬럼 생성 (이미 존재하는 경우 유지)
    if 'open' not in df.columns: df['open'] = df['price']
    if 'high' not in df.columns: df['high'] = df['price']
    if 'low' not in df.columns: df['low'] = df['price']
    if 'close' not in df.columns: df['close'] = df['price']
    if 'openinterest' not in df.columns: df['openinterest'] = 0
    
    # Scenario 문자열을 정수로 변환 (Backtrader Line 전용)
    if 'scenario' in df.columns and df['scenario'].dtype == object:
        df['scenario'] = df['scenario'].map(SCENARIO_MAP).fillna(0)
    
    # 지표 컬럼들이 없는 경우 0으로 채움 (오류 방지)
    indicator_cols = ['ema20', 'ema60', 'macd', 'signal', 'hist', 'atr', 'vwap', 'rsi', 'bb_upper', 'bb_middle', 'bb_lower']
    for col in indicator_cols:
        if col not in df.columns:
            df[col] = 0.0
    
    return df

