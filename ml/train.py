"""Train the final per-level models used by run_cycle.

The final model only sees origins BEFORE --train-end (default from config replay.train_end), so replaying
any origin on/after that day is leakage-free. The last `val_days` before train-end are the validation block.
"""
from __future__ import annotations

import argparse
import subprocess

import numpy as np
import pandas as pd

from .config import load_config, path
from .data import load_levels
from .features import build_table, holiday_dates, prepare_level
from .models import LevelModel
from .utils import dump_json


def train_final(cfg: dict, levels: list[str] | None = None, train_end: str | None = None) -> dict:
    levels = levels or ["portfolio", "zone", "house"]
    L = load_levels(cfg)
    hol = holiday_dates(cfg, L["portfolio"]["timestamp"])
    val_days = cfg["model"]["val_days"]
    te = train_end or cfg["replay"].get("train_end")
    meta = {"levels": {}, "val_days": val_days}
    for level in levels:
        tab = build_table(prepare_level(L[level], cfg), cfg, hol)
        days = np.sort(tab["origin_day"].unique())
        end = pd.Timestamp(te) if te else days[-30]
        end = pd.Timestamp(end).normalize()
        vstart = end - pd.Timedelta(days=val_days)
        tr, va = tab["origin_day"] < vstart, (tab["origin_day"] >= vstart) & (tab["origin_day"] < end)
        if tr.sum() == 0 or va.sum() == 0:
            raise ValueError(f"train-end {end.date()} leaves no train/val rows (data {days[0]}..{days[-1]})")
        print(f"[{level}] train origins < {vstart.date()} ({int(tr.sum()):,} rows), val {vstart.date()}..{end.date()} ({int(va.sum()):,} rows)", flush=True)
        m = LevelModel(cfg, level).fit(tab[tr], tab[va])
        m.save(path(cfg, "models_dir", f"ensemble_{level}.joblib", mkdir=True))
        meta["levels"][level] = {"weights_ridge_lgbm": m.weights.tolist(), "q_adj": m.q_adj, "n_features": len(m.features),
                                 "features": m.features, "train_rows": int(tr.sum())}
        meta["train_end"] = str(end.date())
    try:
        meta["git_hash"] = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        meta["git_hash"] = None
    dump_json(meta, path(cfg, "models_dir", "meta.json", mkdir=True))
    print("saved models; train_end =", meta["train_end"])
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Train final models")
    ap.add_argument("--config", default=None)
    ap.add_argument("--train-end", default=None, help="YYYY-MM-DD; origins on/after this day are out-of-sample")
    ap.add_argument("--levels", default=None)
    a = ap.parse_args()
    train_final(load_config(a.config), a.levels.split(",") if a.levels else None, a.train_end)
