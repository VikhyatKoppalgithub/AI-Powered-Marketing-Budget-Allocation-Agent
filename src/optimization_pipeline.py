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
from src.mmm_model import resolve_mmm_freq, run_fitting
from src.optimizer import (
    ActivationSolveResult,
    OptimResult,
    load_activation_from_config,
    solve,
    solve_with_activation,
)


def load_activation_thresholds(config: dict | None = None) -> dict[str, float]:
    """Load per-channel activation κ (USD/week) from config for Models B/C."""
    thresholds, _ = load_activation_from_config(config)
    return thresholds


def load_activation_ceilings(config: dict | None = None) -> dict[str, float]:
    """Load per-channel activation u_c (USD/week) from config."""
    _, ceilings = load_activation_from_config(config)
    return ceilings


def run_model_b(
    params: dict,
    budget: float,
    channels: list[str],
    config: dict | None = None,
) -> ActivationSolveResult:
    """Model B: activation-threshold enumeration at portfolio budget."""
    cfg = config or load_config()
    thresholds, ceilings = load_activation_from_config(cfg)
    return solve_with_activation(params, budget, channels, thresholds, ceilings)


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
    run_model_b_solve: bool = True,
) -> tuple[OptimResult, dict[str, Any], float, ActivationSolveResult | None]:
    """Fit MMM (if needed), run Model A + optional Model B, attach baseline lift."""
    config = load_config()
    mmm_freq = resolve_mmm_freq(config)
    if not channel_params:
        bo_params = load_bo_params(config)
        if bo_params is not None:
            channel_params = bo_params
        else:
            fitting = run_fitting(freq=mmm_freq)
            channel_params = fitting["params"]

    channels = list(config["channels"]["modeled"])
    budget = float(
        confirmed_budget
        or detected_budget
        or config["optimization"]["default_budget"]
    )
    optim = solve(channel_params, budget, channels)

    model_b: ActivationSolveResult | None = None
    if run_model_b_solve:
        try:
            model_b = run_model_b(channel_params, budget, channels, config=config)
        except (KeyError, ValueError, RuntimeError):
            model_b = None

    if train_df is None:
        train_path = resolve_project_path(config["data"]["train_path"])
        if Path(train_path).exists():
            train_df = pd.read_csv(train_path)

    if train_df is not None and len(train_df) > 0:
        optim = apply_baseline_to_result(
            optim, channel_params, channels, budget, train_df, config=config
        )

    return optim, channel_params, budget, model_b


def apply_optimization_to_session(
    session_state: Any,
    optim: OptimResult,
    channel_params: dict,
    model_b: ActivationSolveResult | None = None,
) -> None:
    """Persist optimizer outputs on Streamlit session_state."""
    config = load_config()
    session_state.channel_params = channel_params
    session_state.optim_result = optim
    session_state.optimizer_fn = optimizer_fn_for_sensitivity
    session_state.activation_thresholds = load_activation_thresholds(config)
    session_state.optim_result_B = model_b.result if model_b is not None else None
    session_state.optimization_complete = True
    session_state.phase = "explore"
