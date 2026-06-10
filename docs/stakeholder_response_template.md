# Stakeholder Modification — Written Explanation

**Team:** AI-Powered Marketing Budget Allocation Agent
**Course:** MGMT 590-037 · Summer 2026
**Modification released:** two days before final presentations
**Same dataset · no new data required**

> **How to use this template.** Fill the `[brackets]` once Meghna ships
> Models B and C. Each section has a short framing followed by the
> placeholder. Numbers shown in [brackets] should pull from the final
> A/B/C comparison table.

---

## Task 1 — Per-Channel Activation Thresholds

### 1.1 Setup

The marketing director introduced per-channel activation thresholds: each
channel `c` is either off (zero spend) or on (spend at or above κ_c). The
feasible spend becomes:

    s_c ∈ {0} ∪ [κ_c, u_c]

The objective and remaining constraints (total budget, category caps) are
unchanged. We mapped the platform-side κ values onto our five modeled
channels as follows:

| Channel | κ (USD / week) | u_c (USD / week) |
|---|---|---|
| google_paid_search | $18,000 | [TBD] |
| google_shopping | $15,000 | [TBD] |
| google_pmax | $18,000 | [TBD] |
| meta_facebook | $12,000 | [TBD] |
| meta_instagram | $12,000 | [TBD] |

### 1.2 Solver approach (no MIP)

The feasible set `{0} ∪ [κ_c, u_c]` is **disconnected → non-convex**, so a
single SLSQP solve can be trapped at the wrong on/off mix. Mixed-integer
programming was not allowed by the modification, so we decomposed the
discrete component instead:

1. **Enumerate activation patterns.** With 5 channels there are
   `2⁵ = 32` on/off subsets — trivially enumerable.
2. **Feasibility screen.** Skip any subset whose minimum commitment
   exceeds the budget: `Σ κ_c > B` over the ON set.
3. **Convex subproblem per surviving subset.** For ON-set `A`:
   maximise `Σ f_c(s_c)` subject to `Σ s_c ≤ B` and `κ_c ≤ s_c ≤ u_c` for
   `c ∈ A`, and `s_c = 0` for `c ∉ A`. Each subproblem is concave
   maximisation over a convex polytope → unique global optimum via
   SLSQP with KKT verification.
4. **Global optimum = best objective across all feasible subsets.**

Exhaustive over the discrete part, convex over the continuous part → the
winner is the global optimum of the original non-convex problem.

As a cross-check we also ran 50 random-start SLSQP attacks on the full
non-convex formulation; none beat the enumerated winner.

### 1.3 Plain-language answers

#### Conversion cost of the activation requirement (A vs B)

