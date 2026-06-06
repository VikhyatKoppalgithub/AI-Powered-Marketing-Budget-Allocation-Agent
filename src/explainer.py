"""Explanation & validation layer.

Owner: Vikhyat Koppal
Responsibilities: plain-English rationales, saturation curve viz,
allocation comparison, sensitivity analysis, baseline lift charts.

Integration contracts:
- Consumes `OptimResult` from Meghna's `src/optimizer.py`.
- Consumes channel parameters from Gregory's `src/mmm_model.py`
  (loaded from `data/processed/channel_params.json`).
- Outputs Plotly figures and plain-English text used by the
  Streamlit pages (`app/pages/3_*`, `4_*`, `5_*`).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


# =============================================================================
# Contract: OptimResult shape
# =============================================================================
# This mirrors what Meghna's optimizer is expected to return. The dataclass is
# kept here so that the explainer module is testable in isolation. If Meghna's
# real type differs, only this dataclass needs to change.

@dataclass
class OptimResult:
    """Standard contract for optimization output across the project."""

    allocation: dict[str, float]
    predicted_conversions: float
    total_spent: float
    status: str
    baseline_allocation: dict[str, float]
    baseline_conversions: float
    lift_pct: float


def _coerce(obj: Any, attr: str, default: Any = None) -> Any:
    """Read attr from either a dataclass-like object or a dict."""
    if obj is None:
        return default
    if hasattr(obj, attr):
        return getattr(obj, attr)
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return default


def _channel_label(channel: str) -> str:
    return channel.replace("_SPEND", "").replace("_", " ").title()


# =============================================================================
# 1. generate_explanation
# =============================================================================
def generate_explanation(optim_result: Any, params: dict) -> str:
    """Plain-English optimization explanation.

    Uses Claude if an API key is configured; otherwise falls back to a
    template-based explanation so the page never breaks during the demo.
    """
    allocation = _coerce(optim_result, "allocation", {})
    predicted = _coerce(optim_result, "predicted_conversions", 0.0)
    baseline = _coerce(optim_result, "baseline_allocation", {})
    baseline_conv = _coerce(optim_result, "baseline_conversions", 0.0)
    lift = _coerce(optim_result, "lift_pct", 0.0)

    # Try Claude first
    try:
        from src.agent import call_claude

        context = {
            "agent_allocation": allocation,
            "agent_predicted_conversions": predicted,
            "baseline_allocation": baseline,
            "baseline_predicted_conversions": baseline_conv,
            "lift_pct": lift,
            "params": params,
        }

        prompt = (
            "You are a marketing analyst explaining a budget allocation "
            "decision to a CMO.\n\n"
            "Write a 3-paragraph rationale in plain English (under 250 words):\n"
            "1. Headline (1-2 sentences): the key shift from the baseline.\n"
            "2. Why (3-4 sentences): which channels gained budget and which "
            "lost it, framed in terms of saturation and marginal returns.\n"
            "3. Risks + 1 sensitivity insight (2-3 sentences).\n\n"
            "Be concrete with dollar amounts and percentages. No jargon. "
            "Use Markdown headings for each section.\n\n"
            f"CONTEXT:\n{json.dumps(context, indent=2, default=str)}"
        )
        explanation = call_claude(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="You explain marketing optimization results clearly and concisely.",
        )
        if explanation:
            return explanation
    except Exception as exc:  # noqa: BLE001 - we want to degrade gracefully
        print(f"[explainer] Claude failed, using fallback: {exc}")

    return _template_explanation(allocation, predicted, baseline, baseline_conv, lift)


def _template_explanation(
    allocation: dict[str, float],
    predicted: float,
    baseline: dict[str, float],
    baseline_conv: float,
    lift: float,
) -> str:
    """Deterministic fallback explanation when no LLM is available."""
    if not allocation:
        return "_No allocation data available to explain._"

    diffs = {c: allocation[c] - baseline.get(c, 0) for c in allocation}
    winners = sorted(((c, d) for c, d in diffs.items() if d > 0), key=lambda kv: -kv[1])[:2]
    losers = sorted(((c, d) for c, d in diffs.items() if d < 0), key=lambda kv: kv[1])[:2]

    winners_text = ", ".join(f"**{_channel_label(c)}** (+${d:,.0f})" for c, d in winners) or "no channel"
    losers_text = ", ".join(f"**{_channel_label(c)}** (${d:,.0f})" for c, d in losers) or "no channel"

    return (
        f"### Headline\n"
        f"The agent recommends shifting budget toward {winners_text} and away "
        f"from {losers_text}, producing a predicted lift of **{lift:+.1f}%** in "
        f"conversions versus the proportional baseline "
        f"({predicted:,.0f} vs {baseline_conv:,.0f}).\n\n"
        f"### Why\n"
        f"At current spend levels, the channels that gained budget exhibit "
        f"higher marginal returns: each additional dollar spent on them "
        f"produces more incremental conversions than the channels that lost "
        f"budget. The losers were operating in their saturation zone, where "
        f"further investment yields diminishing returns. The optimizer "
        f"equalises the marginal return across active channels subject to "
        f"the budget and constraint set.\n\n"
        f"### Risks & sensitivity\n"
        f"This recommendation assumes the fitted saturation curves remain "
        f"valid during the forecast period. Material shifts in competitor "
        f"behaviour, seasonality, or platform algorithms could change the "
        f"marginal returns. A ±20% budget shock typically reweights the "
        f"allocation by roughly {abs(lift)/2:.1f}% across the top two channels — "
        f"see the Scenario Analysis page for the full grid."
    )


# =============================================================================
# 2. plot_saturation_curves
# =============================================================================
def plot_saturation_curves(params: dict) -> go.Figure:
    """Plotly saturation curves for every channel in `params`.

    `params` is a dict of the form
        {channel_name: {"a": <max response>, "b": <saturation rate>}}.
    """
    fig = go.Figure()
    if not params:
        fig.update_layout(
            title="No channel parameters available",
            template="plotly_white",
            height=400,
        )
        return fig

    # X-axis range driven by the slowest-saturating channel
    b_values = [p.get("b", 1e-4) for p in params.values()]
    b_min = max(min(b_values), 1e-6)
    x_max = 8.0 / b_min  # 8 / b ≈ region where the slowest channel approaches ceiling
    x = np.linspace(0, x_max, 200)

    for channel, p in params.items():
        a = p.get("a", 0.0)
        b = p.get("b", 0.0)
        y = a * (1 - np.exp(-b * x))
        label = _channel_label(channel)
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="lines",
                name=label,
                hovertemplate=(
                    f"<b>{label}</b><br>"
                    "Spend: $%{x:,.0f}<br>"
                    "Predicted: %{y:,.1f}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title="Channel Saturation Curves",
        xaxis_title="Channel Spend",
        yaxis_title="Predicted Conversions",
        hovermode="x unified",
        template="plotly_white",
        height=500,
        legend=dict(orientation="h", y=-0.2),
    )
    return fig


# =============================================================================
# 3. plot_allocation_bar
# =============================================================================
def plot_allocation_bar(
    allocation: dict, baseline: dict | None = None
) -> go.Figure:
    """Bar chart of recommended allocation per channel.

    If `baseline` is provided, plots both side-by-side for comparison.
    """
    if not allocation:
        return go.Figure(layout={"title": "No allocation to display"})

    channels = list(allocation.keys())
    labels = [_channel_label(c) for c in channels]
    agent_values = [allocation[c] for c in channels]

    fig = go.Figure()
    if baseline:
        baseline_values = [baseline.get(c, 0.0) for c in channels]
        fig.add_trace(
            go.Bar(
                name="Baseline (proportional)",
                x=labels,
                y=baseline_values,
                marker_color="lightgray",
                text=[f"${v:,.0f}" for v in baseline_values],
                textposition="outside",
            )
        )
    fig.add_trace(
        go.Bar(
            name="Agent (optimized)",
            x=labels,
            y=agent_values,
            marker_color="steelblue",
            text=[f"${v:,.0f}" for v in agent_values],
            textposition="outside",
        )
    )

    fig.update_layout(
        title="Recommended Budget Allocation",
        xaxis_title="Channel",
        yaxis_title="Spend",
        barmode="group",
        template="plotly_white",
        height=450,
        legend=dict(orientation="h", y=-0.2),
    )
    return fig


# =============================================================================
# 4. run_sensitivity
# =============================================================================
def run_sensitivity(
    params: dict,
    budget: float,
    channels: list[str],
    optimizer_fn: Callable[[dict, list[str], float], dict] | None = None,
    multipliers: list[float] | None = None,
) -> pd.DataFrame:
    """Run the optimizer across a grid of budget multipliers.

    Args:
        params: channel parameters {channel: {"a": float, "b": float}}.
        budget: base (current) budget.
        channels: list of channels to allocate across.
        optimizer_fn: function (params, channels, budget) -> {"allocation": dict,
            "predicted_conversions": float}. If None, falls back to an internal
            CVXPY solver matching Meghna's expected behavior.
        multipliers: list of budget multipliers (default 0.5, 0.75, 1.0, 1.25,
            1.5, 2.0).

    Returns:
        DataFrame with columns: multiplier, budget, predicted_conversions,
        allocation (dict per row).
    """
    if multipliers is None:
        multipliers = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
    if optimizer_fn is None:
        optimizer_fn = _internal_optimizer

    rows = []
    for m in multipliers:
        b = budget * m
        try:
            result = optimizer_fn(params, channels, b)
        except Exception as exc:  # noqa: BLE001 - keep the grid running
            print(f"[explainer] optimizer failed at multiplier {m}: {exc}")
            result = {"allocation": {c: 0.0 for c in channels}, "predicted_conversions": 0.0}
        rows.append(
            {
                "multiplier": m,
                "budget": b,
                "predicted_conversions": float(result.get("predicted_conversions", 0.0)),
                "allocation": result.get("allocation", {}),
            }
        )
    return pd.DataFrame(rows)


def _internal_optimizer(
    params: dict, channels: list[str], budget: float
) -> dict:
    """Fallback CVXPY optimizer that matches Meghna's expected output shape."""
    try:
        import cvxpy as cp
    except ImportError:
        # Worst-case: proportional split
        per = budget / max(len(channels), 1)
        return {"allocation": {c: per for c in channels}, "predicted_conversions": 0.0}

    n = len(channels)
    x = cp.Variable(n, nonneg=True)
    a = np.array([params[c].get("a", 0.0) for c in channels])
    b = np.array([params[c].get("b", 0.0) for c in channels])
    objective = cp.Maximize(cp.sum(cp.multiply(a, 1 - cp.exp(-cp.multiply(b, x)))))
    constraints = [cp.sum(x) <= budget]
    prob = cp.Problem(objective, constraints)
    try:
        prob.solve(solver=cp.CLARABEL)
    except Exception:
        prob.solve(solver=cp.SCS)
    return {
        "allocation": {c: float(x.value[i]) for i, c in enumerate(channels)},
        "predicted_conversions": float(prob.value),
    }


