import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from .scenario import ScenarioManager, ScenarioType

class TickGenerator:
    def __init__(self, start_price: float = 100000.0, seed: int = None):
        self.start_price = start_price
        self.current_price = start_price
        if seed is not None:
            np.random.seed(seed)
        self.manager = ScenarioManager()

    def generate(self, duration_seconds: int) -> pd.DataFrame:
        data = []
        base_time = datetime.now()
        
        for i in range(duration_seconds):
            scenario = self.manager.get_next_scenario()
            params = self.manager.get_current_params()
            
            # GBM: dS = mu * S * dt + sigma * S * dW
            # S(t+1) = S(t) * exp((mu - 0.5 * sigma^2) + sigma * epsilon)
            # For 1 second dt = 1
            
            epsilon = np.random.normal(0, 1)
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
