"""
Budget optimization engine (SLSQP + KKT)
Owner: Meghna Advani

Maximizes sum_i a_i * (1 - exp(-b_i * x_i)) subject to sum(x) <= B, x >= 0,
optional per-channel caps. Uses multistart SLSQP from config.yaml.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize

from src.data_prep import load_config, resolve_project_path

logger = logging.getLogger(__name__)


@dataclass
class OptimResult:
    """Optimization output — shared contract for optimizer, explainer, and Streamlit pages."""

    allocation: dict[str, float]
    predicted_conversions: float
    total_spent: float
    status: str
    kkt_status: str
    lambda_budget: float
    success: bool
    baseline_allocation: dict[str, float] = field(default_factory=dict)
    baseline_conversions: float = 0.0
    lift_pct: float = 0.0
    message: str = ""


def _format_status(kkt_status: str, success: bool, message: str) -> str:
    """Human-readable status for Streamlit (page 3 caption)."""
    solver = "converged" if success else "check solver"
    detail = message.strip() if message else ""
    base = f"KKT {kkt_status} · solver {solver}"
    return f"{base} ({detail})" if detail else base


def _validate_inputs(params: dict, budget: float, channels: list[str]) -> None:
    if budget <= 0:
        raise ValueError(f"budget must be positive, got {budget}")
    if not channels:
        raise ValueError("channels must be a non-empty list")
    for ch in channels:
        if ch not in params:
            raise KeyError(f"Missing channel '{ch}' in params")
        a, b = params[ch]["a"], params[ch]["b"]
        if a <= 0 or b <= 0:
            raise ValueError(
                f"Channel '{ch}' requires a > 0 and b > 0; got a={a}, b={b}"
            )


def predicted_conversions(x: list[float] | np.ndarray, params: dict, channels: list[str]) -> float:
    """Total predicted conversions (maximize this)."""
    total = 0.0
    for i, ch in enumerate(channels):
        a = params[ch]["a"]
        b = params[ch]["b"]
        xi = max(float(x[i]), 0.0)
        total += a * (1.0 - np.exp(-b * xi))
    return float(total)


def objective(x: list[float] | np.ndarray, params: dict, channels: list[str]) -> float:
    """Negative total predicted conversions (minimize for SciPy)."""
    return -predicted_conversions(x, params, channels)


def gradient(x: list[float] | np.ndarray, params: dict, channels: list[str]) -> np.ndarray:
    """Gradient of objective (negative marginal conversions per channel)."""
    x = np.asarray(x, dtype=np.float64)
    grad = np.zeros(len(channels), dtype=np.float64)
    for i, ch in enumerate(channels):
        a = params[ch]["a"]
        b = params[ch]["b"]
        xi = max(float(x[i]), 0.0)
        grad[i] = -a * b * np.exp(-b * xi)
    return grad


def marginal_conversions(x: float, a: float, b: float) -> float:
    """d/dx [a * (1 - exp(-b*x))] = a * b * exp(-b*x)."""
    return a * b * np.exp(-b * max(x, 0.0))


def _estimate_lambda(
    x: np.ndarray,
    params: dict,
    channels: list[str],
    budget: float,
    caps: dict[str, float | None] | None,
    tol: float,
) -> float:
    """Shadow price of the budget constraint from active-channel marginals."""
    spend = float(np.sum(x))
    if spend >= budget - tol:
        active = []
        for i, ch in enumerate(channels):
            if x[i] <= tol:
                continue
            cap = caps.get(ch) if caps else None
            if cap is not None and x[i] >= cap - tol:
                continue
            active.append(marginal_conversions(x[i], params[ch]["a"], params[ch]["b"]))
        if active:
            return float(np.median(active))
    return 0.0


def verify_kkt(
    result: Any,
    budget: float,
    channels: list[str],
    params: dict | None = None,
    caps: dict[str, float | None] | None = None,
    tol: float = 1e-6,
) -> dict:
    """
    Numeric KKT checks for the budget allocation problem.

    ``result`` may be an OptimResult, a scipy OptimizeResult, or a raw spend vector.
    When ``params`` is omitted, only primal feasibility is checked.
    """
    if hasattr(result, "allocation"):
        x = np.array([result.allocation[ch] for ch in channels], dtype=np.float64)
        lam = result.lambda_budget
    elif hasattr(result, "x"):
        x = np.asarray(result.x, dtype=np.float64)
        lam = None
    else:
        x = np.asarray(result, dtype=np.float64)
        lam = None

    spend = float(np.sum(x))
    checks: dict[str, Any] = {
        "budget_feasible": spend <= budget + tol,
        "non_negative": bool(np.all(x >= -tol)),
        "spend_total": spend,
        "budget": budget,
    }

    if caps:
        cap_ok = True
        for i, ch in enumerate(channels):
            cap = caps.get(ch)
            if cap is not None and x[i] > cap + tol:
                cap_ok = False
        checks["caps_feasible"] = cap_ok

    if params is not None:
        if lam is None:
            lam = _estimate_lambda(x, params, channels, budget, caps, tol)
        checks["lambda_budget"] = lam

        binding = spend >= budget - tol
        checks["budget_binding"] = binding

        if binding and lam is not None:
            stationarity_errors = []
            for i, ch in enumerate(channels):
                if x[i] <= tol:
                    continue
                cap = caps.get(ch) if caps else None
                if cap is not None and x[i] >= cap - tol:
                    continue
                mc = marginal_conversions(x[i], params[ch]["a"], params[ch]["b"])
                stationarity_errors.append(abs(mc - lam))
            checks["stationarity_max_error"] = (
                float(max(stationarity_errors)) if stationarity_errors else 0.0
            )
            checks["stationarity_ok"] = checks["stationarity_max_error"] <= max(tol, 1e-3)
        else:
            checks["stationarity_ok"] = lam <= tol if not binding else True
            checks["complementary_slackness_ok"] = (not binding) or (lam > tol)

        if not binding:
            checks["complementary_slackness_ok"] = lam <= max(tol, 1e-3)

    primal_ok = checks["budget_feasible"] and checks["non_negative"]
    if caps and not checks.get("caps_feasible", True):
        primal_ok = False

    if params is None:
        status = "pass" if primal_ok else "fail"
    else:
        kkt_ok = primal_ok and checks.get("stationarity_ok", True)
        if caps:
            kkt_ok = kkt_ok and checks.get("caps_feasible", True)
        if not binding:
            kkt_ok = kkt_ok and checks.get("complementary_slackness_ok", True)
        status = "pass" if kkt_ok else "fail"

    checks["status"] = status
    return checks


def _build_bounds(
    channels: list[str],
    budget: float,
    caps: dict[str, float | None] | None,
) -> list[tuple[float, float]]:
    bounds = []
    for ch in channels:
        upper = budget
        if caps and caps.get(ch) is not None:
            upper = min(upper, float(caps[ch]))
        bounds.append((0.0, upper))
    return bounds


def _initial_guess(n: int, budget: float, rng: np.random.Generator) -> np.ndarray:
    weights = rng.dirichlet(np.ones(n))
    return weights * budget


def solve(
    params: dict,
    budget: float,
    channels: list[str],
    caps: dict | None = None,
    n_starts: int | None = None,
    tol: float | None = None,
    max_iter: int | None = None,
    seed: int = 0,
) -> OptimResult:
    """Run multistart SLSQP to maximize predicted conversions under budget."""
    _validate_inputs(params, budget, channels)
    config = load_config()
    opt_cfg = config.get("optimization", {})
    n_starts = n_starts if n_starts is not None else int(opt_cfg.get("n_starts", 50))
    tol = tol if tol is not None else float(opt_cfg.get("tol", 1e-9))
    max_iter = max_iter if max_iter is not None else int(opt_cfg.get("max_iter", 1000))

    n = len(channels)
    bounds = _build_bounds(channels, budget, caps)
    rng = np.random.default_rng(seed)

    def budget_constraint(x: np.ndarray) -> float:
        return budget - float(np.sum(x))

    def budget_jac(x: np.ndarray) -> np.ndarray:
        return -np.ones_like(x)

    constraints = (
        {"type": "ineq", "fun": budget_constraint, "jac": budget_jac},
    )

    starts: list[np.ndarray] = [np.full(n, budget / n)]
    for _ in range(max(n_starts - 1, 0)):
        starts.append(_initial_guess(n, budget, rng))

    best_x: np.ndarray | None = None
    best_val = np.inf
    best_success = False
    best_message = ""

    for x0 in starts:
        res = minimize(
            objective,
            x0,
            args=(params, channels),
            method="SLSQP",
            jac=gradient,
            bounds=bounds,
            constraints=constraints,
            options={"ftol": tol, "maxiter": max_iter, "disp": False},
        )
        if res.fun < best_val:
            best_val = float(res.fun)
            best_x = np.clip(res.x, 0.0, None)
            best_success = bool(res.success)
            best_message = str(res.message)

    assert best_x is not None
    obj = predicted_conversions(best_x, params, channels)
    lam = _estimate_lambda(best_x, params, channels, budget, caps, tol)
    kkt = verify_kkt(best_x, budget, channels, params=params, caps=caps, tol=tol)

    allocation = {ch: float(best_x[i]) for i, ch in enumerate(channels)}
    total_spent = float(sum(allocation.values()))
    kkt_status = str(kkt["status"])
    return OptimResult(
        allocation=allocation,
        predicted_conversions=obj,
        total_spent=total_spent,
        status=_format_status(kkt_status, best_success, best_message),
        kkt_status=kkt_status,
        lambda_budget=lam,
        success=best_success,
        message=best_message,
    )


def load_params(path: str | Path) -> dict:
    """Load channel_params.json written by mmm_model."""
    p = resolve_project_path(path)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def solve_from_file(config_path: str = "config.yaml") -> OptimResult:
    """Load params and config paths, then run solve()."""
    config = load_config(config_path)
    params = load_params(config["data"]["params_path"])
    channels = list(config["channels"]["modeled"])
    budget = float(config["optimization"]["default_budget"])
    caps = config["optimization"].get("channel_caps")
    return solve(params, budget, channels, caps=caps)


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    out = solve_from_file()
    print(out)
