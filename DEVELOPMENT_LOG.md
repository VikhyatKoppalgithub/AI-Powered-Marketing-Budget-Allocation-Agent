# Development Log

## 2026-06-10 — Global-optimality cross-check for Model B/C

**Branch:** feature/agent-chart-explain-threshold-fix  
**Owner:** Meghna Advani  
**Session goal:** Add an independent empirical confirmation that the enumerated Model B/C allocation is globally optimal.

**What was built:**

- `optimizer.py` `cross_check_global_optimum(...)`: randomly samples activation patterns, locally optimizes each with SLSQP, and confirms none beats the enumerated winner. Returns `{enumerated, best_random, gap, relative_gap, patterns_sampled, passed}`. Diagnostic only — not wired into the pipeline or app.
- Tests: 2 cases in `tests/test_optimizer_activation.py` (random search ties enumeration within rounding; a below-optimum claim is flagged as not-passed).
- `docs/optimization.md`: added a "Global-optimality cross-check" subsection.

**What still needs work:**

- Not surfaced in the UI; it's a defense/verification helper run on demand.

**Integration notes:**

- New public function `cross_check_global_optimum` in `src/optimizer.py`. No contract changes.

**How to test it:**

- `pytest tests/test_optimizer_activation.py -q` (13 pass).

## 2026-06-10 — Bug fix: chatbot refused to update thresholds

**Branch:** feature/optimizer  
**Owner:** Meghna Advani  
**Session goal:** Fix the chatbot saying "I can't modify thresholds" when asked "can you change the channel thresholds…".

**What was built:**

- `agent.py` `_looks_like_command`: now recognizes polite imperatives ("can you change/set/lower…", "could you…", "would you…") as commands instead of blocking them as questions. Still rejects polite *explanation* requests ("can you explain how…").
- Bulk "all channels" support: "the channel thresholds to 10M", "all channels", "every channel" parse to the `ALL_CHANNELS` sentinel and apply κ/u_c/λ to every modeled channel. `validate_parameter_change` checks the value against every channel's ceiling/κ and returns an informative message (e.g. "$10M would force those channels permanently OFF").
- Tests: 5 new cases in `tests/test_agent_runtime_params.py` (polite imperative detected, polite explanation not, bulk parse, bulk-above-ceiling rejected, bulk apply writes all channels).

**What still needs work:**

- LLM fallback does not yet emit the bulk sentinel; regex covers the common phrasings.

**Integration notes:**

- New public symbol `ALL_CHANNELS` exported from `src/agent.py`.

**How to test it:**

- `pytest tests/test_agent_runtime_params.py -q` (30 pass). In the app, ask "can you change the meta_facebook threshold to $20k?" → agent confirms; "yes" re-solves.

## 2026-06-10 — Chatbot explains the results charts

**Branch:** feature/optimizer  
**Owner:** Meghna Advani  
**Session goal:** Let the chatbot answer questions about the charts on the Allocation, Curves, and Model Comparison pages.

**What was built:**

- `agent_prompts.py`: `summarize_results_context(session_state)` builds a plain-text digest of the numbers behind every results chart (per-channel recommended vs baseline spend, predicted vs baseline conversions, lift, λ\*, saturation a/b, κ/u_c, and the A/B/C comparison with adstock λ). Returns "" before optimization.
- `build_system_prompt` gained a `results_context` argument; the digest is appended to the system prompt.
- `app/app.py`: chat loop now passes `summarize_results_context(st.session_state)` so the agent can explain any on-screen chart in plain English.
- Tests: 2 new cases in `tests/test_agent_runtime_params.py` (empty before optimization; includes allocation + Model C numbers when present).

**What still needs work:**

- The agent reads numbers, not pixels — it explains the *data* a chart shows, not its visual styling.

**Integration notes:**

- No new session keys; reuses `optim_result`, `optim_result_B/C`, `channel_params`, `activation_thresholds/ceilings`, `adstock_lambdas`.

