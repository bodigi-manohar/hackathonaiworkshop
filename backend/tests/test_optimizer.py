"""Optimizer tests: SoC bounds, energy balance, saving >= 0, graceful infeasibility."""
import json
from pathlib import Path

from backend.config import get_app_config
from backend.optimizer import build_plan
from backend.optimizer.shift import cheapest_window

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "contracts" / "sample" / "forecast.json"


def sample_forecast():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def test_plan_shape_and_saving():
    cfg = get_app_config()
    plan = build_plan(sample_forecast(), cfg)
    assert plan["mode"] == "advisory"
    assert len(plan["slots"]) == 48
    assert plan["saving"] >= 0
    assert plan["cost_after"] <= plan["cost_before"] + 1e-6
    assert plan["assumptions"]


def test_soc_within_bounds_and_energy_balance():
    cfg = get_app_config()
    plan = build_plan(sample_forecast(), cfg)
    spec = cfg.battery
    cap = float(spec.get("capacity_kwh"))
    soc_min = float(spec.get("soc_min_kwh"))
    eta_c = float(spec.get("charge_efficiency"))
    eta_d = float(spec.get("discharge_efficiency"))
    slots = plan["slots"]
    for s in slots:
        assert soc_min - 1e-6 <= s["soc_kwh"] <= cap + 1e-6, f"slot {s['slot']} SoC out of bounds"
    for a, b in zip(slots, slots[1:]):
        # SoC after slot b = SoC after slot a + this slot's own net charge
        expected = a["soc_kwh"] + 0.5 * (eta_c * b["battery_charge_kw"] - b["battery_discharge_kw"] / eta_d)
        assert abs(b["soc_kwh"] - expected) < 0.15, f"energy balance broken at slot {b['slot']}"


def test_battery_actuates_on_peak_day():
    cfg = get_app_config()
    plan = build_plan(sample_forecast(), cfg)
    assert any(s["battery_discharge_kw"] > 0 for s in plan["slots"])
    assert any(s["battery_charge_kw"] > 0 for s in plan["slots"])


def test_infeasible_battery_falls_back_gracefully():
    cfg = get_app_config()
    original = dict(cfg.battery)
    try:
        cfg.battery["capacity_kwh"] = 5.0  # below soc_min/soc_initial -> LP infeasible
        plan = build_plan(sample_forecast(), cfg)
        assert plan["saving"] >= 0
        assert len(plan["slots"]) == 48
        # infeasible battery -> greedy fallback must not actuate the battery
        assert all(s["battery_charge_kw"] == 0.0 and s["battery_discharge_kw"] == 0.0 for s in plan["slots"])
    finally:
        cfg.battery.update(original)


def test_shifted_load_placed_in_cheap_window():
    cfg = get_app_config()
    plan = build_plan(sample_forecast(), cfg)
    assert plan["shifted_loads"]
    for sl in plan["shifted_loads"]:
        assert sl["placed_start_slot"] >= 0


def test_cheapest_window():
    prices = [0.5, 0.5, 0.1, 0.1, 0.5]
    assert cheapest_window(prices, 2, 0, 4) == 2
    assert cheapest_window(prices, 2, 3, 3) is None
    assert cheapest_window(prices, 0, 0, 4) is None
