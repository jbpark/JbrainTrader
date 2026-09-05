import backtrader as bt

class ScenarioAwareStrategy(bt.Strategy):
    """
    A strategy that is aware of the current market scenario.
    """
    params = (
        ('printlog', True),
    )

    def log(self, txt, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.datetime(0)
            print(f'{dt.isoformat()}, {txt}')

    def __init__(self):
        # Keep references to the custom scenario line
        self.scenario = self.datas[0].scenario
        self.dataclose = self.datas[0].close

    def next(self):
        # Get current scenario name (converted from numeric/enum if needed)
        # In our case, scenario names were stored as objects in df,
        # but PandasData often converts everything to floats.
        # We need to handle how scenario is represented.
        
        curr_scenario = self.scenario[0]
        curr_price = self.dataclose[0]
        
        # Log status every 60 steps (seconds) to avoid spamming
        if len(self) % 60 == 0:
            self.log(f'Price: {curr_price:.2f}, Scenario: {curr_scenario}')

        # Example logic: Only buy if in UPTREND and not already in position
        # Note: In a real tick simulation, we would use more complex signals.
        # Here we just demonstrate scenario awareness.
        
        # Since we might have mapped Enum/Name to float, 
        # let's assume ScenarioType handles its own mapping or we just check the line value.
        # For simplicity in this demo, we'll just log and do basic logic if possible.
        
        pass

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            else:
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f'OPERATION PROFIT, GROSS: {trade.pnl:.2f}, NET: {trade.pnlcomm:.2f}')
