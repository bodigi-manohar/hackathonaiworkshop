"""Step 4: leakage-safe feature builder (horizon-as-feature layout).

One row = (entity, forecast origin, horizon h in 0..47). The forecast origin is 00:00 and the target
slot is origin + h. Load-derived features use only y[:origin] (history strictly before the origin):
  - same-slot lags at 1,2,3,7 days before the TARGET slot (always <= origin-1 because h < 48),
  - last value / rolling stats that end at origin-1.
Weather and calendar at the TARGET slot are treated as known in advance ("oracle weather" in backtests;
a noisy variant is built for the degraded-weather scenario).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

H = 48
LOAD_SCALED = ["lag_d1", "lag_d2", "lag_d3", "lag_w1", "ma7", "last", "rm6", "rm48", "rm336",
               "rs48", "rmax48", "rmin48", "solar_lag_d1"]
META = ["entity_id", "origin_idx", "origin_ts", "origin_day", "ts_target", "y_kw",
        "naive_d1", "naive_w1", "naive_ma7"]
WEATHER_FEATS = ["T2M", "cdd", "hdd", "ALLSKY_SFC_SW_DWN", "CLRSKY_SFC_SW_DWN", "cloud_ratio",
                 "PRECTOTCORR", "QV2M", "WS10M", "T2MWET", "PS"]


def feature_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in META]


def holiday_dates(cfg: dict, ts: pd.Series) -> pd.DatetimeIndex:
    try:
        import holidays
        years = list(range(int(ts.min().year) - 1, int(ts.max().year) + 2))
        h = holidays.Australia(subdiv=cfg["features"]["holiday_state"], years=years)
        return pd.DatetimeIndex(sorted(pd.Timestamp(d) for d in h.keys()))
    except Exception as e:  # holidays package missing -> no holiday flag, loudly
        print(f"[warn] holiday calendar unavailable ({e}); is_holiday = 0")
        return pd.DatetimeIndex([])


def prepare_level(level_df: pd.DataFrame, cfg: dict, noise_seed: int | None = None) -> pd.DataFrame:
    """Add derived weather columns. noise_seed != None adds seeded Gaussian noise to temperature and
    radiation (one noise value per timestamp, shared by all entities) to mimic forecast error."""
    df = level_df.copy()
    if noise_seed is not None:
        n = cfg["backtest"]["noise"]
        uniq = np.sort(df["timestamp"].unique())
        rng = np.random.default_rng(noise_seed)
        t_noise = pd.Series(rng.normal(0, n["temp_c"], len(uniq)), index=uniq)
        r_noise = pd.Series(rng.normal(0, n["radiation_w_m2"], len(uniq)), index=uniq)
        if "T2M" in df:
            df["T2M"] = df["T2M"] + df["timestamp"].map(t_noise).to_numpy()
        if "ALLSKY_SFC_SW_DWN" in df:
            df["ALLSKY_SFC_SW_DWN"] = (df["ALLSKY_SFC_SW_DWN"] + df["timestamp"].map(r_noise).to_numpy()).clip(lower=0)
    if "T2M" in df:
        df["cdd"] = (df["T2M"] - 22.0).clip(lower=0)
        df["hdd"] = (16.0 - df["T2M"]).clip(lower=0)
    if {"ALLSKY_SFC_SW_DWN", "CLRSKY_SFC_SW_DWN"} <= set(df.columns):
        clr = df["CLRSKY_SFC_SW_DWN"]
        df["cloud_ratio"] = np.where(clr > 0, (df["ALLSKY_SFC_SW_DWN"] / clr.clip(lower=0.1)).clip(0, 1), 0.0)
    return df


def entity_block(g: pd.DataFrame, origins: np.ndarray, hol: pd.DatetimeIndex) -> pd.DataFrame:
    y = g["load_kw"].to_numpy(float)
    s = g["solar_kw"].to_numpy(float)
    ts = g["timestamp"].to_numpy()
    O = np.asarray(origins, dtype=int)
    n = len(O)
    idx = O[:, None] + np.arange(H)[None, :]                       # (n, 48) target positions
    yz, nan = np.nan_to_num(y), np.isnan(y).astype(float)
    cs, cs2, cn = (np.r_[0.0, np.cumsum(a)] for a in (yz, yz ** 2, nan))

    def wmean(end, w):
        m = (cs[end] - cs[end - w]) / w
        return np.where(cn[end] - cn[end - w] > 0, np.nan, m)

    def wstd(end, w):
        m = (cs[end] - cs[end - w]) / w
        v = (cs2[end] - cs2[end - w]) / w - m ** 2
        return np.where(cn[end] - cn[end - w] > 0, np.nan, np.sqrt(np.clip(v, 0, None)))

    win = sliding_window_view(y, 48)
    bc = lambda a: np.broadcast_to(np.asarray(a)[:, None], (n, H)).ravel()
    lag = lambda k: y[idx - 48 * k]

    f: dict[str, np.ndarray] = {}
    f["horizon"] = np.tile(np.arange(H), n)
    # --- calendar at target slot (known in advance)
    tt = pd.DatetimeIndex(ts[idx.ravel()])
    slot = tt.hour.to_numpy() * 2 + tt.minute.to_numpy() // 30
    dow = tt.dayofweek.to_numpy()
    f["slot"] = slot
    for j in (1, 2, 3):
        f[f"slot_sin{j}"] = np.sin(2 * np.pi * j * slot / 48)
        f[f"slot_cos{j}"] = np.cos(2 * np.pi * j * slot / 48)
    f["dow"] = dow
    f["dow_sin"], f["dow_cos"] = np.sin(2 * np.pi * dow / 7), np.cos(2 * np.pi * dow / 7)
    f["is_weekend"] = (dow >= 5).astype(int)
    f["is_holiday"] = tt.normalize().isin(hol).astype(int)
    f["solar_angle"] = np.maximum(0.0, np.sin(np.pi * (slot - 13) / 22))
    # --- load-derived features, all strictly before the origin
    f["lag_d1"], f["lag_d2"], f["lag_d3"], f["lag_w1"] = (lag(k).ravel() for k in (1, 2, 3, 7))
    f["ma7"] = np.mean([lag(k) for k in range(1, 8)], axis=0).ravel()
    f["last"] = bc(y[O - 1])
    f["rm6"], f["rm48"], f["rm336"] = (bc(wmean(O, w)) for w in (6, 48, 336))
    f["rs48"] = bc(wstd(O, 48))
    f["rmax48"], f["rmin48"] = bc(win[O - 48].max(axis=1)), bc(win[O - 48].min(axis=1))
    f["trend_ratio"] = bc(wmean(O, 48) / (wmean(O - 48, 48) + 1e-6))
    f["solar_lag_d1"] = s[idx - 48].ravel()
    # --- weather at target slot (+ origin-based history)
    for c in WEATHER_FEATS:
        if c in g:
            f[f"w_{c}"] = g[c].to_numpy(float)[idx].ravel()
    if "T2M" in g:
        t = g["T2M"].to_numpy(float)
        ct = np.r_[0.0, np.cumsum(t)]
        f["t2m_prev_day_mean"] = bc((ct[O] - ct[O - 48]) / 48)
        f["t2m_vs_prev_day"] = (t[idx] - t[idx - 48]).ravel()
    if "ALLSKY_SFC_SW_DWN" in g:
        f["clear_sky_proxy"] = f["solar_angle"] * g["CLRSKY_SFC_SW_DWN"].to_numpy(float)[idx].ravel() \
            if "CLRSKY_SFC_SW_DWN" in g else f["solar_angle"]
    out = pd.DataFrame(f)
    out["origin_idx"] = np.repeat(O, H)
    out["origin_ts"] = np.repeat(ts[O], H)
    out["origin_day"] = pd.DatetimeIndex(out["origin_ts"]).normalize()
    out["ts_target"] = ts[idx.ravel()]
    out["y_kw"] = y[idx].ravel()
    out["naive_d1"], out["naive_w1"], out["naive_ma7"] = f["lag_d1"], f["lag_w1"], f["ma7"]
    return out


def build_table(level_df: pd.DataFrame, cfg: dict, hol: pd.DatetimeIndex | None = None,
                origins: np.ndarray | None = None) -> pd.DataFrame:
    """Feature table for every valid 00:00 origin (or for the explicit `origins` grid positions).
    level_df must be sorted by (entity_id, timestamp) on one common regular grid."""
    hol = holiday_dates(cfg, level_df["timestamp"]) if hol is None else hol
    min_hist = cfg["features"]["min_history_days"] * 48
    entities = list(dict.fromkeys(level_df["entity_id"]))
    frames = []
    for code, eid in enumerate(entities):
        g = level_df[level_df["entity_id"] == eid].reset_index(drop=True)
        if origins is None:
            ts = g["timestamp"]
            O = np.flatnonzero(((ts.dt.hour == 0) & (ts.dt.minute == 0)).to_numpy())
            O = O[(O >= min_hist) & (O + H <= len(g))]
        else:
            O = np.asarray(origins, dtype=int)
        blk = entity_block(g, O, hol)
        blk["entity_id"], blk["entity_code"] = eid, code
        frames.append(blk)
    df = pd.concat(frames, ignore_index=True)
    if len(entities) == 1:
        df = df.drop(columns="entity_code")
    return df
