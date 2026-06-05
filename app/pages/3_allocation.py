"""Allocation results page.

Shows the recommended allocation per channel, the lift versus the baseline,
and a plain-English rationale from the explainer.

Owner: Vikhyat Koppal
Depends on session state keys (populated by Meghna's optimizer page):
- `optim_result`: OptimResult dataclass or equivalent dict
- (optional) `channel_params`: {channel: {"a": float, "b": float}}
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.explainer import (
    diagnose_allocation,
    generate_explanation,
    plot_allocation_bar,
    plot_baseline_lift,
)

st.set_page_config(page_title="Allocation", page_icon="📊", layout="wide")
st.title("📊 Recommended Allocation")

optim_result = st.session_state.get("optim_result")

if optim_result is None:
    st.warning(
        "No optimization result yet. Please complete the upload, confirm the "
        "backward analysis, and run the optimizer before viewing this page."
    )
    st.stop()


def _get(obj, attr, default=None):
    if hasattr(obj, attr):
        return getattr(obj, attr)
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return default


allocation = _get(optim_result, "allocation", {})
baseline = _get(optim_result, "baseline_allocation", {})
predicted = _get(optim_result, "predicted_conversions", 0.0)
baseline_conv = _get(optim_result, "baseline_conversions", 0.0)
lift = _get(optim_result, "lift_pct", 0.0)
total_spent = _get(optim_result, "total_spent", sum(allocation.values()))
status = _get(optim_result, "status", "unknown")

# -----------------------------------------------------------------------------
# Headline metrics
# -----------------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Budget Allocated", f"${total_spent:,.0f}")
col2.metric("Predicted Conversions", f"{predicted:,.1f}")
col3.metric("Baseline Conversions", f"{baseline_conv:,.1f}")
col4.metric("Lift vs Baseline", f"{lift:+.1f}%")

st.caption(f"Solver status: `{status}`")

# -----------------------------------------------------------------------------
# Diagnostics — surface multicollinearity, cap-binding, near-linear fits
# -----------------------------------------------------------------------------
channel_params = st.session_state.get("channel_params")
channel_caps = st.session_state.get("channel_caps")  # set by Meghna's optimizer

diagnostics = diagnose_allocation(
    allocation=allocation,
    channel_params=channel_params,
    channel_caps=channel_caps,
)
if diagnostics:
    with st.expander(f"⚠️ {len(diagnostics)} modeling caveat(s) — read before sharing", expanded=True):
        for d in diagnostics:
            level = d.get("level", "info")
            msg = d.get("message", "")
            if level == "warn":
                st.warning(msg)
            elif level == "error":
                st.error(msg)
            else:
                st.info(msg)

# -----------------------------------------------------------------------------
# Allocation bar chart
# -----------------------------------------------------------------------------
st.subheader("Allocation by Channel")
st.plotly_chart(
    plot_allocation_bar(allocation, baseline=baseline), use_container_width=True
)

# -----------------------------------------------------------------------------
# Detailed table
# -----------------------------------------------------------------------------
st.subheader("Allocation Detail")
detail = pd.DataFrame(
    {
        "Channel": list(allocation.keys()),
        "Recommended": list(allocation.values()),
        "Baseline": [baseline.get(c, 0.0) for c in allocation.keys()],
    }
)
detail["Δ vs Baseline"] = detail["Recommended"] - detail["Baseline"]
detail["% of Budget"] = (
    detail["Recommended"] / max(total_spent, 1.0) * 100.0
)

st.dataframe(
    detail.style.format(
        {
            "Recommended": "${:,.0f}",
            "Baseline": "${:,.0f}",
            "Δ vs Baseline": "${:+,.0f}",
            "% of Budget": "{:.1f}%",
        }
    ),
    use_container_width=True,
)

# -----------------------------------------------------------------------------
# Lift comparison
# -----------------------------------------------------------------------------
st.subheader("Where the Agent Moved Money")
st.plotly_chart(plot_baseline_lift(baseline, allocation), use_container_width=True)

# -----------------------------------------------------------------------------
# Explanation
# -----------------------------------------------------------------------------
st.subheader("💡 Why This Recommendation")
with st.spinner("Generating explanation..."):
    explanation = generate_explanation(
        optim_result,
        params={
            "channels": list(allocation.keys()),
            "budget": total_spent,
            "objective": _get(optim_result, "objective", "conversions"),
        },
    )
st.markdown(explanation)
