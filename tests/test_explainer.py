"""Unit tests for src/explainer.py.

These tests do not require an ANTHROPIC_API_KEY — explanation tests rely on the
deterministic template fallback. Plot tests verify only that figures are
returned and structured correctly, not visual output.

Run from repo root:
    pytest tests/test_explainer.py -v
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import pytest

from src.explainer import (
    OptimResult,
    diagnose_allocation,
    generate_explanation,
    plot_allocation_bar,
    plot_baseline_lift,
    plot_saturation_curves,
    plot_sensitivity_tornado,
    run_sensitivity,
)


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------
# Channel names match config.channels.modeled in the team repo (lowercase,
# no _SPEND suffix). Magnitudes reflect Greg's monthly-USD MMM scale.
@pytest.fixture
def channel_params():
    return {
        "google_paid_search": {"a": 1.0e-6, "b": 1.0e-8},   # collinear → ~0 in solver
        "google_shopping":    {"a": 50_000.0, "b": 1.5e-6},
        "google_pmax":        {"a": 120_000.0, "b": 4.0e-7}, # near-linear, needs cap
        "meta_facebook":      {"a": 95_000.0, "b": 5.0e-7},  # near-linear, needs cap
        "meta_instagram":     {"a": 1.0e-6, "b": 1.0e-8},   # collinear → ~0 in solver
    }


@pytest.fixture
def channels(channel_params):
    return list(channel_params.keys())


@pytest.fixture
def optim_result():
    return OptimResult(
        allocation={
            "google_paid_search": 0.0,           # zeroed by multicollinearity
            "google_shopping":    900_000.0,
            "google_pmax":        1_400_000.0,
            "meta_facebook":      1_200_000.0,
            "meta_instagram":     0.0,           # zeroed by multicollinearity
        },
        predicted_conversions=82_000.0,
        total_spent=3_500_000.0,
        status="optimal",
        baseline_allocation={
            "google_paid_search": 700_000.0,
            "google_shopping":    700_000.0,
            "google_pmax":        700_000.0,
            "meta_facebook":      700_000.0,
            "meta_instagram":     700_000.0,
        },
        baseline_conversions=68_000.0,
        lift_pct=20.6,
    )


# -----------------------------------------------------------------------------
# generate_explanation
# -----------------------------------------------------------------------------
def test_generate_explanation_returns_nonempty_string(optim_result, monkeypatch):
    # Ensure no API key is picked up so we hit the template fallback
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("API_Key", raising=False)
    text = generate_explanation(optim_result, params={"budget": 25000})
    assert isinstance(text, str)
    assert len(text) > 100
    assert "%" in text  # the headline cites a lift percent


def test_generate_explanation_accepts_dict_input(optim_result, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("API_Key", raising=False)
    as_dict = {
        "allocation": optim_result.allocation,
        "predicted_conversions": optim_result.predicted_conversions,
        "baseline_allocation": optim_result.baseline_allocation,
        "baseline_conversions": optim_result.baseline_conversions,
        "lift_pct": optim_result.lift_pct,
    }
    text = generate_explanation(as_dict, params={"budget": 25000})
    assert isinstance(text, str)
    assert len(text) > 0


# -----------------------------------------------------------------------------
# plot_saturation_curves
# -----------------------------------------------------------------------------
def test_plot_saturation_curves_returns_figure(channel_params):
    fig = plot_saturation_curves(channel_params)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == len(channel_params)


def test_plot_saturation_curves_empty_params():
    fig = plot_saturation_curves({})
    assert isinstance(fig, go.Figure)


# -----------------------------------------------------------------------------
# plot_allocation_bar
# -----------------------------------------------------------------------------
def test_plot_allocation_bar_returns_figure(optim_result):
    fig = plot_allocation_bar(optim_result.allocation, baseline=optim_result.baseline_allocation)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2  # baseline + optimized


def test_plot_allocation_bar_without_baseline(optim_result):
    fig = plot_allocation_bar(optim_result.allocation)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1


# -----------------------------------------------------------------------------
# run_sensitivity
# -----------------------------------------------------------------------------
def test_run_sensitivity_with_stub_optimizer(channel_params, channels):
    """Use a deterministic stub instead of CVXPY so the test is fast and pure."""

    def stub_optimizer(params, chans, budget):
        per = budget / len(chans)
        return {
            "allocation": {c: per for c in chans},
            "predicted_conversions": budget * 0.001,
        }

    df = run_sensitivity(
        channel_params,
        budget=10_000,
        channels=channels,
        optimizer_fn=stub_optimizer,
        multipliers=[0.5, 1.0, 1.5],
    )
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    assert {"multiplier", "budget", "predicted_conversions", "allocation"}.issubset(df.columns)


# -----------------------------------------------------------------------------
# plot_sensitivity_tornado
# -----------------------------------------------------------------------------
def test_plot_sensitivity_tornado_returns_figure():
    df = pd.DataFrame(
        {
            "multiplier": [0.5, 1.0, 1.5],
            "budget": [5000, 10000, 15000],
            "predicted_conversions": [80.0, 100.0, 115.0],
            "allocation": [{}, {}, {}],
        }
    )
    fig = plot_sensitivity_tornado(df)
    assert isinstance(fig, go.Figure)


def test_plot_sensitivity_tornado_empty_df():
    fig = plot_sensitivity_tornado(pd.DataFrame())
    assert isinstance(fig, go.Figure)


# -----------------------------------------------------------------------------
# plot_baseline_lift
# -----------------------------------------------------------------------------
def test_plot_baseline_lift_returns_figure(optim_result):
    fig = plot_baseline_lift(
        optim_result.baseline_allocation, optim_result.allocation
    )
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2  # baseline bar + optimized bar


# -----------------------------------------------------------------------------
# diagnose_allocation
# -----------------------------------------------------------------------------
def test_diagnose_allocation_flags_zero_channels(optim_result, channel_params):
    """Multicollinearity check: channels at $0 should be flagged."""
    diagnostics = diagnose_allocation(
        optim_result.allocation, channel_params=channel_params
    )
    zero_warnings = [d for d in diagnostics if d.get("level") == "warn" and "$0" in d["message"]]
    assert len(zero_warnings) >= 2  # paid_search + instagram per the fixture


def test_diagnose_allocation_flags_cap_binding(optim_result):
    """When an allocation hits its cap, it should be flagged as info."""
    caps = {"google_pmax": 1_400_000.0}  # exactly equals the optim allocation
    diagnostics = diagnose_allocation(optim_result.allocation, channel_caps=caps)
    cap_flags = [d for d in diagnostics if "cap" in d.get("message", "").lower()]
    assert len(cap_flags) >= 1


def test_diagnose_allocation_no_caveats_when_clean(channel_params):
    """When every channel is funded and there are no caps, return no warnings."""
    clean_alloc = {
        "google_paid_search": 100_000.0,
        "google_shopping":    100_000.0,
        "google_pmax":        100_000.0,
        "meta_facebook":      100_000.0,
        "meta_instagram":     100_000.0,
    }
    # Replace tiny-a fixtures with healthy ones so no near-linear warnings fire
    healthy_params = {c: {"a": 50_000.0, "b": 1e-5} for c in clean_alloc}
    diagnostics = diagnose_allocation(clean_alloc, channel_params=healthy_params)
    assert diagnostics == []
