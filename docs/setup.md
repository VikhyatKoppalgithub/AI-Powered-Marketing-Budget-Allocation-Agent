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

## Running tests

```bash
pytest tests/ -v --tb=short
```

Do not commit `data/raw/`, `data/processed/`, or `.env`.
