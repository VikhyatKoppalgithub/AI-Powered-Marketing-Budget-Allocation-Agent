"""
Page 3 — Budget allocation + optimization results
Owner: Vikhyat Koppal (implements this page)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

st.header("Step 3: Optimal Budget Allocation")

if not st.session_state.get("backward_analysis_confirmed"):
    st.warning("Complete the backward analysis and confirm your setup first (Step 2).")
    st.stop()

st.info("This page will be implemented by Vikhyat once Meghna's optimizer is connected.")
# TODO (Vikhyat): budget slider → solve() → plot_allocation_bar() → KKT shadow price display
