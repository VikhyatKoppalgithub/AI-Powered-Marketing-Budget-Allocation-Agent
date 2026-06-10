# Development Log

## 2026-06-09 — Day-0 data deliverable: weekly stats, u_c ceilings, and team handoff

**Branch:** feature/data-prep  
**Owner:** Ana Valderrama  
**Session goal:** Deliver the Day-0 data layer — weekly spend statistics, channel ceilings, and the handoff artifacts Greg and Meghna need to start the MMM fit and Model B.

**What was built:**

- `src/weekly_stats.py` — Ana's permanent data-layer module alongside `data_prep.py`, owning `compute_weekly_stats()` (per-channel weekly min/median/max, B_raw, train/holdout week counts, weekly y mean), `compute_uc_ceilings()` (u_c = 1.5 × max weekly spend per channel, flags any channel where u_c < κ), `scale_decision()` (D2 mid-market scaling), `write_handoff()`, and the `KAPPA` / `KAPPA_SUM` / `B_TARGET` / `B_SCENARIO_ACTIVATION` constants
- `run_pipeline()` integration — every pipeline run automatically computes weekly stats and u_c ceilings and writes the handoff JSON; return dict includes `weekly_stats`, `uc_result`, `handoff`, `verification`
- Handoff outputs — `data/processed/ana_day0_handoff.json` with `uc_ceilings`, `B_portfolio` ($831,142/wk), `B_scenario_activation` ($90,000), κ map, and per-channel weekly stats for Meghna and Greg; plus `weekly_stats.json` and `weekly_scaled_spend.csv` (when scale factor < 1)
- `verify_pipeline_outputs()` — column presence (DATE_DAY, 5 spend, 5 adstock, y), >5% null flags, and all-USD currency checks on pipeline outputs
- CLI report — `python src/weekly_stats.py` prints verification, weekly stats table, u_c ceiling table, Portfolio B recommendation, scale decision, and adstock ownership boundary
- Tests — `tests/test_weekly_stats.py`: 15 tests on synthetic DataFrames, all passing

**What still needs work:**

- Real-data run flags >5% nulls in non-modeled CLICKS/IMPRESSIONS columns — informational, not blocking

**Integration notes:**

- Greg: reads `train_weeks` / `holdout_weeks` / `weekly_y_mean` and per-channel weekly stats from the handoff JSON for the weekly MMM fit scale
- Meghna: pastes `uc_ceilings` into config `activation.ceilings` and `B_portfolio` into `optimization.default_budget`; all 5 channels have u_c ≥ κ, so no channel is forced always-OFF in Model B at real scale; `B_scenario_activation` ($90k) is available for the activation write-up

**How to test it:**

```bash
pytest tests/test_weekly_stats.py -v
python src/weekly_stats.py
```

## 2026-06-09 — Bayesian Optimization for MMM tuning (Stage 1)

**Branch:** feature/optimizer  
**Owner:** Meghna Advani  
**Session goal:** Implement Lecture 7 BO (GP + EI) for MMM hyperparameters without replacing SLSQP allocation.

**What was built:**

- `src/bo_mmm_tuning.py`: GP + EI loop, `evaluate_mmm_hyperparams`, `run_bo_tuning`, `load_bo_params`
- `mmm_model.py`: `reg_b_weight`, `adstock_decay_overrides`, optional BO output path
- `config.yaml`: `mmm_tuning` block; `optimization_pipeline` loads BO params when `use_bo_params: true`
- Tests: `tests/test_bo_mmm_tuning.py`
- Docs: `optimization_problem_spec.md` §12, `architecture.md`, plan status updated

**What still needs work:**

- Offline BO run on full dataset (~30 refits); set `mmm_tuning.enabled: true` manually
- Optional notebook `03_bo_mmm_tuning.ipynb` for demo charts
- `tune_decays: true` uses adstock spend for fit — document if enabled

**How to test it:**

```bash
pytest tests/test_bo_mmm_tuning.py -v
# After pipeline: enable mmm_tuning.enabled in config.yaml
python -m src.bo_mmm_tuning
```

## 2026-06-09 — Implement baseline lift (historical + equal)

**Branch:** feature/optimizer  
**Owner:** Meghna Advani  
**Session goal:** Populate `baseline_allocation`, `baseline_conversions`, and `lift_pct` on OptimResult for Page 3.

**What was built:**

- `src/baseline.py`: historical proportional baseline, equal split, `compute_lift`, `apply_baseline_to_result`, `run_all_baselines`
- `optimization_pipeline.py`: attaches baseline after `solve()` using train split
- Page 3 backfills baseline for older session results; pages pass `train_df`
- `tests/test_baseline.py`: 7 tests (removed skip marker)

**How to test it:**

```bash
pytest tests/test_baseline.py tests/test_optimization_pipeline.py -v
streamlit run app/app.py  # Step 2 confirm → Step 3 shows non-zero lift
```

## 2026-06-09 — Fix Step 2 freeze (chart subsampling)

**Branch:** feature/optimizer  
**Owner:** Meghna Advani  
**Session goal:** Stop Streamlit from freezing after backward analysis on large datasets.

**What was built:**

- `backward_analysis.py`: subsample scatter plots to 2,000 points per channel; `strip_stage_charts()` after confirm
- `2_backward_analysis.py`: collapse expanders, hide charts post-confirm, `st.status` during MMM + optimizer

**What still needs work:**

- Re-upload or clear session if an old run still has full-size charts cached in memory

**How to test it:**

```bash
streamlit run app/app.py
# Step 2 should scroll smoothly; confirm shows status spinner ~15–20s then Step 3 works
```

## 2026-06-09 — Wire optimizer after backward analysis confirm

**Branch:** feature/optimizer  
**Owner:** Meghna Advani  
**Session goal:** Fix dead-end after Step 2 — run MMM fitting and SLSQP when the user confirms backward analysis.

**What was built:**

- `app/pages/2_backward_analysis.py`: confirm button now runs `run_fitting()` → `solve()`, sets `channel_params`, `optim_result`, `optimizer_fn`, and `optimization_complete` in session state
- `app/app.py`: session defaults for optimizer keys; sidebar labels updated
- README status table: Streamlit end-to-end flow marked complete

**What still needs work:**

- `baseline.py` still stub — lift metrics on page 3 stay at 0 until implemented
- Budget label on upload form says “annual” but optimizer uses the raw dollar value

**Integration notes:**

- Pages 3–5 read `st.session_state.optim_result` and `channel_params` — populated on Step 2 confirm
- `optimizer_fn` wrapper returns dict for Vikhyat’s `run_sensitivity`

**How to test it:**

```bash
streamlit run app/app.py
# Complete Step 1 → Step 2 → Confirm and run optimization → View Step 3
pytest tests/ -v --tb=short
```

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
