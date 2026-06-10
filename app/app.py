"""
Streamlit Main Entry Point
Owner: Ana Valderrama
Run: streamlit run app/app.py
"""
import sys
from pathlib import Path

# Ensure repo root is importable
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env", override=False)
load_dotenv(ROOT / "app" / ".env", override=False)

import streamlit as st

from src.agent import diagnose_claude_setup, run_agent
from src.agent_prompts import build_system_prompt, extract_company_context
from src.guardrails import GuardrailsService

st.set_page_config(
    page_title="MMM Budget Allocation Agent",
    page_icon="📊",
    layout="wide",
)

defaults = {
    "phase": "upload_request",
    "turn_index": 0,
    "conversation_history": [],
    "upload_complete": False,
    "schema_confirmed": False,
    "backward_analysis_confirmed": False,
    "optimization_complete": False,
    "cleaned_df": None,
    "schema_profile": None,
    "backward_analysis_result": None,
    "company_profile": {},
    "channel_params": None,
    "optim_result": None,
    "optim_result_B": None,
    "optimizer_fn": None,
    "activation_thresholds": {},
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

if "guardrails" not in st.session_state:
    st.session_state.guardrails = GuardrailsService()

st.title("MMM Budget Allocation Agent")
st.caption("MGMT 590-037 · AI-Enhanced Optimization · Purdue University · Summer 2026")
st.caption("Marketing Mix Modeling + Nonlinear Budget Optimization · Powered by Claude")

with st.sidebar:
    st.header("Workflow progress")
    steps = [
        ("upload_request", "1. Upload dataset"),
        ("confirm", "2. Confirm schema"),
        ("analysis", "3. Backward analysis"),
        ("optimize", "4. Optimize"),
        ("explore", "5. Explore results"),
    ]
    phase_done = {
        "upload_request": st.session_state.upload_complete,
        "confirm": st.session_state.schema_confirmed,
        "analysis": st.session_state.backward_analysis_confirmed,
        "optimize": st.session_state.optimization_complete,
        "explore": False,
    }
    for phase_id, label in steps:
        if phase_done.get(phase_id):
            icon = "✅"
        elif st.session_state.phase == phase_id:
            icon = "▶"
        else:
            icon = "○"
        st.markdown(f"{icon} {label}")

    st.divider()
    claude_status = diagnose_claude_setup()
    if claude_status["api_key_configured"]:
        st.success("Claude API key detected")
    else:
        st.warning(
            "No Claude API key found. Add `ANTHROPIC_API_KEY=...` to "
            f"`{claude_status['repo_root']}/.env` and restart."
        )
    st.caption("Upload a .zip or .csv file on the Upload page to begin.")
    if st.button("Go to Upload"):
        st.switch_page("pages/1_upload_confirm.py")

for msg in st.session_state.conversation_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask me about your marketing data..."):
    gr = st.session_state.guardrails.apply_input_guardrails(prompt)

    if gr.action == "block":
        with st.chat_message("assistant"):
            st.warning(st.session_state.guardrails.blocked_response_message(gr.block_reason))
    elif gr.action == "redirect":
        with st.chat_message("assistant"):
            st.info(gr.redirect_message)
    else:
        with st.chat_message("user"):
            st.markdown(gr.sanitized)
        st.session_state.conversation_history.append({"role": "user", "content": gr.sanitized})
        st.session_state.turn_index += 1

        company_context = extract_company_context(
            cleaned_df=st.session_state.get("cleaned_df"),
            schema_profile=st.session_state.get("schema_profile"),
            confirmed_target=st.session_state.get("confirmed_target"),
            confirmed_budget=st.session_state.get("confirmed_budget"),
            backward_analysis_result=st.session_state.get("backward_analysis_result"),
            company_profile=st.session_state.get("company_profile"),
        )
        system_prompt = build_system_prompt(
            phase=st.session_state.phase,
            turn_index=st.session_state.turn_index,
            company_context=company_context,
        )

        agent_context = {
            "phase": st.session_state.phase,
            "upload_complete": st.session_state.upload_complete,
            "schema_confirmed": st.session_state.schema_confirmed,
            "backward_analysis_confirmed": st.session_state.backward_analysis_confirmed,
            "optimization_complete": st.session_state.optimization_complete,
            "company_context": company_context,
        }
        raw_response = run_agent(
            user_message=gr.sanitized,
            system_prompt=system_prompt,
            conversation_history=st.session_state.conversation_history,
            context=agent_context,
        )

        clean_response = st.session_state.guardrails.apply_output_guardrails(raw_response)

        with st.chat_message("assistant"):
            st.markdown(clean_response)
        st.session_state.conversation_history.append(
            {"role": "assistant", "content": clean_response}
        )
