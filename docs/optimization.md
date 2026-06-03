# Optimization

> **Owner:** Meghna Advani (draft by Ana)  
> **Last updated:** 2026-06-02  
> **Status:** Draft

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

*Implementation:* `src/optimizer.py` (stub — Meghna).
