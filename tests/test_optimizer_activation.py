"""Tests for Model B activation enumeration in optimizer.py."""
from __future__ import annotations

import pytest

from src.optimizer import (
    ActivationSolveResult,
    solve,
    solve_activation_kappa_sweep,
    solve_with_activation,
)


@pytest.fixture
def three_channel_params() -> dict:
    return {
        "strong": {"a": 50_000.0, "b": 1e-5},
        "weak": {"a": 1_000.0, "b": 1e-6},
        "mid": {"a": 20_000.0, "b": 2e-5},
    }


@pytest.fixture
def thresholds() -> dict[str, float]:
    return {"strong": 5_000.0, "weak": 5_000.0, "mid": 5_000.0}


@pytest.fixture
def ceilings() -> dict[str, float]:
    return {"strong": 100_000.0, "weak": 100_000.0, "mid": 100_000.0}


def test_solve_respects_lower_bound(three_channel_params):
    channels = ["strong", "mid"]
    bounds = {ch: (10_000.0, 50_000.0) for ch in channels}
    result = solve(
        three_channel_params,
        80_000.0,
        channels,
        channel_bounds=bounds,
        n_starts=5,
        seed=0,
    )
    for ch in channels:
        assert result.allocation[ch] >= 10_000.0 - 1e-3


def test_activation_skips_infeasible_pattern(thresholds, ceilings, three_channel_params):
    channels = list(thresholds.keys())
    # Only the all-OFF pattern is feasible when B < kappa
    out = solve_with_activation(
        three_channel_params,
        3_000.0,
        channels,
        thresholds,
        ceilings,
        n_starts=3,
        seed=1,
    )
    assert out.active_channels == ()
    assert out.result.total_spent == 0.0


def test_activation_turns_off_weak_channel(thresholds, ceilings, three_channel_params):
    channels = list(thresholds.keys())
    budget = 25_000.0  # can afford at most ~4 channels at 5k min; forces choices
    out = solve_with_activation(
        three_channel_params,
        budget,
        channels,
        thresholds,
        ceilings,
        n_starts=5,
        seed=2,
    )
    assert isinstance(out, ActivationSolveResult)
    assert out.patterns_feasible >= 1
    assert out.patterns_evaluated == 8  # 2^3
    assert "weak" not in out.active_channels or out.result.allocation["weak"] == 0.0
    for ch in channels:
        spend = out.result.allocation[ch]
        if spend <= 1e-6:
            assert ch not in out.active_channels
        else:
            assert spend >= thresholds[ch] - 1e-3


def test_activation_feasible_respects_kappa_and_budget(
    thresholds, ceilings, three_channel_params
):
    channels = list(thresholds.keys())
    budget = 40_000.0
    out = solve_with_activation(
        three_channel_params,
        budget,
        channels,
        thresholds,
        ceilings,
        n_starts=5,
        seed=3,
    )
    assert out.result.total_spent <= budget + 1e-3
    for ch in out.active_channels:
        assert out.result.allocation[ch] >= thresholds[ch] - 1e-3
        assert out.result.allocation[ch] <= ceilings[ch] + 1e-3


def test_kappa_sweep_returns_three_runs(thresholds, ceilings, three_channel_params):
    channels = list(thresholds.keys())
    budget = 50_000.0
    sweep = solve_activation_kappa_sweep(
        three_channel_params,
        budget,
        channels,
        thresholds,
        ceilings,
        factors=(0.8, 1.0, 1.2),
        n_starts=3,
        seed=4,
    )
    assert set(sweep) == {"kappa_x0.8", "kappa_x1", "kappa_x1.2"}
    assert all(isinstance(v, ActivationSolveResult) for v in sweep.values())


def test_model_a_vs_b_at_portfolio_scale(thresholds, ceilings, three_channel_params):
    """At large B, Model B should match or be close to Model A objective."""
    channels = list(thresholds.keys())
    budget = 200_000.0
    base = solve(three_channel_params, budget, channels, n_starts=5, seed=5)
    act = solve_with_activation(
        three_channel_params,
        budget,
        channels,
        thresholds,
        ceilings,
        n_starts=5,
        seed=5,
    )
    assert act.result.predicted_conversions <= base.predicted_conversions + 1e-6
