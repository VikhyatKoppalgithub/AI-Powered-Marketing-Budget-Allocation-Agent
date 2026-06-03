# Setup

> **Owner:** Ana Valderrama  
> **Last updated:** 2026-06-02  
> **Status:** In Progress

## Local setup from zero

1. Install Python 3.11+.
2. Clone the repository and `cd` into the project root.
3. `pip install -r requirements.txt`
4. `cp .env.example .env` and set `GEMINI_API_KEY` (for future agent wiring).
5. `streamlit run app/app.py`
6. Open the **Upload** page; upload `.zip` or `.csv` with MMM columns.

## Gemini API key

1. Go to [Google AI Studio](https://aistudio.google.com/).
2. Create an API key.
3. Paste into `.env` as `GEMINI_API_KEY=...`

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | For agent (later) | Google Generative AI key |

## Running tests

```bash
pytest tests/ -v --tb=short
```

Do not commit `data/raw/`, `data/processed/`, or `.env`.
