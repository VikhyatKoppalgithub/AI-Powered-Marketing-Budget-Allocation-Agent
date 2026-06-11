# MMM Budget Allocation Agent

**MGMT 590-037 · AI-Enhanced Optimization · Purdue University · Summer 2026**

**Team:** Ana Valderrama, Gregory Sapp, Meghna Advani, Piyush Sandhikar, Vikhyat Koppal

## Problem statement

Marketing teams spread budget across channels (Google, Meta, etc.) without knowing which allocation maximizes conversions. This agent ingests daily MMM-style spend and conversion data, cleans and profiles it, walks users through a backward analysis to define the optimization problem, and (when complete) allocates budget using saturation curves and constrained nonlinear optimization—with an AI guide scoped strictly to marketing analytics.

## Technology stack

- **Python** 3.11+
- **Data:** pandas, numpy, scipy, scikit-learn
- **UI:** Streamlit, Plotly
- **LLM:** Anthropic Claude (`anthropic`) — wired in `agent.py` with graceful fallback when no API key
- **Config:** PyYAML, python-dotenv
- **Testing:** pytest, pytest-cov

## Project folder structure

```
AI-Powered-Marketing-Budget-Allocation-Agent/
├── app/
│   ├── app.py
│   └── pages/
│       ├── 1_upload_confirm.py
│       ├── 2_backward_analysis.py
│       ├── 3_allocation.py
│       ├── 4_curves.py
│       └── 5_scenarios.py
├── config.yaml
├── data/raw/                        (gitignored uploads)
├── data/processed/                  (gitignored outputs)
├── docs/
│   ├── architecture.md
│   ├── data_pipeline.md
│   ├── optimization.md
│   ├── backward_analysis.md
│   ├── agent_design.md
│   ├── setup.md
│   ├── optimization_problem_spec.md
│   └── bayesian_optimization_plan.md
├── notebooks/
│   ├── 01_eda.ipynb
│   └── 02_preprocessing.ipynb
├── report/
│   ├── final_report.tex
│   └── final_report.docx
├── src/
│   ├── data_prep.py
│   ├── weekly_stats.py
│   ├── zip_handler.py
│   ├── backward_analysis.py
│   ├── guardrails.py
│   ├── agent_prompts.py
│   ├── mmm_model.py
│   ├── optimizer.py
│   ├── baseline.py
│   ├── bo_mmm_tuning.py
│   ├── optimization_pipeline.py
│   ├── agent.py
│   └── explainer.py
├── tests/
├── requirements.txt
├── .env.example
├── DEVELOPMENT_LOG.md
└── README.md
```

## How to set up locally

```bash
git clone <repo-url>
cd AI-Powered-Marketing-Budget-Allocation-Agent
pip install -r requirements.txt
cp .env.example .env    # add ANTHROPIC_API_KEY when using the agent
streamlit run app/app.py
```

See [docs/setup.md](docs/setup.md) for full setup steps. BO details: [docs/bayesian_optimization_plan.md](docs/bayesian_optimization_plan.md).

## How to run tests

```bash
pytest tests/ -v --tb=short
```

Expected: Ana + optimizer tests pass; remaining stub tests skipped. Coverage target: 70% on `data_prep`, `zip_handler`, `backward_analysis`, `guardrails`, `agent_prompts`.

## Current implementation status

| Module | Owner | Status |
|--------|-------|--------|
| data_prep | Ana | Complete |
| weekly_stats | Ana | Complete |
| zip_handler | Ana | Complete |
| backward_analysis | Ana | Complete |
| guardrails | Ana | Complete |
| agent_prompts | Ana | Complete |
| Streamlit (upload → analysis → optimize → results) | Ana + Meghna | Complete |
| mmm_model | Gregory | Complete |
| optimizer | Meghna | Complete |
| baseline | Meghna | Complete |
| bo_mmm_tuning | Meghna | Complete |
| agent (Claude) | Piyush | Complete |
| explainer + viz pages | Vikhyat | Complete |

## Team roles

| Member | Role | Files owned |
|--------|------|-------------|
| Ana Valderrama | Data engineering + agent skeleton | `data_prep`, `zip_handler`, `backward_analysis`, `guardrails`, `agent_prompts`, `app/app.py`, `pages/1_*`, `pages/2_*` |
| Gregory Sapp | MMM / prediction | `mmm_model.py` |
| Meghna Advani | Optimization | `optimizer.py`, `baseline.py`, `bo_mmm_tuning.py` |
| Piyush Sandhikar | AI agent | `agent.py` |
| Vikhyat Koppal | Viz / sensitivity | `explainer.py`, `pages/3_*`–`5_*` |

## Integration contracts

| From | To | Interface |
|------|-----|-----------|
| Ana | Gregory | `data/processed/mmm_train.csv` |
| Ana | Greg + Meghna | `data/processed/weekly_handoff.json` + `weekly_stats.json` (written automatically by `run_pipeline()`; printable report via `python src/weekly_stats.py`) |
| Ana | Validation | `data/processed/mmm_test.csv` |
| Ana | Meghna | `BackwardAnalysisResult` (confirmed objective + constraints) |
| Ana | Piyush | `build_system_prompt(phase, turn_index)` |
| Ana | All | `GuardrailsService` on every chat message |
| Gregory | Meghna | `data/processed/channel_params.json` |
| Meghna | Piyush + Vikhyat | `OptimResult` |

See [docs/architecture.md](docs/architecture.md) for data flow and session state keys.

## Development log

Session-by-session progress: [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)
