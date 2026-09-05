import backtrader as bt
import pandas as pd

class CustomPandasData(bt.feeds.PandasData):
    """
    Custom PandasData feed for Backtrader that includes a 'scenario' column.
    """
    lines = ('scenario',)
    params = (
        ('scenario', -1),  # Column index (or name) for scenario
    )

def prepare_bt_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepares a tick dataframe for use with Backtrader.
    Converts tick data into a format that Backtrader's PandasData expects.
    Since we are using tick data, we map the price to open, high, low, close.
    """
    bt_df = df.copy()
    
    # Set datetime index
    bt_df['datetime'] = pd.to_datetime(bt_df['ts'])
    bt_df.set_index('datetime', inplace=True)
    
    # Map OHLC to the same price for tick data
    bt_df['open'] = bt_df['price']
    bt_df['high'] = bt_df['price']
    bt_df['low'] = bt_df['price']
    bt_df['close'] = bt_df['price']
    bt_df['openinterest'] = 0
    
    # Ensure columns are in the right order for easier mapping if needed,
    # though PandasData matches by column name if provided.
    cols = ['open', 'high', 'low', 'close', 'volume', 'openinterest', 'scenario']
    return bt_df[cols]
