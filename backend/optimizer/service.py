"""Optimizer entry point: portfolio-level battery + shiftable loads + generator check.

Produces contracts/sample plan.json. Advisory only; tariff/battery values are assumptions.
Never emits a plan with negative saving (compared against do-nothing, FR-506).
"""
from __future__ import annotations

from backend.config import AppConfig
from backend.optimizer.battery_lp import spec_from_config, solve_battery
from backend.optimizer.shift import cheapest_window
from backend.optimizer.tariff import prices_for_slots


def _greedy_plan(load: list[float], prices: list[float], spec, slot_minutes: int) -> dict:
    """Cheap heuristic fallback if the LP fails: charge at the cheapest slots, discharge at the most expensive."""
    dm = slot_minutes / 60.0
    min_p, max_p = min(prices), max(prices)
    soc = min(max(spec.soc_initial_kwh, spec.soc_min_kwh), spec.capacity_kwh)
    charge, discharge, grid, socs = [], [], [], []
    for t in range(len(load)):
        chg = dis = 0.0
        if prices[t] <= min_p + 1e-9 and soc < spec.capacity_kwh - 0.5:
            chg = min(spec.max_charge_kw, (spec.capacity_kwh - soc) / (spec.charge_efficiency * dm))
            soc = min(spec.capacity_kwh, soc + chg * spec.charge_efficiency * dm)
        elif prices[t] >= max_p - 1e-9 and soc > spec.soc_min_kwh + 0.5:
            dis = min(spec.max_discharge_kw, (soc - spec.soc_min_kwh) / (dm / spec.discharge_efficiency))
            soc = max(spec.soc_min_kwh, soc - dis * dm / spec.discharge_efficiency)
        charge.append(round(chg, 3))
        discharge.append(round(dis, 3))
        grid.append(round(max(0.0, load[t] - chg + dis), 3))
        socs.append(round(soc, 3))
    return {"charge": charge, "discharge": discharge, "grid": grid, "soc": socs}


def build_plan(forecast: dict, cfg: AppConfig) -> dict:
    points = forecast.get("points", [])
    n = len(points)
    quantile = "p90" if cfg.battery.get("use_p90") else "p50"
    base = [float(p.get(quantile, p.get("p50", 0.0)) or 0.0) for p in points]

    tariff = cfg.tariff
    slot_minutes = int(tariff.get("slot_minutes", 30))
    dm = slot_minutes / 60.0
    prices = prices_for_slots(n, tariff)
    demand_charge = float(tariff.get("demand_charge_per_kw", 0.0) or 0.0)

    # baseline: no battery, shiftable loads placed at their default (earliest) slot
    baseline = list(base)
    optimized = list(base)
    shifted_loads: list[dict] = []
    for load in cfg.shiftable_loads:
        kw = float(load["kw"])
        dur = int(load["duration_slots"])
        default_start = int(load.get("allowed_start_slot", 0))
        end = int(load.get("allowed_end_slot", n - 1))
        placed = cheapest_window(prices, dur, default_start, end)
        if placed is None:
            placed = default_start
        for t in range(default_start, min(default_start + dur, n)):
            baseline[t] += kw
        for t in range(placed, min(placed + dur, n)):
            optimized[t] += kw
        shifted_loads.append(
            {
                "name": load.get("name", "load"),
                "kw": kw,
                "duration_slots": dur,
                "default_start_slot": default_start,
                "placed_start_slot": placed,
            }
        )

    cost_before = sum(prices[t] * baseline[t] * dm for t in range(n)) + demand_charge * max(baseline)
    peak_before = max(baseline)

    spec = spec_from_config(cfg.battery)
    sol = solve_battery(optimized, prices, spec, demand_charge_per_kw=demand_charge, slot_minutes=slot_minutes)
    if sol is None:
        sol = _greedy_plan(optimized, prices, spec, slot_minutes)

    cost_after = sum(prices[t] * sol["grid"][t] * dm for t in range(n)) + demand_charge * max(sol["grid"])
    peak_after = max(sol["grid"])

    if cost_after >= cost_before - 1e-6:
        # FR-506: never emit a negative-saving plan — fall back to do-nothing
        slots = [
            {
                "slot": t,
                "price": prices[t],
                "grid_before_kw": round(baseline[t], 1),
                "grid_after_kw": round(baseline[t], 1),
                "battery_charge_kw": 0.0,
                "battery_discharge_kw": 0.0,
                "soc_kwh": round(spec.soc_initial_kwh, 1),
            }
            for t in range(n)
        ]
        cost_after = cost_before
        peak_after = peak_before
        note = "Battery/shifting plan does not save under current assumptions; no action recommended."
    else:
        slots = [
            {
                "slot": t,
                "price": prices[t],
                "grid_before_kw": round(baseline[t], 1),
                "grid_after_kw": round(sol["grid"][t], 1),
                "battery_charge_kw": sol["charge"][t],
                "battery_discharge_kw": sol["discharge"][t],
                "soc_kwh": sol["soc"][t],
            }
            for t in range(n)
        ]
        note = None

    generator_cost = cfg.generator.get("cost_per_kwh")
    generator_recommendation = []
    if generator_cost:
        generator_recommendation = [
            {
                "slot": t,
                "message": f"Grid price {prices[t]:.2f} $/kWh exceeds generator cost {float(generator_cost):.2f} $/kWh",
            }
            for t in range(n)
            if prices[t] > float(generator_cost)
        ]

    return {
        "mode": "advisory",
        "assumptions": tariff.get("assumption", "Illustrative tariff and battery values (assumptions)"),
        "slots": slots,
        "cost_before": round(cost_before, 2),
        "cost_after": round(cost_after, 2),
        "saving": round(max(0.0, cost_before - cost_after), 2),
        "peak_before_kw": round(peak_before, 1),
        "peak_after_kw": round(peak_after, 1),
        "generator_recommendation": generator_recommendation,
        "shifted_loads": shifted_loads,
        "note": note,
    }
