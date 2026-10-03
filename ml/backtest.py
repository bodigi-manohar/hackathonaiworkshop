"""Step 5/8: expanding-window walk-forward backtest (daily 00:00 origins) -> metrics.json, report, xlsx, RESULTS.md.

Only walk-forward splits are used (no shuffled k-fold). For every fold:
  train origins  < val start | val origins = last `val_days` before test | test origins = the fold's days.
Two weather scenarios on the test rows: oracle (actual weather) and noisy (seeded Gaussian noise).
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from . import metrics as M
from .config import load_config, path
from .data import load_levels
from .features import build_table, holiday_dates, prepare_level
from .models import MODEL_NAMES, LevelModel
from .utils import dump_json, md_table


def make_folds(n_days: int, n_folds: int, fold_days: int, val_days: int) -> list[dict]:
    """Positions (in the sorted list of origin days). Train < val < test, always."""
    folds = []
    for k in range(n_folds):
        ts = n_days - (n_folds - k) * fold_days
        te = n_days - (n_folds - k - 1) * fold_days
        vs = ts - val_days
        if vs < 28:
            raise ValueError(f"Not enough history for {n_folds} folds of {fold_days} days (fold {k+1} would train on {vs} days). "
                             "Lower backtest.n_folds or fold_days in config.yaml.")
        folds.append({"fold": k + 1, "val_start": vs, "test_start": ts, "test_end": te})
    return folds


def _records(level, scen, fold, t: pd.DataFrame, pr: pd.DataFrame) -> pd.DataFrame:
    rec = pd.DataFrame({
        "level": level, "scenario": scen, "fold": fold, "entity_id": t["entity_id"].to_numpy(),
        "origin_day": t["origin_day"].to_numpy(), "horizon": t["horizon"].to_numpy(),
        "ts_target": t["ts_target"].to_numpy(), "y": t["y_kw"].to_numpy(),
        "seasonal_naive": t["naive_d1"].to_numpy(), "weekly_naive": t["naive_w1"].to_numpy(),
        "moving_average": t["naive_ma7"].to_numpy(),
        "ridge": pr["ridge"].to_numpy(), "lgbm": pr["lgbm"].to_numpy(), "ensemble": pr["ensemble"].to_numpy(),
        "p10": pr["p10"].to_numpy(), "p90": pr["p90"].to_numpy()})
    return rec.dropna()


def run_backtest(cfg: dict, levels: list[str] | None = None) -> dict:
    bt = cfg["backtest"]
    levels = levels or bt["levels"]
    L = load_levels(cfg)
    hol = holiday_dates(cfg, L["portfolio"]["timestamp"])
    recs = []
    for level in levels:
        print(f"\n=== {level.upper()} ===", flush=True)
        clean = build_table(prepare_level(L[level], cfg), cfg, hol)
        noisy = build_table(prepare_level(L[level], cfg, noise_seed=bt["seed"]), cfg, hol)
        assert (clean["origin_idx"].to_numpy() == noisy["origin_idx"].to_numpy()).all()
        days = np.sort(clean["origin_day"].unique())
        pos = np.searchsorted(days, clean["origin_day"].to_numpy())
        for f in make_folds(len(days), bt["n_folds"], bt["fold_days"], cfg["model"]["val_days"]):
            tr, va = pos < f["val_start"], (pos >= f["val_start"]) & (pos < f["test_start"])
            te = (pos >= f["test_start"]) & (pos < f["test_end"])
            assert days[:f["val_start"]].max() < days[f["val_start"]] <= days[f["test_start"] - 1] < days[f["test_start"]]
            model = LevelModel(cfg, level).fit(clean[tr], clean[va])
            for scen, tab in (("oracle", clean), ("noisy", noisy)):
                t = tab[te]
                recs.append(_records(level, scen, f["fold"], t, model.predict(t)))
            r = recs[-2]
            print(f"  fold {f['fold']}: train_days={f['val_start']} test={str(days[f['test_start']])[:10]}.."
                  f"{str(days[f['test_end']-1])[:10]}  MAE ens={M.mae(r.y, r.ensemble):.3f} "
                  f"naive={M.mae(r.y, r.seasonal_naive):.3f} w={np.round(model.weights,2)} q_adj={model.q_adj:.3f}", flush=True)
    rec = pd.concat(recs, ignore_index=True)
    return write_outputs(cfg, rec, levels)


def write_outputs(cfg: dict, rec: pd.DataFrame, levels: list[str]) -> dict:
    res: dict = {"by_level": {}}
    sheets: dict[str, pd.DataFrame] = {}
    for level in levels:
        for scen in ("oracle", "noisy"):
            r = rec[(rec.level == level) & (rec.scenario == scen)]
            if r.empty:
                continue
            tab = M.model_table(r)
            res["by_level"].setdefault(level, {})[scen] = {
                "by_model": tab.to_dict("records"), "coverage_p10_p90": M.coverage(r), "pinball": M.pinball(r),
                "peak": M.peak_errors(r),
                "by_fold": [{"fold": int(k), "ensemble_mae": M.mae(g.y, g.ensemble), "seasonal_naive_mae": M.mae(g.y, g.seasonal_naive),
                             "skill": 1 - M.mae(g.y, g.ensemble) / M.mae(g.y, g.seasonal_naive)} for k, g in r.groupby("fold")]}
            sheets[f"models_{level}_{scen}"[:31]] = tab
            sheets[f"folds_{level}_{scen}"[:31]] = pd.DataFrame(res["by_level"][level][scen]["by_fold"])
    head_level = "portfolio" if "portfolio" in levels else levels[0]
    hr = rec[(rec.level == head_level) & (rec.scenario == "oracle")]
    last7 = hr[hr.origin_day >= hr.origin_day.max() - pd.Timedelta(days=6)]
    ens_mae = M.mae(hr.y, hr.ensemble)
    head = res["by_level"][head_level]["oracle"]
    metrics = {
        "scope": "walk_forward_backtest", "headline_level": head_level,
        "by_model": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()} for row in head["by_model"]],
        "by_hour": M.by_hour(hr).round(4).to_dict("records"),
        "by_weekday": M.by_weekday(hr).round(4).to_dict("records"),
        "coverage_p10_p90": round(head["coverage_p10_p90"], 4),
        "last_7_days_mae": round(M.mae(last7.y, last7.ensemble), 4),
        "drift_ratio": round(M.mae(last7.y, last7.ensemble) / ens_mae, 4),
        "by_level": res["by_level"],
    }
    sheets["by_hour"], sheets["by_weekday"] = M.by_hour(hr), M.by_weekday(hr)
    sheets["coverage"] = pd.DataFrame([{"level": lv, "scenario": sc, "coverage_p10_p90": d["coverage_p10_p90"], "pinball": d["pinball"], **d["peak"]}
                                       for lv, v in res["by_level"].items() for sc, d in v.items()])
    rdir = path(cfg, "reports_dir", mkdir=True)
    dump_json(metrics, rdir / "metrics_backtest.json")
    try:
        with pd.ExcelWriter(rdir / "results.xlsx") as xw:
            for name, df in sheets.items():
                df.to_excel(xw, sheet_name=name, index=False)
    except Exception as e:
        print(f"[warn] xlsx not written: {e}")
    text = _report_md(metrics, res, rec, head_level)
    (rdir / "backtest.md").write_text(text)
    path(cfg, "docs_dir", "RESULTS.md", mkdir=True).write_text(text + _caveats())
    print("\n" + text)
    return metrics


def _report_md(metrics: dict, res: dict, rec: pd.DataFrame, head_level: str) -> str:
    out = ["# Walk-forward backtest\n",
           f"Expanding window, daily 00:00 origin, 48 half-hour slots, {rec['fold'].nunique()} folds. Units: kW. "
           f"Skill = 1 - MAE / MAE(seasonal naive). Headline level: **{head_level}**.\n"]
    for level, v in res["by_level"].items():
        for scen, d in v.items():
            out.append(f"\n## {level} - {scen} weather\n")
            out.append(md_table(pd.DataFrame(d["by_model"])))
            out.append(f"\nCoverage P10-P90: {d['coverage_p10_p90']:.3f} (target ~0.80) | pinball: {d['pinball']:.3f} | "
                       f"peak MAE: {d['peak']['peak_mae_kw']:.2f} kW | peak timing error: {d['peak']['peak_timing_mae_slots']:.2f} slots\n")
            bm = {r["model"]: r for r in d["by_model"]}
            ok = bm["ensemble"]["mae"] < bm["seasonal_naive"]["mae"]
            out.append(f"\n**Ensemble beats seasonal-naive: {'YES' if ok else 'NO'}** "
                       f"(skill {bm['ensemble']['skill']:.3f}).\n")
            out.append("\nPer fold:\n\n" + md_table(pd.DataFrame(d["by_fold"])))
    out.append(f"\nLast-7-days MAE ({head_level}): {metrics['last_7_days_mae']:.3f} kW, drift ratio {metrics['drift_ratio']:.3f}\n")
    return "\n".join(out)


def _caveats() -> str:
    return ("\n## Notes and honest caveats\n\n"
            "- Headline accuracy is portfolio/zone level; house level is noisy by nature and is reported as is.\n"
            "- 'oracle' = actual observed weather used as the forecast; 'noisy' adds seeded Gaussian noise (see config) to mimic real forecast error.\n"
            "- Solar output is not forecast in this build (it is only used as a lagged feature), so the night-zero solar caveat does not affect these numbers.\n"
            "- The dataset covers about one year, so a calendar-month feature is not used (it would only memorise the seasons).\n"
            "- Blend weights and the P10/P90 calibration are learned on a 14-day validation block directly before each test fold.\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Walk-forward backtest")
    ap.add_argument("--config", default=None)
    ap.add_argument("--levels", default=None, help="comma list, e.g. portfolio,zone (faster)")
    a = ap.parse_args()
    run_backtest(load_config(a.config), a.levels.split(",") if a.levels else None)
