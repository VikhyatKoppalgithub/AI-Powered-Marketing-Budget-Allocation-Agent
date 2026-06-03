# Backward Analysis

> **Owner:** Ana Valderrama  
> **Last updated:** 2026-06-02  
> **Status:** In Progress

## Seven stages (plain English)

| Stage | What it does | Chart/output |
|-------|----------------|--------------|
| 1 Outcome | Identifies target (`y` / `ALL_PURCHASES`) | Target time series |
| 2 Channels | Usable vs sparse spend columns | Coverage bar chart |
| 3 Spend–response | Correlations spend vs conversions | Scatter grid |
| 4 Saturation | Concavity / diminishing returns | Fitted curves |
| 5 Objective | States maximize Σ saturation terms | Text only |
| 6 Constraints | Budget cap, non-negativity, soft caps | Historical allocation bar |
| 7 Confirmation | Summary for user sign-off | Text only |

## Why confirm at Stage 7?

Optimization changes real budget decisions. Stage 7 forces the user to agree on the **objective and constraints inferred from their data** before `optimizer.solve()` runs. The app sets `backward_analysis_confirmed` only after the confirm button; page 3 calls `st.stop()` until then.
