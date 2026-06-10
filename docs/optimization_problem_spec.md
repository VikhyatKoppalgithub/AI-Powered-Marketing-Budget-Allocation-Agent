# Optimization Problem Specification

> **Owner:** Meghna Advani  
> **Last updated:** 2026-06-03  
> **Status:** Final (for current dataset: `data/raw/uploaded_dataset.csv`)  
> **Related:** `config.yaml`, `src/optimizer.py`, EDA session 2026-06-03  
> **Note:** Canonical optimization doc. Content from the former `docs/optimization.md` is merged here.

This document is the **single source of truth** for the optimization problem: team decisions and EDA rationale (channels, objective, constraints, budget), plus **solver math** (KKT, SLSQP, shadow price) and implementation guidance for `src/optimizer.py`.

It is based on EDA and pipeline runs on the uploaded Conjura-style dataset (132,759 rows, 143 timeseries, 2019-07-21 → 2024-06-02).

---

## Problem overview (plain English)

Marketing teams need to decide how much to spend on each advertising channel. Given a **total budget** \(B\), the agent finds spend amounts \(x_i\) per channel that **maximize predicted conversions**, assuming each channel’s response **flattens at higher spend** (saturation). Curve shape parameters \((a_i, b_i)\) come from Gregory’s MMM fit on historical data; Meghna’s optimizer allocates budget subject to “don’t exceed \(B\)” and “don’t spend negative amounts.”

---

## Quick answer: Is this already in `config.yaml`?

**Partially.** The YAML file configures *infrastructure* (paths, channel lists, solver knobs). It does **not** document rationale, portfolio-level budget sizing, the objective formula, or KKT interpretation.

| Decision | In `config.yaml`? | Where else | Gap / mismatch |
|----------|-------------------|------------|----------------|
| **5 modeled channels** | Yes — `channels.modeled` + `column_map` | `dropped_columns`, pipeline | Rationale not in YAML |
| **4 dropped channels** | Yes — `channels.dropped_sparse` + `dropped_columns` | `handle_spend_nulls()` | Matches EDA |
| **Target = purchases** | Yes — `data.target_column: ALL_PURCHASES` | Pipeline renames to `y` | Revenue not chosen; not explained in YAML |
| **Objective function** | **No** | This doc, backward analysis Stage 5 | Not machine-readable in YAML |
| **Constraints (Σx≤B, x≥0)** | **No** (implicit) | `backward_analysis` Stage 6 | Caps keys exist but are all `null` |
| **Default budget B** | Yes — `optimization.default_budget: 50000` | — | **Does not match EDA** (~$3.5M/month portfolio); placeholder |
| **MMM frequency** | Yes — `mmm.freq: weekly` | Greg `run_fitting` | Stakeholder mod; κ in USD/week |
| **Activation κ** | Yes — `activation.thresholds` | Model B/C (Day 1) | Team-confirmed; `ceilings` TBD |
| **Solver settings** | Yes — SLSQP, `n_starts`, `tol`, `max_iter` | `src/optimizer.py` stub | OK |
| **Portfolio vs row-level budget** | **No** | Buggy estimate in Stage 6 | Documented in Section 3 |
| **Optimizer uses 5 spend cols only** | Implied by `column_map` | Backward analysis lists 12 cols | **Use config modeled list only** |

**Recommendation:** Keep `config.yaml` as runtime source of truth for lists and numeric defaults; use **this file** for rationale and math.

---

## 1. Channels

### Decision (final)

**Optimize spend across exactly five channels** (decision variables \(x_1,\ldots,x_5\)):

| Config key | CSV column | Role |
|------------|------------|------|
| `google_paid_search` | `GOOGLE_PAID_SEARCH_SPEND` | Decision variable |
| `google_shopping` | `GOOGLE_SHOPPING_SPEND` | Decision variable |
| `google_pmax` | `GOOGLE_PMAX_SPEND` | Decision variable |
| `meta_facebook` | `META_FACEBOOK_SPEND` | Decision variable |
| `meta_instagram` | `META_INSTAGRAM_SPEND` | Decision variable |

**Excluded from optimization** (dropped in pipeline, not in `channels.modeled`):

| Config key | CSV column | Status |
|------------|------------|--------|
| `google_display` | `GOOGLE_DISPLAY_SPEND` | Dropped |
| `google_video` | `GOOGLE_VIDEO_SPEND` | Dropped |
| `meta_other` | `META_OTHER_SPEND` | Dropped |
| `tiktok` | `TIKTOK_SPEND` | Dropped |

### Rationale

**Data coverage (raw upload, before drops):**

