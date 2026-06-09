"""Tests for optimization_pipeline."""
from __future__ import annotations

from src.optimization_pipeline import optimizer_fn_for_sensitivity, run_optimization_pipeline


def test_run_optimization_pipeline_returns_result():
    params = {
        "google_paid_search": {"a": 100.0, "b": 0.001},
        "google_shopping": {"a": 80.0, "b": 0.002},
        "google_pmax": {"a": 90.0, "b": 0.0015},
        "meta_facebook": {"a": 70.0, "b": 0.003},
        "meta_instagram": {"a": 60.0, "b": 0.004},
    }
    optim, out_params, budget = run_optimization_pipeline(
        confirmed_budget=10_000.0,
        channel_params=params,
    )
    assert out_params == params
    assert budget == 10_000.0
    assert optim.total_spent <= budget + 1e-6
    assert optim.allocation


def test_optimizer_fn_for_sensitivity_shape():
    params = {"ch_a": {"a": 50.0, "b": 0.01}}
    out = optimizer_fn_for_sensitivity(params, ["ch_a"], 1000.0)
    assert "allocation" in out and "predicted_conversions" in out
