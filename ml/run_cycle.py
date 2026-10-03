"""Steps 3, 6, 7: one forecast cycle -> runs/<run_id>/ bundle.

  python -m ml.run_cycle --origin 2013-02-15T00:00 --model baseline    # first contract file (sync S1)
  python -m ml.run_cycle --origin 2013-02-15T00:00                     # trained ensemble

Replay discipline: load-derived features only use data strictly before the origin. Weather at the target
slots is the dataset's actual weather (label `dataset-oracle`).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time

import numpy as np
import pandas as pd

from . import metrics as M
from .config import load_config, path
from .data import load_levels
from .features import H, build_table, holiday_dates, prepare_level
from .models import LevelModel, baseline_forecast
from .utils import dump_json, iso, parse_origin, run_id_for

WEATHER_SOURCE = "dataset-oracle"


def validate_forecast(fc: dict) -> None:
    need = {"run_id", "origin_time", "level", "entity_id", "unit", "slot_minutes", "model_version", "weather_source", "points", "history"}
    miss = need - set(fc)
    assert not miss, f"forecast missing keys {miss}"
    pts = fc["points"]
    assert len(pts) == 48, f"expected 48 points, got {len(pts)}"
    assert [p["slot"] for p in pts] == list(range(48)), "slots must be 0..47 in order"
    for p in pts:
        assert p["p10"] <= p["p50"] <= p["p90"], f"quantile order violated at slot {p['slot']}"
        assert all(np.isfinite([p["p10"], p["p50"], p["p90"]])), "non-finite forecast value"


def _predict(kind: str, level: str, tab: pd.DataFrame, models: dict) -> pd.DataFrame:
    return baseline_forecast(tab) if kind == "baseline" else models[level].predict(tab)


def _forecast_json(cfg, run_id, origin, level, eid, tab_e, pred_e, g, o, kind, version) -> dict:
    tz = cfg["time"]["tz"]
    p = pred_e.reset_index(drop=True)
    ts = pd.DatetimeIndex(tab_e["ts_target"].to_numpy())
    pts = [{"slot": i, "timestamp": iso(ts[i], tz), "p10": round(float(p.p10[i]), 3),
            "p50": round(float(p.ensemble[i]), 3), "p90": round(float(p.p90[i]), 3)} for i in range(H)]
    hist = g.iloc[o - H:o]
    return {"run_id": run_id, "origin_time": iso(origin, tz), "level": level, "entity_id": str(eid), "unit": "kW",
            "slot_minutes": cfg["time"]["slot_minutes"], "model_version": version, "weather_source": WEATHER_SOURCE,
            "points": pts,
            "history": [{"timestamp": iso(t, tz), "actual": round(float(a), 3)}
                        for t, a in zip(hist["timestamp"], hist["load_kw"]) if np.isfinite(a)]}


def _live_accuracy(kind, models, port_df, cfg, hol, o):
    """MAE of the previous 7 daily origins (portfolio), ensemble vs seasonal naive."""
    prev = [o - 48 * k for k in range(1, 8) if o - 48 * k >= cfg["features"]["min_history_days"] * 48]
    if not prev:
        return None
    t = build_table(port_df, cfg, hol, origins=np.array(prev))
    pr = _predict(kind, "portfolio", t, models)
    ok = t["y_kw"].notna().to_numpy()
    m, n = M.mae(t["y_kw"][ok], pr["ensemble"][ok]), M.mae(t["y_kw"][ok], t["naive_d1"][ok])
    return {"mae_kw": round(m, 3), "skill_vs_naive": round(1 - m / n, 3) if n > 0 else None}


def _drivers(cfg, wdf: pd.DataFrame, peak_ts: pd.Timestamp, is_hol: bool) -> list[str]:
    f = cfg["features"]
    out = []
    if "T2M" in wdf:
        tmax, tmin = float(wdf["T2M"].max()), float(wdf["T2M"].min())
        if not (-20.0 <= tmax <= 60.0):
            out.append("Temperature data out of range (check weather columns)")
        else:
            out.append(f"Hot day (max {tmax:.0f} C)" if tmax >= f["hot_c"] else
                       f"Cold day (min {tmin:.0f} C)" if tmin <= f["cold_c"] else f"Mild day (max {tmax:.0f} C)")
    day = "Public holiday" if is_hol else ("Weekend" if peak_ts.dayofweek >= 5 else "Weekday")
    h = peak_ts.hour
    period = "evening" if 17 <= h < 22 else "morning" if 6 <= h < 10 else "daytime" if 10 <= h < 17 else "overnight"
    out.append(f"{day} {period} peak around {peak_ts:%H:%M}")
    if "ALLSKY_SFC_SW_DWN" in wdf:
        a = wdf.set_index("timestamp")["ALLSKY_SFC_SW_DWN"]
        out.append("Low solar at the time of the peak" if a.loc[peak_ts] <= 0.05 * max(a.max(), 1e-9) else "Solar available at the time of the peak")
    return out[:3]


def _explain_context(cfg, run_id, fc, port_g, o, acc, is_hol, in_sample) -> dict:
    tz = cfg["time"]["tz"]
    pts = fc["points"]
    p50 = np.array([p["p50"] for p in pts])
    width = np.array([p["p90"] - p["p10"] for p in pts])
    k = int(p50.argmax())
    ts = pd.DatetimeIndex(port_g["timestamp"].to_numpy()[o:o + H])
    peak_ts = ts[k]
    w = widest = int(width.argmax())
    caveats = ["Weather values are actual observations used as a perfect forecast (replay mode)."]
    if in_sample:
        caveats.append("The model was trained on data that includes this day (in-sample), so accuracy is optimistic.")
    return {"run_id": run_id,
            "peak": {"time": pts[k]["timestamp"], "p50_kw": pts[k]["p50"], "p90_kw": pts[k]["p90"]},
            "total_kwh_next_24h": round(float(p50.sum() * cfg["time"]["slot_minutes"] / 60), 1),
            "drivers": _drivers(cfg, port_g.iloc[o:o + H][[c for c in ("timestamp", "T2M", "ALLSKY_SFC_SW_DWN") if c in port_g]], peak_ts, is_hol),
            "band_width_note": f"P10-P90 band is widest at {ts[w]:%H:%M} ({width[w]:.1f} kW wide)",
            "accuracy_last_7_days": acc,
            "caveats": caveats}
    # alerts_summary / plan_summary are added by the backend (alerts + optimizer live there)


def run_cycle(cfg: dict, origin_str: str, model: str = "ensemble", levels=("portfolio", "zone", "house"), force: bool = False) -> str:
    t0 = time.time()
    tz = cfg["time"]["tz"]
    origin = parse_origin(origin_str, tz)
    run_id = run_id_for(origin)
    rdir = path(cfg, "runs_dir", run_id)
    if (rdir / "forecast.json").exists() and not force:
        print(f"run {run_id} already exists (use --force to overwrite)")
        return run_id
    L = load_levels(cfg)
    port = L["portfolio"]
    grid = pd.DatetimeIndex(port["timestamp"])
    o = int(grid.searchsorted(origin))
    if o >= len(grid) or grid[o] != origin:
        raise ValueError(f"origin {origin} is not on the data grid ({grid[0]} .. {grid[-1]}, 30-min slots)")
    if o < cfg["features"]["min_history_days"] * 48 or o + H > len(grid):
        raise ValueError(f"origin {origin} needs >= {cfg['features']['min_history_days']} days of history and 48 slots of weather after it; "
                         f"valid origins are {grid[cfg['features']['min_history_days'] * 48]} .. {grid[len(grid) - H]}")
    hol = holiday_dates(cfg, port["timestamp"])
    models, in_sample, version, train_end = {}, False, "baseline-seasonal-naive-v1", None
    if model == "ensemble":
        mp = path(cfg, "models_dir")
        try:
            models = {lv: LevelModel.load(mp / f"ensemble_{lv}.joblib") for lv in levels}
            train_end = json.loads((mp / "meta.json").read_text())["train_end"]
        except FileNotFoundError:
            raise SystemExit("No trained models found. Run: python -m ml.train   (or use --model baseline)")
        in_sample = bool(origin.normalize() < pd.Timestamp(train_end))
        version = "ensemble-v1"
        if in_sample:
            print(f"[warn] origin {origin.date()} is before the model's train_end {train_end}: in-sample, accuracy is optimistic")
    timings = {"load_s": round(time.time() - t0, 2)}
    entities = {"portfolio": ["all"], "zone": [], "house": []}
    forecasts, portfolio_fc = [], None
    for level in levels:
        ts0 = time.time()
        lv_df = prepare_level(L[level], cfg)
        tab = build_table(lv_df, cfg, hol, origins=np.array([o]))
        pr = _predict(model, level, tab, models)
        for eid in dict.fromkeys(lv_df["entity_id"]):
            m = (tab["entity_id"] == eid).to_numpy()
            g = lv_df[lv_df["entity_id"] == eid].reset_index(drop=True)
            fc = _forecast_json(cfg, run_id, origin, level, eid, tab[m], pr[m], g, o, model, version)
            validate_forecast(fc)
            dump_json(fc, rdir / f"forecast_{level}_{eid}.json")
            if level != "portfolio":
                entities[level].append(str(eid))
            else:
                portfolio_fc, port_g = fc, g
        timings[f"{level}_s"] = round(time.time() - ts0, 2)
    assert portfolio_fc is not None, "portfolio level is required"
    dump_json(portfolio_fc, rdir / "forecast.json")
    acc = _live_accuracy(model, models, prepare_level(port, cfg), cfg, hol, o)
    is_hol = bool(origin.normalize() in hol)
    dump_json(_explain_context(cfg, run_id, portfolio_fc, port_g, o, acc, is_hol, in_sample), rdir / "explain_context.json")
    # metrics.json: backtest numbers (contract shape) + live last-7-day numbers
    mpath = path(cfg, "reports_dir", "metrics_backtest.json")
    metrics = json.loads(mpath.read_text()) if mpath.exists() else {
        "scope": "not_run_yet", "by_model": [], "by_hour": [], "by_weekday": [], "coverage_p10_p90": None, "last_7_days_mae": None}
    if acc:
        metrics["last_7_days_mae"] = acc["mae_kw"]
        bm = {r["model"]: r["mae"] for r in metrics.get("by_model", [])}
        if bm.get("ensemble"):
            metrics["drift_ratio"] = round(acc["mae_kw"] / bm["ensemble"], 4)
    dump_json(metrics, rdir / "metrics.json")
    dump_json(entities, rdir / "entities.json")
    sha = hashlib.sha256(port["load_kw"].to_numpy(float)[:o].tobytes() + open(cfg["_config_path"], "rb").read()).hexdigest()
    timings["total_s"] = round(time.time() - t0, 2)
    dump_json({"run_id": run_id, "origin_time": iso(origin, tz), "model": model, "model_version": version, "train_end": train_end,
               "in_sample": in_sample, "weather_source": WEATHER_SOURCE, "inputs_sha256": sha, "timings": timings,
               "created_at": pd.Timestamp.now(tz="UTC").isoformat(), "trigger": "cli"}, rdir / "run_meta.json")
    print(f"run {run_id} written to {rdir}  ({timings['total_s']}s, entities: 1 portfolio, {len(entities['zone'])} zones, {len(entities['house'])} houses)")
    return run_id


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Run one forecast cycle")
    ap.add_argument("--origin", default=None, help="local Sydney time e.g. 2013-02-15T00:00 (default: config replay.demo_origin)")
    ap.add_argument("--model", choices=["ensemble", "baseline"], default="ensemble")
    ap.add_argument("--levels", default="portfolio,zone,house")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--config", default=None)
    a = ap.parse_args()
    c = load_config(a.config)
    run_cycle(c, a.origin or c["replay"]["demo_origin"], a.model, tuple(a.levels.split(",")), a.force)
