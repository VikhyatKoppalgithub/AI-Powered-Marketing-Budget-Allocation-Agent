"""Model A vs B vs C comparison page.

Owner: Vikhyat Koppal

Renders the stakeholder-modification deliverable:
- Side-by-side comparison of Model A (base), Model B (activation thresholds),
  and Model C (adstock + activation).
- Adstock decay viz, curve drift overlay, shadow price trend, activation status.
- LLM-generated answers to the 8 plain-language questions from the modification.

Session-state contract (set by Meghna's optimizer page or app.py):
- `optim_result`          → OptimResult for Model A
- `optim_result_B`        → OptimResult for Model B (None until Meghna ships)
- `optim_result_C`        → OptimResult for Model C (None until Meghna + Greg ship)
- `channel_params`        → fitted (a, b) from Model A
- `channel_params_C`      → re-fitted (a, b) under adstock for Model C
- `activation_thresholds` → {channel: kappa} dict
- `adstock_lambdas`       → {channel: lambda} dict
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from src.explainer import (
    activation_status,
    compare_models,
    generate_comparison_explanation,
    plot_activation_status,
    plot_adstock_decay,
    plot_curve_drift,
    plot_shadow_price_trend,
)

st.title("🔬 Model Comparison: A vs B vs C")

st.markdown(
    "**Stakeholder modification view.** Compares the base model against the "
    "activation-threshold model and the adstock + activation model. Surfaces "
    "the conversion cost of activation, the value of the budget under each "
    "model, and the impact of carryover."
)

with st.expander("🟢 In plain English — what is this page?"):
    st.markdown(
        """
We built three versions of the model, each a bit more realistic:

- **Model A — basic:** just split the budget for the most conversions.
- **Model B — on/off rules:** a channel must get a **minimum** amount to be
  worth "turning on", otherwise it stays at $0 (no tiny, wasteful spends).
- **Model C — carryover (adstock):** today's spend keeps working for a while
  *after* you spend it, not just on the same day.

This page compares what each one recommends, so you can see how those
real-world rules change the plan.
"""
    )

# -----------------------------------------------------------------------------
# Pull models + metadata from session state
# -----------------------------------------------------------------------------
result_A = st.session_state.get("optim_result")
result_B = st.session_state.get("optim_result_B")
result_C = st.session_state.get("optim_result_C")
params_A = st.session_state.get("channel_params") or {}
params_C = st.session_state.get("channel_params_C") or {}
thresholds = st.session_state.get("activation_thresholds") or {}
lambdas = st.session_state.get("adstock_lambdas") or {}

metadata = {
    "A": {"name": "Base", "thresholds": None, "lambdas": None},
    "B": {"name": "Activation", "thresholds": thresholds, "lambdas": None},
    "C": {"name": "Adstock + Activation", "thresholds": thresholds, "lambdas": lambdas},
}

if result_A is None:
    st.warning(
        "No Model A result yet — run the base optimizer (Page 3) first. "
        "Models B and C will appear here once Meghna ships the activation "
        "and adstock solvers."
    )
    st.stop()

# -----------------------------------------------------------------------------
# Status banner
# -----------------------------------------------------------------------------
status_chips = []
status_chips.append("✅ Model A" if result_A else "⏳ Model A")
status_chips.append("✅ Model B" if result_B else "⏳ Model B (pending)")
status_chips.append("✅ Model C" if result_C else "⏳ Model C (pending)")
st.caption(" · ".join(status_chips))

# -----------------------------------------------------------------------------
# Comparison table
# -----------------------------------------------------------------------------
st.subheader("Side-by-side comparison")
table = compare_models(result_A, result_B, result_C, metadata)
st.dataframe(
    table.style.format(
        {
            "Predicted Conversions": "{:,.1f}",
            "Total Spent": "${:,.0f}",
            "Shadow Price (λ_budget)": "{:.4f}",
        },
        na_rep="—",
    ),
    use_container_width=True,
)

st.caption(
    "Shadow price λ_budget = extra predicted conversions from one more "
    "dollar of weekly budget at the optimum."
)

# -----------------------------------------------------------------------------
# Shadow price trend
# -----------------------------------------------------------------------------
shadow_prices = {}
for key, r in [("A", result_A), ("B", result_B), ("C", result_C)]:
    if r is None:
        continue
    val = getattr(r, "lambda_budget", None)
    if val is None and isinstance(r, dict):
        val = r.get("lambda_budget")
    if val is not None:
        shadow_prices[f"Model {key}"] = float(val)

if shadow_prices:
    st.subheader("Budget shadow price across models")
    st.plotly_chart(plot_shadow_price_trend(shadow_prices), use_container_width=True)

# -----------------------------------------------------------------------------
# Model B — activation status
# -----------------------------------------------------------------------------
if result_B is not None:
    st.subheader("Model B — channel activation status")
    allocation_B = getattr(result_B, "allocation", None)
    if allocation_B is None and isinstance(result_B, dict):
        allocation_B = result_B.get("allocation", {})
    if allocation_B:
        status_B = activation_status(allocation_B, thresholds=thresholds)
        st.plotly_chart(plot_activation_status(status_B), use_container_width=True)
        on_count = sum(1 for s in status_B if s["status"] in ("ON_INTERIOR", "AT_KAPPA"))
        off_count = sum(1 for s in status_B if s["status"] == "OFF")
        st.caption(
            f"**{on_count} channels active · {off_count} channels turned off.** "
            "Channels marked 'AT_KAPPA' sit exactly at their activation "
            "threshold — the binding constraint, not the saturation curve."
        )
else:
    st.info("Model B not yet available — activation status will render once Meghna ships it.")

# -----------------------------------------------------------------------------
# Model C — adstock decay + curve drift
# -----------------------------------------------------------------------------
if lambdas:
    st.subheader("Model C — adstock decay rate per channel")
    st.plotly_chart(plot_adstock_decay(lambdas), use_container_width=True)

if params_A and params_C:
    st.subheader("Saturation curve drift: Model A vs Model C")
    st.plotly_chart(
        plot_curve_drift(params_A, params_C, lambdas=lambdas),
        use_container_width=True,
    )
elif not params_C:
    st.info(
        "Model C curves not yet available — once Greg ships re-fitted "
        "parameters under adstock, the curve drift overlay will render here."
    )

# -----------------------------------------------------------------------------
# Plain-language answers (8 questions)
# -----------------------------------------------------------------------------
st.subheader("💬 Plain-language answers (Sections 1.3 + 2.3 of the modification)")
with st.spinner("Generating comparison narrative..."):
    narrative = generate_comparison_explanation(
        result_A, result_B, result_C, metadata=metadata
    )
st.markdown(narrative)

# -----------------------------------------------------------------------------
# Provenance — what data the page is using
# -----------------------------------------------------------------------------
with st.expander("Provenance — what's in session state"):
    st.json(
        {
            "has_result_A": result_A is not None,
            "has_result_B": result_B is not None,
            "has_result_C": result_C is not None,
            "channels_in_params_A": list(params_A.keys()),
            "channels_in_params_C": list(params_C.keys()),
            "activation_thresholds": thresholds,
            "adstock_lambdas": lambdas,
        }
    )
