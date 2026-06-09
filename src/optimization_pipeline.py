"""
Streamlit-agnostic MMM fit + SLSQP orchestration for the app workflow.
Owner: Meghna Advani
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.baseline import apply_baseline_to_result
from src.bo_mmm_tuning import load_bo_params
from src.data_prep import load_config, resolve_project_path
from src.mmm_model import run_fitting
from src.optimizer import OptimResult, solve


def optimizer_fn_for_sensitivity(params: dict, channels: list[str], budget: float) -> dict:
    """Return dict shape expected by explainer.run_sensitivity."""
    result = solve(params, budget, channels)
    return {
        "allocation": result.allocation,
        "predicted_conversions": result.predicted_conversions,
    }


def run_optimization_pipeline(
    *,
    confirmed_budget: float | None = None,
    detected_budget: float | None = None,
    channel_params: dict | None = None,
    train_df: pd.DataFrame | None = None,
) -> tuple[OptimResult, dict[str, Any], float]:
    """Fit MMM (if needed), run SLSQP, attach baseline lift, return result."""
    config = load_config()
    if not channel_params:
        bo_params = load_bo_params(config)
        if bo_params is not None:
            channel_params = bo_params
        else:
            fitting = run_fitting()
            channel_params = fitting["params"]

    channels = list(config["channels"]["modeled"])
    budget = float(
        confirmed_budget
        or detected_budget
        or config["optimization"]["default_budget"]
    )
    optim = solve(channel_params, budget, channels)

    if train_df is None:
        train_path = resolve_project_path(config["data"]["train_path"])
        if Path(train_path).exists():
            train_df = pd.read_csv(train_path)

    if train_df is not None and len(train_df) > 0:
        optim = apply_baseline_to_result(
            optim, channel_params, channels, budget, train_df, config=config
        )

    return optim, channel_params, budget


def apply_optimization_to_session(session_state: Any, optim: OptimResult, channel_params: dict) -> None:
    """Persist optimizer outputs on Streamlit session_state."""
    session_state.channel_params = channel_params
    session_state.optim_result = optim
    session_state.optimizer_fn = optimizer_fn_for_sensitivity
    session_state.optimization_complete = True
    session_state.phase = "explore"