**How to test it:**

- `pytest tests/test_agent_runtime_params.py -q` (25 pass). In the app, run optimization then ask the chatbot "why is Google Shopping so tall in the allocation chart?".

## 2026-06-10 — Day 1: Model C (adstock + activation) re-solve

**Branch:** feature/optimizer  
**Owner:** Meghna Advani  
**Session goal:** Wire Greg's adstock inputs into the optimizer so Model C re-solves with steady-state effective spend.

**What was built:**

- `optimizer.py`: `apply_adstock_steady_state(params, lambdas)` folds carryover into effective curves (`b_eff = b/(1-λ)`); Model C reuses the existing Model B enumeration unchanged (one code path covers A/B/C). λ=0 is a no-op.
- `optimization_pipeline.py`: `load_model_c_inputs` (reads `channel_params_C.json` + `adstock_lambdas.json`), `run_model_c`; `run_optimization_pipeline` now returns `model_c` too; `apply_optimization_to_session` sets `optim_result_C`, `channel_params_C`, `adstock_lambdas` (Vikhyat's Page 6 keys); `maybe_resolve` re-solves Model C on current λ.
- `config.yaml`: `model_c` block (paths + enabled flag) with PROVISIONAL caveat.
- Copied Greg's `channel_params_C.json` + `adstock_lambdas.json` into `data/processed/`.
- Updated callers in `app/pages/2_backward_analysis.py` and `app/pages/3_allocation.py` to the 5-tuple.
- Tests: adstock bridge math, λ=0 ≡ Model B, invalid λ rejected, carryover lift, `run_model_c`. Full suite **209 passed, 2 skipped**.

**Smoke result (B=$831k):** A=94,085 · B=94,085 · **C=95,076** conversions (carryover lift on paid_search λ=0.30).

**What still needs work:**

- λ values are PROVISIONAL (Greg refreshes once D2 scale locked; keys frozen, no rework).
- Optional: global-optimality cross-check (N random-start full SLSQP vs enumerated winner).

**How to test it:**

```bash
pytest tests/test_optimizer_activation.py tests/test_optimization_pipeline.py -v
```

## 2026-06-10 — Bug fixes: budget scale, KKT false-fail, UX polish

**Branch:** feature/optimizer  
**Owner:** Meghna Advani  
**Session goal:** Fix demo issues surfaced while testing the chat + allocation flow, and add usability polish.

**What was built / fixed:**

- `agent.py`: `detect_parameter_change` now requires an explicit action verb and rejects questions (`_looks_like_command`) — questions like *"if the ceiling is 375K, how did…"* no longer misfire as commands.
- `backward_analysis.py`: detected budget now scales to `mmm.freq` (weekly = `avg_daily × 7`) instead of `× 260`, so the budget matches the weekly curves and κ/u_c.
- `app/pages/1_upload_confirm.py`: Weekly/Monthly/Annual budget toggle (auto-converts to weekly); re-confirm now invalidates cached backward-analysis/optimization results (`_invalidate_downstream`) so a changed budget actually propagates; new "Update budget only" panel reuses the loaded dataset without re-upload.
- `app/pages/2_backward_analysis.py`: fixed `AttributeError` crash from unsafe `st.session_state.backward_analysis_confirmed` access (now `.get(...)`).
- `optimizer.py` (`verify_kkt`): budget-feasibility/caps tolerance now scales with budget magnitude (`max(tol, 1e-6 * max(1, budget))`), eliminating false **KKT fail** caused by sub-cent float rounding at large budgets. `_format_status` reworded ("optimal allocation found" on pass) to drop the misleading "check solver" text.
- `app/app.py`: migrated to `st.navigation`; first tab renamed **"app" → "Chatbot"** (and friendlier titles for all tabs). Session defaults now init on every page load.
- Plain-English "In plain English" expanders added to Backward Analysis, Allocation, Curves, Scenarios, and Model Comparison pages; allocation metrics got tooltips and a KKT-pass gloss.

**How to test it:**

```bash
pytest tests/test_optimizer.py tests/test_agent_runtime_params.py tests/test_backward_analysis.py -v
streamlit run app/app.py   # check Chatbot tab name + budget toggle + KKT pass at $831k
```

## 2026-06-10 — Day 1: Agent runtime parameters (κ/λ/B/u_c) + re-solve

**Branch:** feature/optimizer  
**Owner:** Meghna Advani (assisting Piyush — `agent.py`)  
**Session goal:** Make κ/λ/B/u_c runtime-tunable from chat and re-solve (stakeholder mod v3, parameterization scope).

**What was built:**

- `agent.py`: `parse_parameter_change` (regex) + Claude fallback (`detect_parameter_change`), `validate_parameter_change`, `apply_parameter_change`, confirm/cancel helpers, `process_parameter_message` coordinator; `modify_constraints` intent keywords
- `agent_prompts.py`: `modify_constraints` + `constraint_change_explained` workflow prompts
- `optimization_pipeline.py`: `maybe_resolve()` re-solves Models A/B from session-state params
- `app/app.py`: parameter branch in chat loop + `params_dirty`/`pending_param_change`/ceilings/lambdas session defaults
- Tests: `tests/test_agent_runtime_params.py` (20); full suite 200 passed, 2 skipped

**What still needs work:**

- λ override triggers Model C refit — wire when Greg ships `channel_params_C` + holdout λ
- Vikhyat: optional "current parameters" caption reads `activation_thresholds` / `adstock_lambdas` / `confirmed_budget`

**How to test it:**

```bash
pytest tests/test_agent_runtime_params.py -v
```

## 2026-06-09 — Day 1: Model B activation solver + Ana budget/u_c in config

**Branch:** feature/optimizer  
**Owner:** Meghna Advani  
**Session goal:** Ship 32-pattern activation enumeration (Model B) and lock Ana handoff numbers.

**What was built:**

- `config.yaml`: `default_budget` $831,142/wk, `activation.ceilings` (Ana u_c), `scenario_budget_activation` $90k
- `optimizer.py`: `solve_with_activation`, `solve_activation_kappa_sweep`, `channel_bounds` on `solve()`
- `optimization_pipeline.py`: runs Model B, sets `optim_result_B` in session state
- App pages 2/3 wired for Model B; tests in `test_optimizer_activation.py`

**What still needs work:**

- Model C (adstock + activation) — blocked on Greg `channel_params_C` + `adstock_lambdas`
- Merge Ana `feature/data-prep` when on team remote for `ana_day0_handoff.json` auto-generation

**How to test it:**

```bash
pytest tests/test_optimizer_activation.py tests/test_optimization_pipeline.py -v
```

## 2026-06-09 — Day 0: weekly MMM pipeline + activation κ in config

**Branch:** feature/optimizer  
**Owner:** Meghna Advani  
**Session goal:** Wire stakeholder-mod κ and weekly MMM frequency without changing budget or u_c.

**What was built:**

- `config.yaml`: `mmm.freq: weekly`, `activation.thresholds` (confirmed κ), `optimization.time_unit`
- `optimization_pipeline.py`: `load_activation_thresholds`, weekly `run_fitting`, session `activation_thresholds`
- `mmm_model.py`: `resolve_mmm_freq()` reads config when freq omitted
- `app/app.py`: default `activation_thresholds` session key
- Tests: extended `test_optimization_pipeline.py`, `resolve_mmm_freq` in `test_mmm_model.py`

**What still needs work:**

- `activation.ceilings` (u_c) and `default_budget` — see `docs/optimization_problem_spec.md` §13 (how to decide)
- Model B/C solvers (Day 1)

**How to test it:**

```bash
pytest tests/test_optimization_pipeline.py tests/test_mmm_model.py::test_resolve_mmm_freq_reads_config_default -v
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