| Channel | Null % | Row-days with spend > 0 | Verdict |
|---------|--------|-------------------------|---------|
| Google Paid Search | 27% | 93,200 (70%) | Model |
| Google Shopping | 41% | 77,084 (58%) | Model |
| Google PMax | 54% | 60,982 (46%) | Model |
| Meta Facebook | 40% | 80,048 (60%) | Model |
| Meta Instagram | 80% | 26,765 (20%) | Model (sparse but usable) |
| Google Display | 86% | 16,218 (12%) | Drop — in `dropped_columns` |
| Meta Other | 82% | 21,969 (17%) | Drop — negligible spend after USD |
| Google Video | 94% | 7,617 (6%) | Drop — >90% null rule |
| TikTok | 97% | 3,219 (2%) | Drop — >90% null rule |

**Project rules applied:** Channels with **≥90% null** or **<30 non-zero observations** are not modeled. Display, meta_other, video, and tiktok fail sparsity or spend relevance.

**Portfolio spend share (post-pipeline, five channels only, USD, all 143 series aggregated per calendar day):**

| Channel | ~Share of daily portfolio spend |
|---------|----------------------------------|
| Meta Facebook | 34% |
| Google Shopping | 28% |
| Google PMax | 21% |
| Meta Instagram | 9% |
| Google Paid Search | 8% |

**Meta Instagram caveat:** Only ~19% of row-days have spend, and ~55% of timeseries ever use it. Still included: passes global rules, ~9% spend share, matches `config.yaml`. Drop in config only if MMM fit fails — not per user session.

**Adstock and aggregated spends:** Pipeline creates `{channel}_adstock`, `google_spend`, and `meta_spend` for MMM/EDA only. The optimizer must **not** use backward analysis’s full `spend_columns` list (12 names) — that would double-count.

### Fixed vs variable

| Aspect | Fixed or variable? | Mechanism |
|--------|-------------------|-----------|
| Channel set (5) | **Fixed** for this dataset | `config.yaml` + `dropped_columns` |
| Channel set for new uploads | **Semi-fixed** | Re-run EDA; change config if schema/sparsity differs |
| Per-channel caps | **Variable (optional)** | `optimization.channel_caps` (currently all `null`) |

---

## 2. Objective function

### Decision (final)

**Maximize predicted total conversions** using a **sum of per-channel saturation curves**:

\[
\max_{x_1,\ldots,x_5} \sum_{i=1}^{5} a_i \left(1 - e^{-b_i x_i}\right)
\]

| Symbol | Meaning |
|--------|---------|
| \(x_i\) | Spend allocated to channel \(i\) (USD, non-negative, planning period e.g. one month, **portfolio level**) |
| \(a_i, b_i\) | Saturation parameters from `data/processed/channel_params.json` (Gregory’s MMM on **train** data) |
| Target for fitting | `ALL_PURCHASES` → `y` after pipeline (`data.target_column` in YAML) |

**Not used:** `ALL_PURCHASES_ORIGINAL_PRICE` (revenue) — skewed scale, mixed currency interpretation, weaker stakeholder story than conversion counts.

### Rationale (EDA + team)

1. **Business alignment:** Backward analysis Stage 5: “maximize conversions” ↔ `ALL_PURCHASES` / `y`.
2. **Saturation shape:** Portfolio daily spend vs `y` shows diminishing returns (log-log correlations ~0.87–0.92 on major channels) → exponential saturation, not linear.
3. **Integration:** Gregory exports \((a,b)\); optimizer implements this objective and gradient; KKT section below assumes this form.

### SciPy formulation (minimize)

`scipy.optimize.minimize` minimizes, so implement:

\[
\min_{x} f(x) = -\sum_{i=1}^{5} a_i \left(1 - e^{-b_i x_i}\right)
\]

**Gradient** (for SLSQP):

\[
\frac{\partial f}{\partial x_i} = -a_i b_i e^{-b_i x_i}
\]

Provide `objective()` and `gradient()` in `src/optimizer.py` (see Section 7).

### What YAML contains

- `data.target_column: ALL_PURCHASES` — yes.
- Objective formula — **not** in YAML.

### Fixed vs variable

| Aspect | Fixed or variable? | Mechanism |
|--------|-------------------|-----------|
| Saturation functional form | **Fixed** | This doc + `optimizer.py` |
| Target column (`y`) | **Fixed** for this dataset | `config.yaml`; Stage 1 |
| Curve parameters \(a_i, b_i\) | **Fixed per pipeline run** | `channel_params.json` |
| Budget scale of \(x\) | **Variable** | User budget \(B\) — Section 3 |

---

## 3. Constraints

### Decision (final)

| # | Constraint | Type | Math |
|---|------------|------|------|
| 1 | **Budget** | Hard | \(\sum_{i=1}^{5} x_i \le B\) |
| 2 | **Non-negativity** | Hard | \(x_i \ge 0\) |
| 3 | **Channel caps** | Optional | \(x_i \le \text{cap}_i\) if set in `optimization.channel_caps`; **currently all `null`** |

