"""Saturation curves visualization page.

Shows the fitted Hill / exponential-saturation curve for each channel and
the underlying parameters (a, b).

Owner: Vikhyat Koppal
Depends on session state key:
- `channel_params`: {channel: {"a": float, "b": float}} from Gregory's MMM
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.explainer import plot_saturation_curves

st.set_page_config(page_title="Saturation Curves", page_icon="📈", layout="wide")
st.title("📈 Channel Saturation Curves")

st.markdown(
    "These curves show how each channel's predicted conversions respond to "
    "spend. The flattening at higher spend levels reflects **diminishing "
    "returns** — the foundation of why allocation matters."
)

channel_params = st.session_state.get("channel_params")

if not channel_params:
    st.warning(
        "No channel saturation parameters available yet. Gregory's MMM model "
        "needs to populate `st.session_state.channel_params` first."
    )
    st.stop()

# -----------------------------------------------------------------------------
# Curve plot
# -----------------------------------------------------------------------------
st.plotly_chart(plot_saturation_curves(channel_params), use_container_width=True)

# -----------------------------------------------------------------------------
# Parameter table
# -----------------------------------------------------------------------------
st.subheader("Fitted Parameters")
param_df = pd.DataFrame(
    [
        {
            "Channel": channel,
            "a (max response)": params.get("a", 0.0),
            "b (saturation rate)": params.get("b", 0.0),
        }
        for channel, params in channel_params.items()
    ]
)

st.dataframe(
    param_df.style.format(
        {
            "a (max response)": "{:,.2f}",
            "b (saturation rate)": "{:.6f}",
        }
    ),
    use_container_width=True,
)

st.caption(
    "**a** is the theoretical maximum conversions a channel can deliver as "
    "spend goes to infinity. **b** controls how quickly the channel reaches "
    "saturation — higher b means the channel saturates faster, so additional "
    "spend has less incremental impact."
)

# -----------------------------------------------------------------------------
# Optional: per-channel inspector
# -----------------------------------------------------------------------------
st.subheader("Channel Inspector")
selected = st.selectbox(
    "Pick a channel to see its marginal-return curve at a chosen spend level:",
    options=list(channel_params.keys()),
    format_func=lambda c: c.replace("_SPEND", "").replace("_", " ").title(),
)

if selected:
    import numpy as np
    import plotly.graph_objects as go

    a = channel_params[selected].get("a", 0.0)
    b = channel_params[selected].get("b", 0.0)

    if b > 0:
        x_max = 6.0 / b
        x = np.linspace(0, x_max, 200)
        marginal = a * b * np.exp(-b * x)
        cumulative = a * (1 - np.exp(-b * x))

        col1, col2 = st.columns(2)
        with col1:
            fig1 = go.Figure(
                go.Scatter(x=x, y=cumulative, mode="lines", name="Cumulative response")
            )
            fig1.update_layout(
                title="Cumulative response",
                xaxis_title="Spend",
                yaxis_title="Predicted conversions",
                template="plotly_white",
                height=350,
            )
            st.plotly_chart(fig1, use_container_width=True)

        with col2:
            fig2 = go.Figure(
                go.Scatter(x=x, y=marginal, mode="lines", name="Marginal return",
                           line=dict(color="orange"))
            )
            fig2.update_layout(
                title="Marginal return (∂conversions / ∂spend)",
                xaxis_title="Spend",
                yaxis_title="Conversions per additional $",
                template="plotly_white",
                height=350,
            )
            st.plotly_chart(fig2, use_container_width=True)
