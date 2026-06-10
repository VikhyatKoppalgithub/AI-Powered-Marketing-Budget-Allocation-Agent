# Optimization

> **Owner:** Meghna Advani (draft by Ana)  
> **Last updated:** 2026-06-10  
> **Status:** In Progress

## Objective (plain English)

Maximize total predicted conversions across marketing channels, where each channel’s response follows a saturation curve fitted from historical data.

## Objective (math)

\[
\max \sum_i a_i \left(1 - e^{-b_i x_i}\right)
\]

subject to \(\sum_i x_i \leq B\) and \(x_i \geq 0\).

## KKT conditions (one sentence each)

1. **Stationarity:** Marginal return per channel equals shadow price λ at optimum (or channel is at zero/cap).
2. **Primal feasibility:** Total spend ≤ budget; spends non-negative.
3. **Dual feasibility:** λ ≥ 0.
4. **Complementary slackness:** If budget not fully used, λ = 0; if channel at cap, corresponding multiplier ≥ 0.

## Why SLSQP (not CVXPY)

The objective is smooth nonlinear sums of exponentials; SLSQP in SciPy handles box constraints and equality/inequality constraints without introducing a separate modeling layer. The team standardizes on SciPy for a lighter dependency footprint until Meghna adds CVXPY if needed for extensions.

## Shadow price (non-technical)

λ* is the extra conversions you’d get from one more dollar of total budget at the optimum — the “value of loosening the budget constraint by $1.”

## Models A / B / C (one solver, three configurations)

- **Model A (base):** the objective above — concave, so a single SLSQP solve is globally optimal.
- **Model B (activation):** each channel is OFF ($0) or ON (spend in [κ, u]). The feasible set is non-convex, so we **enumerate all 2⁵ = 32 on/off patterns**, solve a convex subproblem per feasible pattern, and take the best. Global optimum = exhaustive over the discrete part × convex (KKT-verified) inside each.
- **Model C (adstock + activation):** carryover is geometric; at steady state effective spend is `s/(1−λ)`. Evaluating `f_c(s/(1−λ))` is algebraically identical to keeping raw spend and using a steeper rate `b_eff = b/(1−λ)`. So Model C is **Model B run on adstock-adjusted curves** — the same enumeration, gradient, KKT, and shadow-price code path. λ = 0 reduces exactly to Models A/B.

> **Provisional values.** Greg's λ are holdout-selected at portfolio scale, where carryover is weak (only `google_paid_search` λ=0.30; others 0.0) and Model C does not beat Model A. Keys/format are frozen, so refreshing the numbers needs no optimizer change.

*Implementation:* `src/optimizer.py` (`solve`, `solve_with_activation`, `apply_adstock_steady_state`); orchestration in `src/optimization_pipeline.py` (`run_model_b`, `run_model_c`).
