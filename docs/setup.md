# Setup

> **Owner:** Ana Valderrama  
> **Last updated:** 2026-06-09  
> **Status:** In Progress

## Local setup from zero

1. Install Python 3.11+.
2. Clone the repository and `cd` into the project root.
3. `pip install -r requirements.txt`
4. `cp .env.example .env` and set `ANTHROPIC_API_KEY` (required for live Claude chat replies).
5. `streamlit run app/app.py`
6. Open the **Upload** page; upload `.zip` or `.csv` with MMM columns.

## Anthropic API key

1. Go to [Anthropic Console](https://console.anthropic.com/).
2. Create an API key.
3. Paste into `.env` as `ANTHROPIC_API_KEY=...`

Optional: override the default model with `ANTHROPIC_MODEL=claude-sonnet-4-20250514`.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | For agent + explainer | Anthropic API key |
| `ANTHROPIC_MODEL` | No | Claude model name (defaults to `config.yaml`) |

## Optional: Bayesian Optimization for MMM tuning (offline)

See [bayesian_optimization_plan.md](bayesian_optimization_plan.md). After the data pipeline produces train/test CSVs:

1. Set `mmm_tuning.enabled: true` in `config.yaml`
2. Run `python -m src.bo_mmm_tuning` (~30 MMM refits)
3. Set `mmm_tuning.use_bo_params: true` to load `channel_params_bo.json` in the app

## Running tests

```bash
pytest tests/ -v --tb=short
```

Do not commit `data/raw/`, `data/processed/`, or `.env`.
