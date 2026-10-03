# Generates contracts/sample JSON files (48-slot forecast/plan, one peak alert).
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "contracts" / "sample"
SAMPLE.mkdir(parents=True, exist_ok=True)

TZ = timezone(timedelta(hours=11))  # Australia/Sydney AEDT, Feb 2013
ORIGIN = datetime(2013, 2, 15, 0, 0, tzinfo=TZ)

HOURS = [118, 112, 108, 105, 104, 106, 115, 135, 150, 158, 160, 163, 161, 158,
         155, 150, 152, 165, 182, 175, 155, 140, 128, 122]
def p50(slot: int) -> float:
    h = (slot // 2) % 24
    k = slot % 2
    nxt = HOURS[(h + 1) % 24]
    return round(HOURS[h] + (nxt - HOURS[h]) * 0.5 * k, 1)

def ts(slot: int) -> str:
    return (ORIGIN + timedelta(minutes=30 * slot)).isoformat()

def price(slot: int) -> float:
    hour = (slot * 0.5) % 24
    if 14 <= hour < 20:
        return 0.38
    if 22 <= hour or hour < 7:
        return 0.12
    return 0.24

points = []
history = []
prev = 125.0
for h in range(24):
    for k in range(2):
        slot = h * 2 + k
        v = p50(slot)
        widen = 1.0 + 0.25 * max(0.0, (v - 150) / 40)
        points.append({
            "slot": slot,
            "timestamp": ts(slot),
            "p10": round(v * 0.94 - 2.0 * widen, 1),
            "p50": v,
            "p90": round(v * 1.06 + 2.0 * widen, 1),
        })
        prev += (-3.2 if slot in (36, 37, 38, 39) else 1.1) + (0.4 * (slot % 3 - 1))
        history.append({
            "timestamp": (ORIGIN - timedelta(days=1) + timedelta(minutes=30 * slot)).isoformat(),
            "actual": round(prev, 1),
        })

forecast = {
    "run_id": "2013-02-15T00-00",
    "origin_time": ORIGIN.isoformat(),
    "level": "portfolio",
    "entity_id": "all",
    "unit": "kW",
    "slot_minutes": 30,
    "model_version": "ensemble-v1",
    "weather_source": "open-meteo",
    "points": points,
    "history": history,
}
(SAMPLE / "forecast.json").write_text(json.dumps(forecast, indent=2))

alerts = [
    {
        "id": "a1",
        "type": "peak",
        "severity": "warn",
        "level": "portfolio",
        "entity_id": "all",
        "window_start": "2013-02-15T18:00:00+11:00",
        "window_end": "2013-02-15T20:00:00+11:00",
        "value": 182.0,
        "threshold": 170.0,
        "message": "Evening peak above threshold",
    }
]
(SAMPLE / "alerts.json").write_text(json.dumps(alerts, indent=2))

cap, min_soc, soc = 100.0, 10.0, 50.0
charge_max = discharge_max = 10.0
eta = 0.95
plan_slots = []
cost_before = 0.0
for slot in range(48):
    load = p50(slot)
    price_v = price(slot)
    charge = discharge = 0.0
    if price_v <= 0.15 and soc < cap - 1:
        charge = min(charge_max, cap - soc) / eta
        charge = round(min(charge, charge_max), 1)
        if charge:
            soc = min(cap, soc + charge * eta * 0.5)
    elif 36 <= slot < 40 and soc > min_soc + 1:
        discharge = min(discharge_max, (soc - min_soc) / (0.5 * eta))
        discharge = round(min(discharge, discharge_max), 1)
        if discharge:
            soc = max(min_soc, soc - discharge * 0.5 / eta)
    grid = round(max(0.0, load - charge + discharge), 1)
    cost_before += price_v * load * 0.5
    plan_slots.append({
        "slot": slot,
        "price": price_v,
        "grid_before_kw": load,
        "grid_after_kw": grid,
        "battery_charge_kw": charge,
        "battery_discharge_kw": discharge,
        "soc_kwh": round(soc, 1),
    })
cost_after = sum(s["price"] * s["grid_after_kw"] * 0.5 for s in plan_slots)
peak_before = max(s["grid_before_kw"] for s in plan_slots)
peak_after = max(s["grid_after_kw"] for s in plan_slots)
saving = round(max(0.0, cost_before - cost_after), 2)

plan = {
    "mode": "advisory",
    "assumptions": "Illustrative tariff and battery values",
    "slots": plan_slots,
    "cost_before": round(cost_before, 2),
    "cost_after": round(cost_after, 2),
    "saving": saving,
    "peak_before_kw": peak_before,
    "peak_after_kw": peak_after,
    "generator_recommendation": [
        {"slot": 36, "message": "Generator cheaper than grid for this slot"}
    ],
}
(SAMPLE / "plan.json").write_text(json.dumps(plan, indent=2))

metrics = {
    "scope": "walk_forward_backtest",
    "by_model": [
        {"model": "seasonal_naive", "mae": 12.4, "rmse": 16.0, "nmae": 0.098, "skill": 0.0},
        {"model": "weekly_naive", "mae": 11.1, "rmse": 14.8, "nmae": 0.088, "skill": 0.10},
        {"model": "ridge", "mae": 10.6, "rmse": 14.0, "nmae": 0.084, "skill": 0.14},
        {"model": "lightgbm", "mae": 9.9, "rmse": 13.3, "nmae": 0.079, "skill": 0.20},
        {"model": "ensemble", "mae": 9.8, "rmse": 13.1, "nmae": 0.077, "skill": 0.21},
    ],
    "by_hour": [{"hour": h, "mae": round(7.5 + 4.5 * abs(h - 18) / 6, 1)} for h in range(24)],
    "by_weekday": [{"weekday": d, "mae": round(9.2 + 0.4 * d, 1)} for d in range(7)],
    "coverage_p10_p90": 0.79,
    "last_7_days_mae": 10.2,
    "drift_ratio": 1.05,
}
(SAMPLE / "metrics.json").write_text(json.dumps(metrics, indent=2))

context = {
    "run_id": "2013-02-15T00-00",
    "peak": {"time": "2013-02-15T18:30:00+11:00", "p50_kw": 182.0, "p90_kw": 195.3},
    "total_kwh_next_24h": 3120.0,
    "drivers": ["Hot afternoon (max 36 C)", "Weekday evening", "Low solar after 17:00"],
    "band_width_note": "P10-P90 band is widest at the evening peak",
    "accuracy_last_7_days": {"mae_kw": 10.2, "skill_vs_naive": 0.21},
    "alerts_summary": ["1 peak alert (warn)"],
    "plan_summary": {"saving": 37.3, "peak_reduction_kw": 22.4},
    "weather": {"max_apparent_temp_c": 36.0, "source": "open-meteo"},
}
(SAMPLE / "explain_context.json").write_text(json.dumps(context, indent=2))

entities = {"portfolio": ["all"], "zone": ["2000", "2010"], "house": ["1", "2", "3"]}
(SAMPLE / "entities.json").write_text(json.dumps(entities, indent=2))

print("samples written:", sorted(p.name for p in SAMPLE.iterdir()))
