"""Battery dispatch linear program (FR-502).

Decision variables per slot t (0..47):
    s_t  charge power (kW, >= 0, <= max_charge_kw)
    d_t  discharge power (kW, >= 0, <= max_discharge_kw)
    x_t  state of charge after slot t (kWh, [soc_min, capacity])
    g_t  grid import (kW, >= 0)
    p    peak grid import (kW)  — linearised demand charge (FR-502)

Objective: sum_t price_t * g_t * dt  +  demand_charge * p
Constraints:
    g_t - s_t + d_t = load_t                       (power balance)
    x_t - x_{t-1} = dt * (eta_c * s_t - d_t / eta_d)  (SoC dynamics)
    p >= g_t  for all t                            (peak import)
    x_0 = soc_initial
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog


@dataclass
class BatterySpec:
    capacity_kwh: float
    max_charge_kw: float
    max_discharge_kw: float
    charge_efficiency: float
    discharge_efficiency: float
    soc_min_kwh: float
    soc_initial_kwh: float


def spec_from_config(cfg: dict) -> BatterySpec:
    return BatterySpec(
        capacity_kwh=float(cfg.get("capacity_kwh", 100.0)),
        max_charge_kw=float(cfg.get("max_charge_kw", 10.0)),
        max_discharge_kw=float(cfg.get("max_discharge_kw", 10.0)),
        charge_efficiency=float(cfg.get("charge_efficiency", 0.95)),
        discharge_efficiency=float(cfg.get("discharge_efficiency", 0.95)),
        soc_min_kwh=float(cfg.get("soc_min_kwh", 0.0)),
        soc_initial_kwh=float(cfg.get("soc_initial_kwh", 0.0)),
    )


def solve_battery(
    load_kw: list[float],
    prices: list[float],
    spec: BatterySpec,
    demand_charge_per_kw: float = 0.0,
    slot_minutes: int = 30,
) -> dict | None:
    """Solve the LP. Returns None if infeasible (caller falls back to greedy)."""
    n = len(load_kw)
    if n == 0 or spec.capacity_kwh <= spec.soc_min_kwh:
        return None
    if not (spec.soc_min_kwh <= spec.soc_initial_kwh <= spec.capacity_kwh):
        return None
    dm = slot_minutes / 60.0

    idx_s = slice(0, n)
    idx_d = slice(n, 2 * n)
    idx_x = slice(2 * n, 3 * n + 1)
    idx_g = slice(3 * n + 1, 4 * n + 1)
    idx_p = 4 * n + 1
    n_vars = n_vars_count(n)

    c = np.zeros(n_vars)
    c[idx_g] = np.asarray(prices) * dm
    c[idx_p] = demand_charge_per_kw

    a_ub: list[list[float]] = []
    b_ub: list[float] = []
    for t in range(n):
        row = [0.0] * n_vars
        row[idx_p] = -1.0
        row[idx_g.start + t] = 1.0
        a_ub.append(row)
        b_ub.append(0.0)

    a_eq: list[list[float]] = []
    b_eq: list[float] = []
    for t in range(n):
        row = [0.0] * n_vars
        row[idx_x.start + t + 1] = 1.0
        row[idx_x.start + t] = -1.0
        row[idx_s.start + t] = -dm * spec.charge_efficiency
        row[idx_d.start + t] = dm / spec.discharge_efficiency
        a_eq.append(row)
        b_eq.append(0.0)

        row2 = [0.0] * n_vars
        row2[idx_g.start + t] = 1.0
        row2[idx_s.start + t] = -1.0
        row2[idx_d.start + t] = 1.0
        a_eq.append(row2)
        b_eq.append(float(load_kw[t]))

    bounds: list[tuple[float | None, float | None]] = []
    bounds += [(0.0, spec.max_charge_kw)] * n
    bounds += [(0.0, spec.max_discharge_kw)] * n
    bounds += [(spec.soc_min_kwh, spec.capacity_kwh)] * (n + 1)
    bounds[idx_x.start] = (spec.soc_initial_kwh, spec.soc_initial_kwh)
    bounds += [(0.0, None)] * n
    bounds.append((0.0, None))

    try:
        res = linprog(
            c,
            A_ub=np.asarray(a_ub),
            b_ub=np.asarray(b_ub),
            A_eq=np.asarray(a_eq),
            b_eq=np.asarray(b_eq),
            bounds=bounds,
            method="highs",
        )
    except Exception:
        return None
    if not res.success:
        return None

    x = res.x
    return {
        "charge": [round(float(x[idx_s.start + t]), 3) for t in range(n)],
        "discharge": [round(float(x[idx_d.start + t]), 3) for t in range(n)],
        "soc": [round(float(x[idx_x.start + t + 1]), 3) for t in range(n)],
        "grid": [round(float(x[idx_g.start + t]), 3) for t in range(n)],
        "cost": float(res.fun),
    }


def n_vars_count(n: int) -> int:
    # s(n) + d(n) + soc(n+1) + g(n) + peak(1)
    return 4 * n + 2
