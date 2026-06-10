# Architecture

> **Owner:** Ana Valderrama  
> **Last updated:** 2026-06-09  
> **Status:** In Progress

## Data flow

```mermaid
flowchart TB
  user[User]
  upload[zip_handler]
  prep[data_prep]
  backward[backward_analysis]
  guard[guardrails]
  chat[app.py]
  bo[bo_mmm_tuning GP+EI]
  mmm[mmm_model]
  opt[optimizer SLSQP]
  base[baseline]

  user --> upload
  upload --> prep
  prep --> backward
  backward --> opt
  prep --> mmm
  bo --> mmm
  mmm --> opt
  opt --> base
  user --> chat
  chat --> guard
  guard --> chat
```

**Two-stage optimization:** BO tunes MMM hyperparameters offline (`bo_mmm_tuning.py`); SLSQP allocates budget (`optimizer.py`). See [bayesian_optimization_plan.md](bayesian_optimization_plan.md).

## Integration contracts

1. **Ana → Gregory:** `data/processed/mmm_train.csv` (cleaned, adstock, train split)
2. **Ana → Validation:** `data/processed/mmm_test.csv` (holdout, last 3 months per series)
3. **Ana → Meghna:** `BackwardAnalysisResult` with `confirmed_by_user=True`
4. **Ana → Piyush:** `build_system_prompt(phase, turn_index)`
5. **Gregory → Meghna:** `data/processed/channel_params.json` (`a`, `b` per channel); optional BO-tuned `channel_params_bo.json`

## Streamlit session state keys

| Key | Purpose |
|-----|---------|
| `phase` | Workflow phase for prompts |
| `turn_index` | Chat turn counter |
| `conversation_history` | Chat messages |
| `upload_complete` | Upload step done |
| `schema_confirmed` | User confirmed schema |
| `backward_analysis_confirmed` | User confirmed Stage 7 — unlocks optimizer |
| `optimization_complete` | Optimizer finished |
| `cleaned_df` | Processed DataFrame |
| `train_df` / `test_df` | Splits |
| `eda_report` | Plotly EDA dict |
| `raw_path` | Absolute path to saved raw CSV |
| `schema_profile` | `SchemaProfile` dataclass |
| `backward_analysis_result` | Full backward analysis |
| `confirmed_target` / `confirmed_budget` | User form inputs |
| `optim_result` / `channel_params` | Optimizer + MMM outputs for pages 3–5 |
| `optimizer_fn` | Sensitivity wrapper for page 5 |
| `activation_thresholds` | Per-channel κ (USD/week) from `config.yaml` for page 6 |
| `optim_result_B` / `optim_result_C` | Models B/C (pending Meghna Day 1) for page 6 |
| `channel_params_C` / `adstock_lambdas` | Model C curves + decay (pending Gregory) |
