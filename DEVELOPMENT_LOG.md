# Development Log

## 2026-06-06 — Gemini → Claude API migration

**Branch:** main  
**Owner:** Piyush Sandhikar  
**Session goal:** Replace Google Gemini with Anthropic Claude across the agent and explainer.

**What was built:**

- `src/agent.py` now uses `anthropic` (`get_claude_client`, `call_claude`, `run_agent`)
- `src/explainer.py` uses `call_claude()` for allocation explanations
- `requirements.txt`: `google-generativeai` replaced with `anthropic`
- `config.yaml` provider set to `anthropic`; default model `claude-sonnet-4-20250514`
- `.env.example`, tests, README, and `docs/setup.md` updated for `ANTHROPIC_API_KEY`

**What still needs work:**

- Live end-to-end chat validation with a real Anthropic key

**Integration notes:**

- Env var is now `ANTHROPIC_API_KEY` (legacy `API_Key` still accepted as fallback)
- Optional override: `ANTHROPIC_MODEL`
- `call_claude(messages, system_prompt=...)` is shared by agent chat and explainer

**How to test it:**

```bash
pip install -r requirements.txt
pytest tests/test_agent.py tests/test_explainer.py -v --tb=short
cp .env.example .env   # set ANTHROPIC_API_KEY
streamlit run app/app.py
```

## 2026-06-06 — Gemini agent wiring

**Branch:** main  
**Owner:** Piyush Sandhikar  
**Session goal:** Implement `agent.py`, connect Gemini to the Streamlit chat, and add agent tests.

**What was built:**

- `get_gemini_client()`, `parse_problem()`, `run_agent()`, `run_benchmark()` in `src/agent.py`
- Streamlit chat now calls `run_agent()` with workflow context from session state
- `tests/test_agent.py` (mocked Gemini) and `test_agent_responds_in_scope` integration smoke test
- README / `docs/agent_design.md` status updates for the agent module

**What still needs work:**

- Live Gemini benchmark runs with a real `GEMINI_API_KEY` (optional)
- End-to-end chat validation once optimization pages are fully wired

**Integration notes:**

- `run_agent(user_message, system_prompt, conversation_history, context=None)` is the chat contract
- `context` should include `phase`, `upload_complete`, `schema_confirmed`, `backward_analysis_confirmed`
- Optimization questions are blocked in-agent until `backward_analysis_confirmed` is true

**How to test it:**

```bash
pytest tests/test_agent.py tests/test_integration.py::test_agent_responds_in_scope -v --tb=short
cp .env.example .env   # set GEMINI_API_KEY for live Gemini replies
streamlit run app/app.py
```

## 2026-06-05 — Optimizer implementation (SLSQP + KKT)

**Branch:** feature/optimizer  
**Owner:** Meghna Advani  
**Session goal:** Implement `optimizer.py` with multistart SLSQP, KKT verification, and tests consuming Gregory's `channel_params.json`.

**What was built:**

- `src/optimizer.py`: `objective`, `gradient`, `predicted_conversions`, `verify_kkt`, `solve`, `solve_from_file`, `load_params`
- Multistart SLSQP (config `n_starts`, `tol`, `max_iter`); budget + non-negativity + optional caps
- Shadow price `lambda_budget` from active-channel marginals
- `tests/test_optimizer.py` (14 tests); integration tests for budget + KKT un-skipped

**What still needs work:**

- `baseline.py` stub
- Wire `solve()` into Streamlit page 3 (Vikhyat)
- Update `optimization.default_budget` to portfolio-scale (~$3.5M) after team sign-off

**Integration notes:**

- Expects Gregory's JSON keys = `config["channels"]["modeled"]` with `{"a", "b"}` per channel
- `solve(params, budget, channels)` returns unified `OptimResult` for Piyush + Vikhyat
- Aligned field names with Vikhyat's pages (`predicted_conversions`, `status`, etc.); explainer imports shared dataclass

**How to test it:**

```bash
pytest tests/test_optimizer.py tests/test_integration.py::test_optimizer_budget_constraint_holds -v --tb=short
python -c "from src.optimizer import load_params, solve; p=load_params('data/processed/channel_params.json'); print(solve(p, 3_500_000, list(p.keys())))"
```

## 2026-06-02 — Ana MVP skeleton

**Branch:** feature/data-prep  
**Owner:** Ana Valderrama  
**Session goal:** Scaffold the team repo and implement Ana's MVP (data pipeline, upload, backward analysis, guardrails, Streamlit, tests).

**What was built:**

- Full `config.yaml`, `requirements.txt`, `.gitignore`, `.env.example`
- `src/data_prep.py`, `zip_handler.py`, `backward_analysis.py`, `guardrails.py`, `agent_prompts.py`
- Teammate stubs: `mmm_model`, `optimizer`, `baseline`, `agent`, `explainer`
- Streamlit `app/app.py` + pages 1–2; pages 3–5 stubbed with optimization gate
- Tests for Ana modules (synthetic fixtures); integration smoke tests
- Notebooks `01_eda.ipynb`, `02_preprocessing.ipynb`
- Docs: architecture, data_pipeline, backward_analysis, agent_design, setup, optimization (draft)

**What still needs work:**

- Wire Gemini in `agent.py` (Piyush)
- MMM fitting and optimizer (Gregory, Meghna)
- Allocation and viz pages (Vikhyat)
- End-to-end test when all modules land

**Integration notes:**

- `run_pipeline(raw_path=...)` must be called after `confirm_and_save`
- Target column renamed to `y` after `aggregate_channels`; backward analysis checks both
- Optimization blocked until `st.session_state.backward_analysis_confirmed == True`

**How to test it:**

```bash
pytest tests/ -v --tb=short
streamlit run app/app.py
```
