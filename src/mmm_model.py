"""
MMM / Saturation curve fitting
Owner: Gregory Sapp
"""
from __future__ import annotations

import pandas as pd


def saturation_curve(spend: float, a: float, b: float) -> float:
    """Saturation response: a * (1 - exp(-b * spend))."""
    pass


def fit_channel(train_df: pd.DataFrame, channel: str, target: str) -> dict:
    """Fit saturation parameters for one channel."""
    pass


def fit_all_channels(train_df: pd.DataFrame, channels: list[str], target: str) -> dict:
    """Fit all channels and return parameter dict."""
    pass


def export_params(params: dict, output_path: str) -> None:
    """Write channel parameters to JSON."""
    pass


def run_fitting(config_path: str = "config.yaml") -> dict:
    """Run full MMM fitting pipeline."""
    pass


def evaluate_on_test(test_df: pd.DataFrame, params: dict) -> dict:
    """Evaluate fitted model on holdout."""
    pass
