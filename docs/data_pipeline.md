# Data Pipeline

> **Owner:** Ana Valderrama  
> **Last updated:** 2026-06-02  
> **Status:** In Progress

## Eleven cleaning steps (plain English)

1. **Load raw CSV** — Parse dates; reject negative spend.
2. **Remove duplicates** — Fail on exact or `(timeseries, date)` key duplicates.
3. **Normalize currency** — Convert spend/revenue to USD via `fx_rates`; keep original code.
4. **Fill vertical nulls** — Forward-fill org verticals; remaining → `"Unknown"`.
5. **Handle spend nulls** — Modeled channels → 0; drop sparse columns (display, video, meta_other, tiktok).
6. **Validate non-negative spend** — Hard fail if any spend &lt; 0.
7. **Winsorize** — Cap each channel at 99th percentile per timeseries.
8. **Fill date gaps** — Complete daily index; spend = 0; conversions left NaN on gap days.
9. **Adstock** — Geometric decay per channel per series; adds `{channel}_adstock`.
10. **Aggregate channels** — `google_spend`, `meta_spend`; target → `y`.
11. **Export + split** — Write `mmm_ready.csv`, EDA report, `mmm_train.csv` / `mmm_test.csv`.
12. **Weekly handoff** — Compute weekly spend stats and u_c ceilings (1.5 × max weekly spend per channel), then write `weekly_handoff.json` and `weekly_stats.json` for the MMM fit (weekly scale), optimizer budget $B$, ceilings, and κ activation thresholds. Logic lives in `src/weekly_stats.py` and runs automatically inside `run_pipeline()`; `python src/weekly_stats.py` prints the same numbers as a report.

## Train/test split rationale

Hold out the **last 3 calendar months per `MMM_TIMESERIES_ID`** so each series has its own cutoff and there is no leakage into training. Short series (&lt; ~3 months of days) use the last 20% of dates as test.

## Dataset quality findings

- **Granularity:** Daily, 143 timeseries (Conjura reference dataset).
- **Nulls:** Spend nulls mean inactive channel; filled with 0. Verticals ~16% null.
- **Modeled (5):** google_paid_search, google_shopping, google_pmax, meta_facebook, meta_instagram — nulls filled with 0.
- **Dropped (4):** google_display, google_video, meta_other, tiktok — columns removed (too sparse; meta_instagram is modeled despite ~80% null).
- **Currencies:** 14 codes normalized to USD via static ECB-style rates in `config.yaml`.

See [setup.md](setup.md) for running the pipeline locally.
