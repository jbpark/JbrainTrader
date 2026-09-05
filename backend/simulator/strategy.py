import backtrader as bt

class ScenarioAwareStrategy(bt.Strategy):
    """
    시나리오별로 다른 단타 전략을 적용하는 샘플 전략.
    """
    params = (
        ('printlog', True),
        ('strategy_name', 'SCENARIO_DEFAULT'),
        ('ticker_name', 'SIM'),
    )

    def log(self, txt, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.datetime(0)
            print(f'{dt.isoformat()}, {txt}')

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.datascenario = self.datas[0].scenario
        self.order = None
        self.trade_history = [] 
        self.buy_steps = [] # Track martingale scale steps
        
        # Integration with custom rules
        from core.strategy import TradingStrategy
        from core.strategy_manager import StrategyManager
        import os
        # Find project root (three levels up: simulator -> backend -> root)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.custom_strategy = TradingStrategy(strategy_manager=StrategyManager(base_dir=project_root))
        self.rule_name = self.params.strategy_name
        self.ticker_name = self.params.ticker_name
        self.pnl_history = [] # Track total value for comparison charts

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            marker = 'B' if order.isbuy() else 'S'
            self.trade_history.append({
                'time': bt.num2date(order.executed.dt).timestamp() * 1000,
                'price': order.executed.price,
                'marker': marker,
                'qty': abs(order.executed.size),
                'amount': order.executed.value,
                'pnl': getattr(order, 'pnl', 0) # Simplification
            })
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}, Qty: {order.executed.size}')
                self.buy_steps.append({'price': order.executed.price, 'qty': order.executed.size, 'time': bt.num2date(order.executed.dt)})
            else:
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}, Qty: {order.executed.size}')
                if self.position:
                    # 부분 매도: 매도된 주 수만큼 최근 매수 스텝(LIFO)에서 차감
                    remaining = abs(order.executed.size)
                    while remaining > 0 and self.buy_steps:
                        last_step = self.buy_steps[-1]
                        if last_step['qty'] <= remaining:
                            remaining -= last_step['qty']
                            self.buy_steps.pop()
                        else:
                            last_step['qty'] -= remaining
                            remaining = 0
                else:
                    self.buy_steps = []
        self.order = None

    def get_scenario_name(self) -> str:
        # 정수형으로 저장된 시나리오 코드를 다시 문자열로 매핑하여 반환
        val = int(self.datas[0].scenario[0])
        inv_map = {1: 'UPTREND', 2: 'DOWNTREND', 3: 'SIDEWAYS', 4: 'VOLATILE', 5: 'FLASH_CRASH'}
        return inv_map.get(val, 'UNKNOWN')

    def next(self):
        # Track portfolio value for each tick to create comparison chart
        # 성능을 위해 샘플링 (10틱당 1회 또는 마지막 틱)
        if len(self) % 10 == 0 or len(self) >= len(self.datas[0]) - 1:
            self.pnl_history.append({
                'time': bt.num2date(self.datas[0].datetime[0]).timestamp() * 1000,
                'value': self.broker.getvalue()
            })
        
        scenario = self.get_scenario_name()
        
        if self.order:
            return

        # Use custom strategy rules if provided and not default
        if self.rule_name and self.rule_name != 'SCENARIO_DEFAULT':
            # Update custom strategy with the latest row for evaluation
            now = bt.num2date(self.datas[0].datetime[0])
            
            # 지표들을 포함한 row 생성 (속도 최적화를 위해 이미 계산된 값을 사용)
            row = {
                'datetime': now,
                'open': self.datas[0].open[0],
                'high': self.datas[0].high[0],
                'low': self.datas[0].low[0],
                'close': self.datas[0].close[0],
                'volume': self.datas[0].volume[0],
                # 추가된 지표 라인들
                'ema20': self.datas[0].ema20[0],
                'ema60': self.datas[0].ema60[0],
                'macd': self.datas[0].macd[0],
                'signal': self.datas[0].signal[0],
                'hist': self.datas[0].hist[0],
                'atr': self.datas[0].atr[0],
                'vwap': self.datas[0].vwap[0],
                'rsi': self.datas[0].rsi[0],
                'bb_upper': self.datas[0].bb_upper[0],
                'bb_middle': self.datas[0].bb_middle[0],
                'bb_lower': self.datas[0].bb_lower[0]
            }
            # Update data for the actual ticker
            ticker = self.ticker_name
            self.custom_strategy.update_data(ticker, row)
            
            # Sync positions from Backtrader to TradingStrategy for condition evaluation
            if self.position:
                if not self.buy_steps:
                    self.buy_steps = [{'price': self.position.price, 'qty': self.position.size, 'time': now}]
                self.custom_strategy.positions[ticker] = self.buy_steps
            else:
                self.buy_steps = []
                self.custom_strategy.positions[ticker] = []

            # Check for signals
            buy_sig = self.custom_strategy.check_buy_signal(ticker, self.rule_name)
            if buy_sig:
                self.log(f'CUSTOM BUY SIGNAL [{self.rule_name}] Step {buy_sig.get("step")} @ {self.dataclose[0]}')
                self.order = self.buy(size=buy_sig.get('size', 1.0))
            else:
                sell_sig = self.custom_strategy.check_sell_signal(ticker, self.rule_name)
                if sell_sig and self.position:
                    self.log(f'CUSTOM SELL SIGNAL [{self.rule_name}] Type {sell_sig.get("type")} @ {self.dataclose[0]}')
                    if sell_sig.get('type') == 'SELL_ALL':
                        self.order = self.close()
                    else:
                        self.order = self.sell(size=sell_sig.get('size', 1.0))
            return


        # Fallback to hardcoded scenario logic
        if scenario == 'UPTREND':
            if not self.position:
                self.log(f'UPTREND -> Scalping BUY, {self.dataclose[0]:.2f}')
                self.order = self.buy()
        
        elif scenario == 'DOWNTREND':
            if self.position:
                self.log(f'DOWNTREND -> EXIT, {self.dataclose[0]:.2f}')
                self.order = self.close()

        elif scenario == 'VOLATILE':
            # Mean Reversion: Buy low, sell high relative to previous tick
            if not self.position and len(self.dataclose) > 1 and self.dataclose[0] < self.dataclose[-1]:
                self.order = self.buy()
            elif self.position and len(self.dataclose) > 1 and self.dataclose[0] > self.dataclose[-1]:
                self.order = self.close()

        elif scenario == 'SIDEWAYS':
            # Trend follow or just alternate for demo
            if not self.position and len(self.dataclose) > 1 and self.dataclose[0] > self.dataclose[-1]:
                self.order = self.buy()
            elif self.position and len(self.dataclose) > 1 and self.dataclose[0] < self.dataclose[-1]:
                self.order = self.close()

        elif scenario == 'FLASH_CRASH':
            if self.position:
                self.log(f'FLASH_CRASH -> Emergency EXIT, {self.dataclose[0]:.2f}')
                self.order = self.close()