**No** equality \(\sum x_i = B\): with saturation, the optimum may leave budget unused → complementary slackness gives λ = 0 when budget is not binding.

### Rationale for budget \(B\)

**Aggregation:** \(B\) is **portfolio-level** (sum all timeseries for the period), not mean per row-day.

| Method | Approximate value | Comment |
|--------|-------------------|---------|
| Mean daily spend × 30 | ~$3.85M / month | Long-run average |
| Last 30 calendar days total | ~$3.62M | Current run rate |
| `config.yaml` `default_budget` | **$50,000** | Placeholder only |
| Backward analysis `detected_budget` (~$1.74M) | Row-level mean × 260 | **Misleading** for portfolio — fix Stage 6 separately |

**Recommended default B:** **~$3,500,000 / month**. Users override via `confirmed_budget` in Streamlit.

**No caps initially:** Avoid over-constraining; add caps in YAML if solutions are unrealistic for sparse channels.

### What YAML contains

```yaml
optimization:
  default_budget: 50000      # team should update — see Section 9
  n_starts: 50
  solver: "SLSQP"
  tol: 1.0e-9
  max_iter: 1000
  channel_caps:
    google_paid_search: null
    # ... all null
```

---

## 4. KKT conditions

At the optimum \(x^*\) (with optional caps \(x_i \le c_i\)), the Karush-Kuhn-Tucker conditions characterize the solution. Below: one **math** statement and one **plain-English** sentence each.

| Condition | Math (intuition) | Plain English |
|-----------|------------------|---------------|
| **1. Stationarity** | \(\nabla f(x^*) + \lambda \mathbf{1} - \sum_i \mu_i \mathbf{e}_i = 0\) (with multipliers for active bounds) | At each channel, marginal **cost** of one more dollar of spend (in objective units) balances the shadow price λ on the budget — unless the channel is at zero or a cap. |
| **2. Primal feasibility** | \(\sum x_i \le B\), \(x_i \ge 0\), caps if any | Total spend does not exceed budget; no negative allocations. |
| **3. Dual feasibility** | \(\lambda \ge 0\), \(\mu_i \ge 0\) | Multipliers on inequalities are non-negative. |
| **4. Complementary slackness** | \(\lambda(B - \sum x_i^*) = 0\); \(\mu_i(x_i^* - c_i) = 0\) | If budget is not fully used, λ = 0; if a channel is below its cap, that cap’s multiplier is zero. |

**Implementation:** `verify_kkt(result, budget, channels)` in `src/optimizer.py` should check these numerically (tolerance from `config.yaml` `optimization.tol`) and set `OptimResult.kkt_status`.

---

## 5. Shadow price (non-technical)

**λ\*** (report as `OptimResult.lambda_budget`) is the **extra conversions** you would gain from **one more dollar** of total budget at the optimum — the value of slightly loosening the budget constraint.

- If the budget is **not binding** (spend sum \(< B\)), λ\* ≈ 0: more money would not help at the margin.
- If the budget is **binding** (spend sum \(= B\)), λ\* > 0: additional budget would increase the objective.

Vikhyat’s page 3 should display λ\* in plain language for stakeholders.

---

## 6. Solver: why SLSQP (not CVXPY)

The objective is a **smooth nonlinear sum of exponentials** with **box constraints** (non-negativity, optional caps) and one **linear inequality** (budget). **SLSQP** in SciPy (`scipy.optimize.minimize`, method=`SLSQP`):

- Handles inequality and bound constraints in one call  
- Works with user-supplied gradients (faster and more stable for this problem)  
- Avoids a separate modeling layer and keeps dependencies light (team standard in `requirements.txt`)

**CVXPY** is better for convex programs and disciplined convex modeling; this problem is not posed as a convex program in the course design, and SciPy is sufficient for five dimensions with multi-start (`optimization.n_starts: 50`).

**Config knobs:** `solver: SLSQP`, `tol: 1e-9`, `max_iter: 1000`, `n_starts: 50` — use random or heuristic starting points across the feasible box to reduce local-minimum risk.

---

## 7. Implementation (`src/optimizer.py`)

### `OptimResult` (return type)

```python
@dataclass
class OptimResult:
    allocation: dict[str, float]   # channel key -> spend
    objective_value: float         # maximum conversions (positive, negate f at end)
    kkt_status: str
    lambda_budget: float
    success: bool
    message: str = ""
```

### Public functions (contract)

