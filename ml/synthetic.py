"""Synthetic Ausgrid-shaped CSV for offline tests (same raw columns as the real file)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def make_synthetic_csv(path, days: int = 150, n_houses: int = 6, n_zones: int = 3, start: str = "2012-07-01", seed: int = 0) -> None:
    rng = np.random.default_rng(seed)
    ts = pd.date_range(start, periods=days * 48, freq="30min")
    slot, doy, dow = ts.hour * 2 + ts.minute // 30, ts.dayofyear.to_numpy(), ts.dayofweek.to_numpy()
    temp = 18 + 7 * np.cos(2 * np.pi * (doy - 15) / 365) + 5 * np.sin(np.pi * (slot - 10) / 24) \
        + np.repeat(rng.normal(0, 2.5, days), 48)
    clr = 900 * np.maximum(0, np.sin(np.pi * (slot - 13) / 22))
    allsky = clr * np.repeat(rng.uniform(0.3, 1, days), 48)
    rows = []
    for h in range(1, n_houses + 1):
        size = rng.uniform(0.6, 1.8)
        shape = 0.5 + 0.7 * np.exp(-((slot - 38) ** 2) / 18) + 0.3 * np.exp(-((slot - 15) ** 2) / 12)
        load = size * shape * (1 + 0.04 * np.maximum(temp - 24, 0) + 0.03 * np.maximum(14 - temp, 0))
        load = load * np.where(dow >= 5, 1.1, 1.0) * rng.lognormal(0, 0.12, len(ts))
        solar = size * allsky / 1000 * 0.8
        rows.append(pd.DataFrame({
            "datetime": ts, "Community": f"Community_{h}", "Cluster": f"Cluster_{(h - 1) % n_zones}", "Num_Houses": 40,
            "Load_kWh": load, "Solar_kWh": solar, "ALLSKY_SFC_SW_DWN": allsky + rng.normal(0, 10, len(ts)).clip(-20),
            "CLRSKY_SFC_SW_DWN": clr, "T2M": temp, "PRECTOTCORR": rng.exponential(0.1, len(ts)),
            "QV2M": 8 + rng.normal(0, 1, len(ts)), "PS": 101 + rng.normal(0, 0.3, len(ts)),
            "WS10M": rng.uniform(0, 6, len(ts)), "T2MWET": temp - 3}))
    df = pd.concat(rows, ignore_index=True)
    df.loc[rng.choice(len(df), 40, replace=False), "Load_kWh"] = np.nan      # short gaps to exercise QC
    df.to_csv(path, index=False)
