from enum import Enum, auto
import random
from dataclasses import dataclass, field
from typing import Dict, List

class ScenarioType(Enum):
    UPTREND = auto()
    DOWNTREND = auto()
    SIDEWAYS = auto()
    VOLATILE = auto()
    FLASH_CRASH = auto()

@dataclass
class ScenarioParams:
    name: str
    drift: float
    volatility: float
    duration_range: tuple[int, int]  # (min_seconds, max_seconds)

class ScenarioManager:
    def __init__(self, initial_scenario: str = "SIDEWAYS"):
        # Default parameters for each scenario
        self.params = {
            ScenarioType.UPTREND: ScenarioParams("UPTREND", 0.0001, 0.0002, (300, 900)),
            ScenarioType.DOWNTREND: ScenarioParams("DOWNTREND", -0.0001, 0.0002, (300, 900)),
            ScenarioType.SIDEWAYS: ScenarioParams("SIDEWAYS", 0.0, 0.0001, (600, 1800)),
            ScenarioType.VOLATILE: ScenarioParams("VOLATILE", 0.0, 0.0005, (120, 300)),
            ScenarioType.FLASH_CRASH: ScenarioParams("FLASH_CRASH", -0.005, 0.002, (30, 60)),
        }
        
        # Transition probabilities (from: {to: prob})
        self.transitions = {
            ScenarioType.UPTREND: {ScenarioType.UPTREND: 0.7, ScenarioType.SIDEWAYS: 0.2, ScenarioType.VOLATILE: 0.1},
            ScenarioType.DOWNTREND: {ScenarioType.DOWNTREND: 0.7, ScenarioType.SIDEWAYS: 0.2, ScenarioType.VOLATILE: 0.1},
            ScenarioType.SIDEWAYS: {ScenarioType.SIDEWAYS: 0.6, ScenarioType.UPTREND: 0.15, ScenarioType.DOWNTREND: 0.15, ScenarioType.VOLATILE: 0.1},
            ScenarioType.VOLATILE: {ScenarioType.VOLATILE: 0.5, ScenarioType.SIDEWAYS: 0.2, ScenarioType.UPTREND: 0.1, ScenarioType.DOWNTREND: 0.1, ScenarioType.FLASH_CRASH: 0.1},
            ScenarioType.FLASH_CRASH: {ScenarioType.SIDEWAYS: 0.5, ScenarioType.VOLATILE: 0.5},
        }
        
        try:
            self.current_scenario = ScenarioType[initial_scenario.upper()]
        except (KeyError, AttributeError):
            self.current_scenario = ScenarioType.SIDEWAYS
            
        self.remaining_duration = random.randint(*self.params[self.current_scenario].duration_range)

    def get_next_scenario(self) -> ScenarioType:
        if self.remaining_duration <= 0:
            probs = self.transitions.get(self.current_scenario, {self.current_scenario: 1.0})
            types = list(probs.keys())
            weights = list(probs.values())
            self.current_scenario = random.choices(types, weights=weights)[0]
            
            p = self.params[self.current_scenario]
            self.remaining_duration = random.randint(*p.duration_range)
            
        return self.current_scenario

    def step(self):
        self.remaining_duration -= 1

    def get_current_params(self) -> ScenarioParams:
        return self.params[self.current_scenario]
