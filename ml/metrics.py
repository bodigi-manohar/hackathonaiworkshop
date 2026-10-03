"""Metric functions (kW). Skill = 1 - MAE_model / MAE_seasonal_naive."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .models import MODEL_NAMES


def mae(y, p): return float(np.mean(np.abs(np.asarray(y) - np.asarray(p))))
def rmse(y, p): return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(p)) ** 2)))


def model_table(rec: pd.DataFrame) -> pd.DataFrame:
    base = mae(rec["y"], rec["seasonal_naive"])
    mean_y = float(rec["y"].mean())
    rows = []
    for m in MODEL_NAMES:
        e = mae(rec["y"], rec[m])
        rows.append({"model": m, "mae": e, "rmse": rmse(rec["y"], rec[m]), "nmae": e / mean_y,
                     "skill": 1.0 - e / base if base > 0 else float("nan")})
    return pd.DataFrame(rows)


def coverage(rec: pd.DataFrame) -> float:
    return float(((rec["y"] >= rec["p10"]) & (rec["y"] <= rec["p90"])).mean())


def pinball(rec: pd.DataFrame, qs=(0.1, 0.9)) -> float:
    tot = 0.0
    for q, col in zip(qs, ("p10", "p90")):
        d = rec["y"] - rec[col]
        tot += float(np.mean(np.maximum(q * d, (q - 1) * d)))
    return tot / 2


def by_hour(rec: pd.DataFrame, model="ensemble") -> pd.DataFrame:
    e = (rec["y"] - rec[model]).abs()
    return e.groupby(pd.DatetimeIndex(rec["ts_target"]).hour).mean().rename("mae").rename_axis("hour").reset_index()


def by_weekday(rec: pd.DataFrame, model="ensemble") -> pd.DataFrame:
    e = (rec["y"] - rec[model]).abs()
    return e.groupby(pd.DatetimeIndex(rec["ts_target"]).dayofweek).mean().rename("mae").rename_axis("weekday").reset_index()


def peak_errors(rec: pd.DataFrame, model="ensemble") -> dict:
    r = rec.sort_values(["entity_id", "origin_day", "horizon"])
    r = r[r.groupby(["entity_id", "origin_day"])["horizon"].transform("size") == 48]
    if r.empty:
        return {"peak_mae_kw": float("nan"), "peak_bias_kw": float("nan"), "peak_timing_mae_slots": float("nan")}
    Y, P = r["y"].to_numpy().reshape(-1, 48), r[model].to_numpy().reshape(-1, 48)
    d = P.max(1) - Y.max(1)
    return {"peak_mae_kw": float(np.abs(d).mean()), "peak_bias_kw": float(d.mean()),
            "peak_timing_mae_slots": float(np.abs(P.argmax(1) - Y.argmax(1)).mean())}
