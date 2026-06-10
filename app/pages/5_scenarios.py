"""Sensitivity / scenario analysis page.

Runs the optimizer across a user-defined grid of budget multipliers and
shows the tornado chart + per-channel allocation flow.

Owner: Vikhyat Koppal
Depends on session state keys:
- `optim_result`: OptimResult from Meghna's optimizer
- `channel_params`: {channel: {"a": float, "b": float}} from Gregory
- (optional) `optimizer_fn`: callable from Meghna's optimizer module
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from src.explainer import plot_sensitivity_tornado, run_sensitivity

st.title("🎯 Sensitivity & Scenario Analysis")

st.markdown(
    "How does the recommendation change when the budget shifts? "
    "These scenarios test the robustness of the allocation strategy and "
    "demonstrate the agent's behaviour under stakeholder-driven modifications."
)

with st.expander("🟢 In plain English — what is this page?"):
    st.markdown(
        """
This page asks *"what if your budget were different?"*

It re-runs the recommendation across a range of budgets, so you can see:

- which channels keep **absorbing money productively** as the budget grows, and
- which ones **saturate** and stop being worth more.

It's useful for planning a budget increase — or for defending the plan if your
budget gets cut.
"""
    )

optim_result = st.session_state.get("optim_result")
channel_params = st.session_state.get("channel_params")
optimizer_fn = st.session_state.get("optimizer_fn")  # optional, set by Meghna

if optim_result is None or not channel_params:
    st.warning(
        "Need both the optimizer output (`optim_result`) and the channel "
        "parameters (`channel_params`) in session state. Complete the earlier "
        "steps first."
    )
    st.stop()


def _get(obj, attr, default=None):
    if hasattr(obj, attr):
        return getattr(obj, attr)
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return default


allocation = _get(optim_result, "allocation", {})
base_budget = _get(optim_result, "total_spent", sum(allocation.values()))
channels = list(allocation.keys())

# -----------------------------------------------------------------------------
# Controls
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("Scenario Settings")
    min_mult = st.slider("Min budget multiplier", 0.25, 1.0, 0.5, 0.05)
    max_mult = st.slider("Max budget multiplier", 1.0, 3.0, 2.0, 0.1)
    n_points = st.slider("Number of scenarios", 4, 15, 7)

multipliers = list(np.round(np.linspace(min_mult, max_mult, n_points), 3))
if 1.0 not in multipliers:
    multipliers.append(1.0)
    multipliers = sorted(multipliers)

# -----------------------------------------------------------------------------
# Run sensitivity grid
# -----------------------------------------------------------------------------
with st.spinner("Running sensitivity grid..."):
    sens_df = run_sensitivity(
        channel_params,
        base_budget,
        channels,
        optimizer_fn=optimizer_fn,
        multipliers=multipliers,
    )

# -----------------------------------------------------------------------------
# Headline metrics
# -----------------------------------------------------------------------------
base_row = sens_df.loc[(sens_df["multiplier"] - 1.0).abs().idxmin()]
worst = sens_df.loc[sens_df["predicted_conversions"].idxmin()]
best = sens_df.loc[sens_df["predicted_conversions"].idxmax()]

c1, c2, c3 = st.columns(3)
c1.metric("Base scenario", f"{base_row['predicted_conversions']:,.1f}")
c2.metric(
    f"Best ({best['multiplier']:.2f}x)",
    f"{best['predicted_conversions']:,.1f}",
    delta=f"{(best['predicted_conversions'] - base_row['predicted_conversions']):+.1f}",
)
c3.metric(
    f"Worst ({worst['multiplier']:.2f}x)",
    f"{worst['predicted_conversions']:,.1f}",
    delta=f"{(worst['predicted_conversions'] - base_row['predicted_conversions']):+.1f}",
)

# -----------------------------------------------------------------------------
# Tornado chart
# -----------------------------------------------------------------------------
st.subheader("Sensitivity Tornado")
st.plotly_chart(plot_sensitivity_tornado(sens_df), use_container_width=True)

# -----------------------------------------------------------------------------
# Allocation flow across budgets
# -----------------------------------------------------------------------------
st.subheader("Allocation Flow Across Budget Levels")
flow_rows = []
for _, row in sens_df.iterrows():
    for channel, amount in row["allocation"].items():
        flow_rows.append(
            {
                "Budget Multiplier": f"{row['multiplier']:.2f}x",
                "Budget": row["budget"],
                "Channel": channel.replace("_SPEND", "").replace("_", " ").title(),
                "Allocation": amount,
            }
        )
flow_df = pd.DataFrame(flow_rows)

fig_flow = px.bar(
    flow_df,
    x="Budget Multiplier",
    y="Allocation",
    color="Channel",
    title="How allocation shifts as the budget scales",
    template="plotly_white",
)
fig_flow.update_layout(height=500)
st.plotly_chart(fig_flow, use_container_width=True)

# -----------------------------------------------------------------------------
# Scenario summary table
# -----------------------------------------------------------------------------
st.subheader("Scenario Summary")
summary = sens_df[["multiplier", "budget", "predicted_conversions"]].copy()
summary["lift_vs_base_pct"] = (
    summary["predicted_conversions"] / base_row["predicted_conversions"] - 1
) * 100
summary["conv_per_$1k"] = summary["predicted_conversions"] / (summary["budget"] / 1000)

st.dataframe(
    summary.style.format(
        {
            "multiplier": "{:.2f}x",
            "budget": "${:,.0f}",
            "predicted_conversions": "{:,.1f}",
            "lift_vs_base_pct": "{:+.1f}%",
            "conv_per_$1k": "{:.2f}",
        }
    ),
    use_container_width=True,
)

st.caption(
    "The marginal efficiency (conversions per $1K) is the headline number for "
    "stakeholder Q&A — it captures how diminishing returns affect the "
    "incremental value of each additional dollar."
)