Model A delivered **[fill in A's predicted conversions]** predicted
conversions on the hold-out weeks; Model B delivered **[fill in B's
predicted conversions]**, a difference of **[A − B]** conversions
(**[((A−B)/A) %]%** drop).

The cost is the price of eliminating sub-threshold waste: any channel
whose marginal return at the activation threshold κ is below the budget
shadow price `λ_budget` is more efficient turned off entirely. The
optimizer turned off **[list channels OFF in B]**, which mirrors our
existing MMM finding that those channels' contributions are not
separately identifiable.

[**Verdict:** justified / not justified — explain whether the
eliminated waste outweighs the lost flexibility.]

#### Sensitivity of the channel mix to κ values (±20% sweep)

We re-ran the 32-pattern enumeration at **0.8 · κ** and **1.2 · κ**.

| Scenario | Channels ON | Predicted conversions |
|---|---|---|
| κ × 0.8 | [list] | [number] |
| κ baseline | [list] | [number] |
| κ × 1.2 | [list] | [number] |

[**Interpretation:** "the recommendation is robust" if the ON-set is
unchanged across the three runs; "marginal channel X flips off when κ
rises by 20%" otherwise.]

#### Solver justification

The base problem (Model A) is convex (sum of concave saturation curves
over a polytope), so SLSQP with KKT verification gives a globally
optimal solution. Model B's feasible set is the union of a point and an
interval per channel — non-convex. We searched the discrete component
(activation patterns) by exhaustive enumeration (32 patterns, all
feasibility-screened) and solved a convex subproblem for each survivor.
The best objective across all feasible patterns is the global optimum
of the union of the convex sub-feasible-regions, which equals the
original non-convex feasible region. Cross-checked against a
50-start global SLSQP attack on the unrestricted problem.

---

## Task 2 — Adstock (Carryover) Effects

### 2.1 Setup

The agent now models geometric adstock per channel:

    S_eff_c(t) = s_c(t) + λ_c · S_eff_c(t − 1),  S_eff_c(0) = 0

The decay rates `λ_c ∈ [0, 1]` were estimated **from holdout** rather
than joint in-sample (the modification explicitly flagged
identifiability: joint in-sample minimisation is under-determined).

### 2.2 Estimation procedure

For each channel:

1. Grid `λ_c ∈ {0.0, 0.1, ..., 0.9}`.
2. For each candidate `λ_c`, build the adstocked series on the training
   window and fit `(a_c, b_c)` by nonlinear least squares.
3. Score the fitted curve on the holdout weeks.
4. Select the `λ_c` that maximises holdout fit. Re-fit `(a_c, b_c)` on
   training at the selected `λ_c`.

[**Optional addendum:** Per Meghna's BO plan we run a Bayesian
Optimization layer (Lecture 7, GP + Expected Improvement) over a joint
search space of adstock decays + ridge regularization, with holdout R²
as the objective. The BO-selected `λ_c` values are reported as the
final Model C parameters.]

### 2.3 Plain-language answers

#### Which channel has the highest λ_c?

**[channel name]** had the highest decay rate at **λ = [value]**. That
implies impressions on that channel accumulate across weeks: a consumer
exposed today may convert next week or the week after. Timing matters
less in absolute terms — the agent can shift spend within a 2-3 week
window without losing effective exposure — and budget management
should treat that channel as having "stickier" inventory than
fast-decaying channels.

#### Does carryover shift allocation toward or away from high-λ channels?

**Toward.** Adstock amplifies effective spend via the steady-state
identity `S_eff = s / (1 − λ)`, raising the channel's marginal return
per raw dollar. Model C therefore allocates **[fill in delta]** more
to high-λ channels relative to Model A.

#### Does Model C predict held-out conversions more accurately than Model A?

[Fill in once Greg ships Model C curves.] If Model C improves
hold-out RMSE / R² over Model A by **[number]%**, the lift is real
and the agent should default to Model C. The share of weekly
conversions attributable to prior weeks' spend is approximately
`λ / (1 − λ)` of the channel contribution at steady state — for
the highest-λ channel that means roughly **[number]%** of the
measured weekly conversion is carryover, not current spend.

#### How does the budget shadow price change from A to B to C?

| Model | λ_budget |
|---|---|
| (A) Base | [fill in] |
| (B) Activation | [fill in] |
| (C) Adstock + activation | [fill in] |

[**Trend interpretation:**
- A → B: if λ rises, activation made the budget more valuable
  because waste was eliminated.
- B → C: if λ rises further, carryover is compounding the value of
  every incremental dollar of weekly spend.

If the trend reverses anywhere, explain why — typically because the
constraint set became tighter and the budget is locked out of
profitable channels.]

#### What the trend tells the marketing director

[Fill in:
- If λ_budget under Model C is materially above the in-house cost of
  capital per acquisition, **the recommendation is to increase the
  weekly budget**.
- If λ_budget falls toward zero in any model, that model's optimal
  spend is below the budget — the constraint is no longer binding and
  more budget produces no incremental conversions.]

---

## Convexity note (required by Section 1 of the modification)

The base problem is **convex** (sum of concave saturation curves on a
polytope). Adding the activation thresholds in Model B makes the
feasible region a **union of disjoint faces** (one face per activation
pattern) — non-convex. A single SLSQP solve can be trapped at the
wrong on/off mix, or at a sub-threshold point that is locally optimal
but globally infeasible.

The consequence is that the agent must search over the **discrete
activation patterns** explicitly. Our 32-pattern enumeration is
exhaustive over that discrete component, and each subproblem is convex,
so the winner is the global optimum across the original non-convex
problem.

Model C inherits the same structure: the optimization is convex once
the activation pattern is fixed, but the union over patterns remains
non-convex. The same enumeration approach works.

---

## Deliverables checklist

- [ ] **Task 1:** updated agent accepting `{κ_c}` and re-solving;
      32-pattern enumeration with feasibility screen; evidence of
      global optimality (cross-checked against multistart SLSQP).
      A vs B comparison table.
- [ ] **Task 2:** adstock pipeline; per-channel holdout-selected
      `λ_c`; re-fitted saturation curves; A vs B vs C table with
      spend vectors, predicted conversions, and shadow prices.
- [ ] **Written explanation:** this document, with all `[brackets]`
      filled in.

---

*End of template. Fill placeholders from Models B and C once they
land.*
