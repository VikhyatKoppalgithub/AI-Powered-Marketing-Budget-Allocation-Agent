# Optimizer ↔ Explainer Integration Checklist

> **Owner:** Meghna Advani + Vikhyat Koppal  
> **Last updated:** 2026-06-05  
> **Status:** In Progress  
> **Context:** After merging `origin/main` (PR #3 explainer + pages) into `feature/optimizer`

Use this when wiring the real optimizer into Streamlit and before merging Meghna's optimizer PR.

---

## Branch state

- Local branch: `feature/optimizer` (includes Vikhyat's merged work + Meghna's `optimizer.py`)
- **Tests passing (2026-06-05):** `test_optimizer.py` (14), `test_explainer.py` (13), optimizer integration (2) — **29 total**

---

## Contract: unified `OptimResult` (resolved 2026-06-05)

Single dataclass in **`src/optimizer.py`**. Explainer imports it (duplicate removed).

| Field | Owner / use |
|-------|-------------|
| `allocation`, `predicted_conversions`, `total_spent`, `status` | Vikhyat pages + explainer |
| `baseline_allocation`, `baseline_conversions`, `lift_pct` | Vikhyat UI — **0 / empty until `baseline.py`** |
| `kkt_status`, `lambda_budget`, `success`, `message` | Meghna optimizer / course / agent |

---

## Contract gap (historical — before alignment)

### Meghna — `src/optimizer.py` (implemented)

| Field | Type | Notes |
|-------|------|--------|
| `allocation` | `dict[str, float]` | Channel key → monthly USD |
| `objective_value` | `float` | Predicted conversions |
| `kkt_status` | `str` | `"pass"` / `"fail"` |
| `lambda_budget` | `float` | Shadow price of budget |
| `success` | `bool` | SciPy multistart best run |
| `message` | `str` | Solver message |

### Vikhyat — `src/explainer.py` + pages (expects)

| Field | Type | Meghna has? |
|-------|------|-------------|
| `allocation` | `dict[str, float]` | ✅ Same |
| `predicted_conversions` | `float` | ⚠️ Named `objective_value` |
| `total_spent` | `float` | ⚠️ Derivable: `sum(allocation.values())` |
| `status` | `str` | ⚠️ Named `kkt_status` (different semantics) |
| `baseline_allocation` | `dict[str, float]` | ❌ Needs `baseline.py` |
| `baseline_conversions` | `float` | ❌ Needs `baseline.py` |
| `lift_pct` | `float` | ❌ Needs `baseline.py` |

Vikhyat's explainer defines a **duplicate** `OptimResult` dataclass for isolated tests. Long-term: import from `src.optimizer` and align fields.

---

## Session state keys (Streamlit)

| Key | Set by | Used by |
|-----|--------|---------|
| `optim_result` | **Meghna (missing today)** | Pages 3, 4, 5; explainer |
| `channel_params` | Gregory / pipeline | Pages 3–5; diagnostics |
| `channel_caps` | Meghna optimizer (optional) | Page 3 diagnostics |
| `optimizer_fn` | Meghna (optional) | Page 5 sensitivity |

**Today:** Page 3 shows a warning if `optim_result` is `None`. Nothing in the app calls `solve()` yet.

---

## Agreed fix options (pick one in 15-min sync)

### Option A — Extend Meghna's `OptimResult` (recommended)

Add to `src/optimizer.py`:

- `predicted_conversions` → alias/property for `objective_value`
- `total_spent` → property `sum(allocation.values())`
- `status` → property mapping from `kkt_status` and/or `success`
- `baseline_allocation`, `baseline_conversions`, `lift_pct` → populated when `baseline.py` runs (or `None` / 0 until then)

Vikhyat removes duplicate dataclass; pages use one type.

### Option B — Adapter dict in app layer

After `solve()`, build:

```python
st.session_state["optim_result"] = {
    "allocation": result.allocation,
    "predicted_conversions": result.objective_value,
    "total_spent": sum(result.allocation.values()),
    "status": result.kkt_status,
    **baseline_fields_from_baseline_py,
}
```

Keeps optimizer pure; wiring lives in a new small helper or page 2→3 handoff.

### Option C — Vikhyat updates pages

Pages read `objective_value`, `lambda_budget`, `kkt_status` directly. Explainer `_coerce` updated. More churn on his side.

---

## `optimizer_fn` for page 5 (sensitivity)

`run_sensitivity(..., optimizer_fn=...)` expects a callable roughly:

```python
def optimizer_fn(params: dict, channels: list[str], budget: float) -> dict:
    # return {"allocation": {...}, "predicted_conversions": float}
```

**Meghna wrapper** (note argument order: `params`, `channels`, `budget`):

```python
from src.optimizer import solve

def optimizer_fn(params, channels, budget):
    r = solve(params, budget, channels, n_starts=20)
    return {
        "allocation": r.allocation,
        "predicted_conversions": r.objective_value,
    }
```

Set `st.session_state["optimizer_fn"] = optimizer_fn` where optimization runs.

---

## Baseline.py dependency

Page 3 headline metrics need:

- `baseline_allocation` — historical spend mix × B (`compute_historical_baseline`)
- `baseline_conversions` — predict conversions at that mix
- `lift_pct` — `compute_lift(optimized, baseline, params)`

**Order:** Optimizer PR can merge first; baseline PR or small follow-up fills lift fields.

---

## Pre-PR checklist (Meghna)

- [x] Merge `origin/main` into `feature/optimizer`
- [x] Optimizer tests pass
- [x] Explainer tests pass (no conflict with optimizer module)
- [ ] Team picks Option A / B / C for `OptimResult` alignment
- [ ] Wire `solve()` → `st.session_state["optim_result"]` (Meghna or Vikhyat)
- [ ] Implement `baseline.py` for lift fields
- [ ] Set `channel_params` in session after MMM / upload pipeline
- [ ] E2E: upload → analysis confirm → optimize → page 3 renders real numbers

---

## Message for Vikhyat (copy-paste)

> Pulled your explainer + pages into `feature/optimizer`. Optimizer tests + your explainer tests all pass. Contract gap: my `OptimResult` uses `objective_value` / `kkt_status` / `lambda_budget`; your pages expect `predicted_conversions` / `status` / baseline / lift fields. Proposal: extend my dataclass (or app adapter) + I add `baseline.py` for lift. Can we sync 15 min on who wires `st.session_state['optim_result']` and whether you drop the duplicate `OptimResult` in explainer?

---

## Related docs

- [optimization_problem_spec.md](optimization_problem_spec.md) — problem definition
- [architecture.md](architecture.md) — session keys and integration contracts
