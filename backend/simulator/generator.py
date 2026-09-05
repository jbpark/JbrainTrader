import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from .scenario import ScenarioManager

class TickGenerator:
    def __init__(self, start_price: float = 100000.0, seed: int = None, initial_scenario: str = "SIDEWAYS"):
        self.start_price = start_price
        self.current_price = start_price
        if seed is not None:
            np.random.seed(seed)
        self.manager = ScenarioManager(initial_scenario=initial_scenario)

    def generate(self, duration_seconds: int) -> pd.DataFrame:
        data = []
        # 시작 시간을 당일 09:00:00으로 고정
        now = datetime.now()
        base_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
        
        for i in range(duration_seconds):
            scenario = self.manager.get_next_scenario()
            params = self.manager.get_current_params()
            
            # GBM: dS = mu * S * dt + sigma * S * dW
            # S(t+1) = S(t) * exp((mu - 0.5 * sigma^2) + sigma * epsilon)
            
            epsilon = np.random.normal(0, 1)
            # dt is 1 second
            ret = (params.drift - 0.5 * params.volatility**2) + params.volatility * epsilon
            self.current_price *= np.exp(ret)
            
            # Simulated volume: random value with basic scaling by volatility
            volume = int(np.random.gamma(shape=2, scale=10) * (1 + params.volatility * 1000))
            
            data.append({
                'ts': base_time + timedelta(seconds=i),
                'price': round(self.current_price, 2),
                'volume': max(1, volume),
                'scenario': scenario.name
            })
            
            self.manager.step()
            
        return pd.DataFrame(data)

class ReconstructionGenerator:
    def __init__(self, mode: str = "REALISTIC", density: int = 1, interval: str = "1분"):
        self.mode = mode.upper()
        self.density = density  # ticks per second/minute depending on source
        self.interval = interval

    def generate_from_ohlcv(self, df_ohlcv: pd.DataFrame) -> pd.DataFrame:
        """
        df_ohlcv columns: [ts, open, high, low, close, volume]
        """
        all_ticks = []
        
        for _, row in df_ohlcv.iterrows():
            ticks = self._reconstruct_candle(row)
            all_ticks.extend(ticks)
            
        return pd.DataFrame(all_ticks)

    def _reconstruct_candle(self, row) -> list:
        o, h, l, c = float(row['open']), float(row['high']), float(row['low']), float(row['close'])
        v = float(row['volume'])
        ts = row['ts']
        
        # Determine number of ticks to generate (per candle)
        # Assuming source is 1m, and density 1 -> 60 ticks
        n_ticks = 60 * self.density 
        
        if self.mode == "SIMPLE":
            # O -> H -> L -> C linear path
            path = [o, h, l, c]
            prices = np.interp(np.linspace(0, 3, n_ticks), np.arange(4), path)
            # Add tiny noise (0.01% of price)
            prices += np.random.normal(0, o * 0.0001, n_ticks)
        
        elif self.mode == "PATTERNED":
            # Trend-based: if Bullish, O -> L -> H -> C; if Bearish, O -> H -> L -> C
            path = [o, l, h, c] if c >= o else [o, h, l, c]
            prices = np.interp(np.linspace(0, 3, n_ticks), np.arange(4), path)
            prices += np.random.normal(0, o * 0.0002, n_ticks)
            
        else: # REALISTIC (Random Walk constrained by H/L)
            prices = np.zeros(n_ticks)
            prices[0] = o
            vol = (h - l) / o / np.sqrt(n_ticks) # Rough volatility estimate
            
            for i in range(1, n_ticks - 1):
                # Scale drift towards Close as we approach end
                drift = (c - prices[i-1]) / (n_ticks - i)
                change = drift + np.random.normal(0, o * vol)
                new_price = prices[i-1] + change
                
                # Constrain within H/L
                prices[i] = max(l, min(h, new_price))
            
            prices[-1] = c
            
        # Distribute volume
        vol_per_tick = max(1, int(v / n_ticks))
        
        ticks = []
        for i, p in enumerate(prices):
            ticks.append({
                'ts': ts + timedelta(seconds=i * (60/n_ticks)),
                'price': round(float(p), 2),
                'volume': vol_per_tick,
                'scenario': f"RECON:{self.mode}:{self.interval}"
            })
            
        return ticks
