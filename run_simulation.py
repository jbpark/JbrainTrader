from src.simulator.generator import TickGenerator
from src.simulator.persistence import TickPersistence
from src.simulator.datafeed import prepare_bt_dataframe, CustomPandasData
from src.simulator.strategy import ScenarioAwareStrategy
import backtrader as bt
import os

def run_pipeline():
    print("Step 1: Generating Market Data...")
    generator = TickGenerator(start_price=100000.0, seed=42)
    # Generate 1 hour (3600 seconds) of tick data
    df = generator.generate(duration_seconds=3600)
    print(f"Generated {len(df)} ticks.")
    print(df.head())

    print("\nStep 2: Persisting Data...")
    persistence = TickPersistence(db_path="ticks.db")
    persistence.save_to_db(df)
    persistence.export_to_parquet(df, "ticks.parquet")
    print("Data saved to ticks.db and exported to ticks.parquet")

    print("\nStep 3: Preparing Data for Backtrader...")
    # Map scenario names to numeric values for Backtrader if needed
    # (Though we can use strings if PandasData handles it, usually it wants floats)
    scenario_map = {
        'UPTREND': 1.0,
        'DOWNTREND': 2.0,
        'SIDEWAYS': 3.0,
        'VOLATILE': 4.0,
        'FLASH_CRASH': 5.0
    }
    df['scenario_num'] = df['scenario'].map(scenario_map)
    
    bt_df = prepare_bt_dataframe(df)
    # Correct columns for custom feed
    bt_df = bt_df.drop(columns=['scenario'])
    bt_df = bt_df.rename(columns={'scenario_num': 'scenario'})
    
    print("Data prepared for Backtrader.")
    print(bt_df.head())

    print("\nStep 4: Setting up Backtrader (Cerebro)...")
    cerebro = bt.Cerebro()
    
    # Add strategy
    cerebro.addstrategy(ScenarioAwareStrategy)

    # Create Data Feed
    data = CustomPandasData(dataname=bt_df)
    cerebro.adddata(data)

    # Set broker variables
    cerebro.broker.setcash(10000000.0)
    cerebro.broker.setcommission(commission=0.00015)  # 0.015%
    cerebro.broker.set_slippage_fixed(10)  # Fixed 10 unit slippage for demonstration

    print(f"Initial Portfolio Value: {cerebro.broker.getvalue():.2f}")

    print("\nStep 5: Running Backtest...")
    cerebro.run()

    print(f"Final Portfolio Value: {cerebro.broker.getvalue():.2f}")

if __name__ == "__main__":
    # Ensure src package exists
    if not os.path.exists("src/simulator/__init__.py"):
        os.makedirs("src/simulator", exist_ok=True)
        with open("src/simulator/__init__.py", "w") as f:
            pass
            
    run_pipeline()