| Function | Role |
|----------|------|
| `objective(x, params, channels)` | Negative total predicted conversions |
| `gradient(x, params, channels)` | ∂f/∂x_i per channel |
| `verify_kkt(result, budget, channels)` | Numeric KKT check → dict / status string |
| `solve(params, budget, channels, caps=None)` | Multi-start SLSQP → `OptimResult` |
| `solve_from_file(config_path="config.yaml")` | Load params path + config; run solve |

### Checklist

1. Read `config["channels"]["modeled"]`; map to spend columns via `column_map`.
2. Load \((a,b)\) per channel from `data/processed/channel_params.json` (Gregory).
3. Use portfolio-level \(B\) from `confirmed_budget` or `optimization.default_budget`.
4. Decision vector length = **5** only; ignore adstock / aggregated spend columns.
5. Constraints in `minimize`: `{'type': 'ineq', 'fun': lambda x: B - np.sum(x)}` plus bounds `(0, cap_i)`.
6. Run `n_starts` optimizations; keep best feasible result.
7. Return `OptimResult` with `allocation`, `lambda_budget`, `kkt_status`.

**Consumers:** Piyush (agent explanations), Vikhyat (`app/pages/3_allocation.py`).

---

## 8. How fixed vs variable choices work in the app

```text
┌─────────────────────────────────────────────────────────────────┐
│ FIXED BY CONFIG + PIPELINE                                      │
│  • 5 channels, 4 dropped  •  Target y  •  Saturation objective  │
│  •  Hard: sum(x)<=B, x>=0                                       │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ FIXED PER RUN — channel_params.json (a_i, b_i)                  │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ VARIABLE BY USER — budget B; optional caps                      │
└─────────────────────────────────────────────────────────────────┘
```

Channels and objective form are not per-session toggles without re-fitting MMM. **Budget** is the main scenario lever.

---

## 9. Suggested `config.yaml` updates (team approval)

With `mmm.freq: weekly`, express **B in USD/week** (or document conversion):

```yaml
mmm:
  freq: weekly
optimization:
  time_unit: weekly
  default_budget: 808000   # ~$3.5M/month ÷ 4.33; portfolio Model A (EDA 2026-06-03)
```

Users still override via `confirmed_budget` in Streamlit. See **§13** for activation ceilings and scenario-B choices.

---

## 13. Stakeholder mod — config values (locked Day 1)

Ana Day-0 handoff (weekly train resample):

| Field | Value |
|---|---|
| `optimization.default_budget` | **831,142** USD/week |
| `optimization.scenario_budget_activation` | **90,000** USD/week (optional activation narrative) |
| `activation.ceilings` | see `config.yaml` (1.5 × max weekly train spend) |

Model B solver: `solve_with_activation()` in `optimizer.py` — 32-pattern enumeration, κ ±20% via `solve_activation_kappa_sweep()`.

Model C: pending Greg re-fit + holdout λ.

---

## 10. Data reference (reproducibility)

```bash
# Repo root, venv active
python -c "from src.data_prep import run_pipeline; run_pipeline(raw_path='data/raw/uploaded_dataset.csv')"
python -c "from src.backward_analysis import run_backward_analysis; ..."
```

**Dataset fingerprint:** 132,759 rows · 143 timeseries · 14 currencies · no raw duplicates.

---

## 12. Bayesian optimization layer (Stage 1 — MMM tuning)

> **Detail:** [bayesian_optimization_plan.md](bayesian_optimization_plan.md)  
> **Implementation:** `src/bo_mmm_tuning.py`

Lecture 7 BO applies to **expensive MMM refits**, not budget allocation:

| Stage | Method | Module |
|-------|--------|--------|
| Tune MMM hyperparameters (holdout R²) | GP + Expected Improvement | `bo_mmm_tuning.py` |
| Allocate budget given curves | SLSQP + KKT | `optimizer.py` |

**Default search (config):** `reg_b_weight` only (`tune_decays: false`) so fitted curves stay on **raw USD** spend — aligned with the optimizer.

**Offline run:**

```bash
# After pipeline produces mmm_train.csv + mmm_test.csv
# Set mmm_tuning.enabled: true in config.yaml, then:
python -m src.bo_mmm_tuning
# Set mmm_tuning.use_bo_params: true to load channel_params_bo.json in the app
```

---

## 11. Document map

| Question | Read this |
|----------|-----------|
| Full optimization spec (this file) | **optimization_problem_spec.md** |
| Cleaning before optimization | [data_pipeline.md](data_pipeline.md) |
| Stage 7 confirmation gate | [backward_analysis.md](backward_analysis.md) |
| Repo / LLM context | [../PROJECT_HANDOFF.md](../PROJECT_HANDOFF.md) |
| BO plan (team) | [bayesian_optimization_plan.md](bayesian_optimization_plan.md) |
| Pending κ / B / u_c decisions | **§13** (this file) |

---

*End of specification.*
