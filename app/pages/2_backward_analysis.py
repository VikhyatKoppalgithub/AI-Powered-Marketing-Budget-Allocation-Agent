"""
Page 2 — 7-stage backward analysis
Owner: Ana Valderrama
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from src.backward_analysis import run_backward_analysis

st.header("Step 2: Backward Analysis")
st.markdown(
    """
Before optimizing, we work **backward from your observed outcomes** to understand
what your data is telling us — identifying your objective function and
constraints from the data itself.
"""
)

if not st.session_state.get("schema_confirmed"):
    st.warning("Complete Step 1 first.")
    st.stop()

df = st.session_state.get("cleaned_df")
if df is None:
    st.error("No dataset in session. Please re-upload.")
    st.stop()

if st.session_state.get("backward_analysis_result") is None:
    with st.spinner("Running backward analysis..."):
        result = run_backward_analysis(
            df=df,
            user_budget=st.session_state.get("confirmed_budget"),
        )
    st.session_state.backward_analysis_result = result
else:
    result = st.session_state.backward_analysis_result

for stage in result.stages:
    with st.expander(f"**{stage.title}**", expanded=True):
        st.markdown(stage.finding)
        st.caption(stage.technical_detail)
        if stage.chart is not None:
            st.plotly_chart(stage.chart, use_container_width=True)

st.divider()
st.subheader("Confirm your optimization setup")
st.markdown(result.objective_function_text)
st.code(result.objective_function_math, language="text")
for c in result.constraint_text:
    st.markdown(f"- {c}")

if not st.session_state.backward_analysis_confirmed:
    if st.button("Confirm and allow optimization to run"):
        result.confirmed_by_user = True
        st.session_state.backward_analysis_result = result
        st.session_state.backward_analysis_confirmed = True
        st.session_state.phase = "optimize"
        st.success(
            "Setup confirmed. The optimizer is now unlocked. "
            "Proceed to Step 3: Allocation when Meghna's optimizer is connected."
        )
else:
    st.success("Analysis confirmed. Optimization is unlocked.")
