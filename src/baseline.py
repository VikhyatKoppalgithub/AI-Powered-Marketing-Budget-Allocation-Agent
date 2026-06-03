"""
Baseline comparisons for optimization lift
Owner: Meghna Advani
"""
from __future__ import annotations

import pandas as pd


def compute_historical_baseline(df: pd.DataFrame, channels: list[str]) -> dict:
    """Historical average allocation."""
    pass


def compute_equal_baseline(budget: float, channels: list[str]) -> dict:
    """Equal split baseline."""
    pass


def compute_lift(optimized: dict, baseline: dict, params: dict) -> dict:
    """Lift vs baseline."""
    pass


def run_all_baselines(config_path: str = "config.yaml") -> dict:
    """Run all baseline computations."""
    pass