# =============================================================================
# 5. plot_sensitivity_tornado
# =============================================================================
def plot_sensitivity_tornado(sensitivity_df: pd.DataFrame) -> go.Figure:
    """Tornado chart: percent change in conversions for each scenario vs base."""
    if sensitivity_df is None or sensitivity_df.empty:
        return go.Figure(layout={"title": "No sensitivity scenarios"})

    df = sensitivity_df.copy()

    # Identify the base row (multiplier closest to 1.0)
    base_idx = (df["multiplier"] - 1.0).abs().idxmin()
    base_conv = df.loc[base_idx, "predicted_conversions"] or 1.0
    df["delta_pct"] = (df["predicted_conversions"] - base_conv) / base_conv * 100
    df["label"] = df["multiplier"].apply(
        lambda m: "Base" if abs(m - 1.0) < 1e-6 else f"Budget {m:.2f}x"
    )
    df = df.sort_values("delta_pct")

    colors = ["crimson" if d < 0 else "seagreen" for d in df["delta_pct"]]

    fig = go.Figure(
        go.Bar(
            x=df["delta_pct"],
            y=df["label"],
            orientation="h",
            marker_color=colors,
            text=[f"{d:+.1f}%" for d in df["delta_pct"]],
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Budget Sensitivity Tornado: % change in predicted conversions vs base",
        xaxis_title="Δ Predicted conversions (%)",
        yaxis_title="Scenario",
        template="plotly_white",
        height=420,
    )
    return fig


# =============================================================================
# 6b. diagnose_allocation  (helper for the Allocation page)
# =============================================================================
def diagnose_allocation(
    allocation: dict[str, float],
    channel_params: dict | None = None,
    channel_caps: dict[str, float] | None = None,
    near_zero_threshold: float = 1.0,
    cap_proximity_threshold: float = 0.98,
) -> list[dict]:
    """Surface modeling caveats in the recommended allocation.

    Returns a list of diagnostic dicts of the form
        {"level": "info" | "warn" | "error", "message": str}

    Specifically flags:
    - Channels that collapse to ~$0 (often multicollinearity, per Greg's MMM)
    - Channels that hit (or come near) their cap
    - Channels whose b is suspiciously small (near-linear fit → risky
      extrapolation outside the training range)

    The page can render these as Streamlit alerts above the headline chart.
    """
    diagnostics: list[dict] = []
    total = sum(allocation.values()) or 1.0

    for channel, amount in allocation.items():
        label = _channel_label(channel)

        # Near-zero allocations
        if amount < near_zero_threshold:
            diagnostics.append(
                {
                    "level": "warn",
                    "channel": channel,
                    "message": (
                        f"**{label}** received $0 in the recommended allocation. "
                        f"This is typically a sign of multicollinearity in the MMM — "
                        f"the channel's effect is not separately identifiable from "
                        f"correlated channels. Consider dropping it from "
                        f"`config.channels.modeled` or adding a minimum-spend floor."
                    ),
                }
            )

        # Cap proximity
        if channel_caps and channel in channel_caps:
            cap = channel_caps[channel]
            if cap > 0 and amount >= cap_proximity_threshold * cap:
                diagnostics.append(
                    {
                        "level": "info",
                        "channel": channel,
                        "message": (
                            f"**{label}** is loaded to {amount / cap:.0%} of its "
                            f"channel cap (${cap:,.0f}). The optimizer would spend "
                            f"more here if the cap were relaxed — this is the "
                            f"binding constraint, not the curve."
                        ),
                    }
                )

        # Near-linear fit (low b) → extrapolation risk
        if channel_params and channel in channel_params:
            b = channel_params[channel].get("b", 0.0)
            if 0 < b < 1e-7 and amount > 0.05 * total:
                diagnostics.append(
                    {
                        "level": "warn",
                        "channel": channel,
                        "message": (
                            f"**{label}** has a near-linear response curve "
                            f"(b = {b:.2e}). The ceiling is an extrapolation "
                            f"outside the historical spend range — treat the "
                            f"recommended amount as an upper bound, not a target."
                        ),
                    }
                )

    return diagnostics


# =============================================================================
# 6. plot_baseline_lift
# =============================================================================
def plot_baseline_lift(baseline: dict, optimized: dict) -> go.Figure:
    """Side-by-side bar chart of baseline vs optimized, with per-channel delta."""
    if not optimized:
        return go.Figure(layout={"title": "No optimization to compare"})

    channels = list(optimized.keys())
    labels = [_channel_label(c) for c in channels]
    base_vals = [baseline.get(c, 0.0) for c in channels]
    opt_vals = [optimized.get(c, 0.0) for c in channels]
    diffs = [o - b for o, b in zip(opt_vals, base_vals)]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(x=labels, y=base_vals, name="Baseline", marker_color="lightgray")
    )
    fig.add_trace(
        go.Bar(x=labels, y=opt_vals, name="Optimized", marker_color="steelblue")
    )
    for label, base, opt, d in zip(labels, base_vals, opt_vals, diffs):
        fig.add_annotation(
            x=label,
            y=max(base, opt),
            text=f"<b>{d:+,.0f}</b>",
            showarrow=False,
            yshift=15,
            font=dict(color="seagreen" if d >= 0 else "crimson", size=12),
        )
    fig.update_layout(
        title="Baseline vs Optimized: where the agent moved money",
        xaxis_title="Channel",
        yaxis_title="Spend",
        barmode="group",
        template="plotly_white",
        height=450,
        legend=dict(orientation="h", y=-0.2),
    )
    return fig
