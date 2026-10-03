"""Step 2: raw CSV -> tidy house / zone / portfolio parquet tables + QC report + entities.json.

Time handling: the dataset is a wall-clock grid with exactly 48 slots per day, so we index by
Australia/Sydney wall-clock time (naive, regular 30-min grid). Offsets are added only when we
write ISO strings for the JSON outputs (see utils.iso).
Unit: raw values are kWh per 30 min -> kW = kWh * 2.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from .config import load_config, path
from .utils import dump_json


def load_raw(cfg: dict) -> pd.DataFrame:
    rc = cfg["raw_columns"]
    df = pd.read_csv(path(cfg, "raw_csv"))
    ts = pd.to_datetime(df[rc["timestamp"]])
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert(cfg["time"]["tz"]).dt.tz_localize(None)
    k = cfg["time"]["kwh_to_kw"]
    out = pd.DataFrame({
        "timestamp": ts,
        "house_raw": df[rc["house"]].astype(str),
        "zone_id": df[rc["zone"]].astype(str),
        "load_kw": df[rc["load"]].astype(float) * k,
        "solar_kw": df[rc["solar"]].astype(float) * k,
    })
    if rc.get("num_houses") in df.columns:
        out["num_houses"] = df[rc["num_houses"]].astype(float)
    for c in cfg["weather_columns"]:
        if c in df.columns:
            out[c] = df[c].astype(float)
    out = repair_weather(out, cfg)
    ids = out["house_raw"].str.extract(r"(\d+)$")[0]
    out["house_id"] = ids.where(ids.notna(), out["house_raw"])
    return out.drop(columns="house_raw")


OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"

_WEATHER_RANGES = {
    "T2M": (-25.0, 55.0),      # deg C
    "WS10M": (0.0, 40.0),      # m/s
    "PS": (850.0, 1080.0),     # hPa
    "QV2M": (0.0, 30.0),       # g/kg
}


def weather_looks_broken(df: pd.DataFrame) -> tuple[bool, str]:
    """True when a weather column holds physically impossible values (mislabeled/scrambled merge)."""
    for col, (lo, hi) in _WEATHER_RANGES.items():
        if col not in df.columns:
            continue
        v = df[col].dropna()
        if v.empty:
            continue
        mn, mx = float(v.min()), float(v.max())
        if mn < lo or mx > hi:
            return True, f"{col} range {mn:.1f}..{mx:.1f} outside [{lo:g}, {hi:g}]"
    return False, ""


def _open_meteo_hourly(cfg: dict, start, end) -> pd.DataFrame:
    """Hourly Sydney wall-clock weather from Open-Meteo archive, cached under data/cache/weather/."""
    import requests

    cache_dir = path(cfg, "processed_dir").parent / "cache" / "weather"
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = f"openmeteo_{pd.Timestamp(start):%Y%m%d}_{pd.Timestamp(end):%Y%m%d}.parquet"
    cache = cache_dir / key
    if cache.exists():
        return pd.read_parquet(cache)
    params = {
        "latitude": cfg["weather"]["latitude"],
        "longitude": cfg["weather"]["longitude"],
        "start_date": pd.Timestamp(start).strftime("%Y-%m-%d"),
        "end_date": pd.Timestamp(end).strftime("%Y-%m-%d"),
        "hourly": "temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m,precipitation",
        "timezone": cfg["weather"].get("timezone", "Australia/Sydney"),
    }
    r = requests.get(OPEN_METEO_ARCHIVE, params=params, timeout=60)
    r.raise_for_status()
    h = r.json()["hourly"]
    w = pd.DataFrame({
        "temperature_2m": h["temperature_2m"],
        "relative_humidity_2m": h["relative_humidity_2m"],
        "surface_pressure": h["surface_pressure"],
        "wind_speed_10m": h["wind_speed_10m"],
        "precipitation": h["precipitation"],
    }, index=pd.to_datetime(h["time"]))
    w.index.name = "timestamp"
    w = w[~w.index.duplicated(keep="first")].sort_index()
    w.to_parquet(cache)
    print(f"[data] Open-Meteo weather cached to {cache}")
    return w


def repair_weather(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Replace implausible weather columns with Open-Meteo values, keeping the same column names.

    The Kaggle dataset's weather block is mislabeled (e.g. T2M actually holds radiation), so when the
    ranges fail we rebuild T2M/QV2M/PS/WS10M/T2MWET/PRECTOTCORR from the Open-Meteo archive for Sydney.
    If the fetch fails, the weather columns are dropped loudly - never silently used.
    """
    broken, why = weather_looks_broken(df)
    if not broken:
        return df
    ts = pd.to_datetime(df["timestamp"])
    try:
        w = _open_meteo_hourly(cfg, ts.min().normalize(), ts.max().normalize() + pd.Timedelta(days=1))
    except Exception as e:
        print(f"[warn] weather repair failed ({e}); dropping weather columns")
        return df.drop(columns=[c for c in cfg["weather_columns"] if c in df.columns])
    m = w.reindex(ts.dt.floor("1h"))
    t = m["temperature_2m"].to_numpy(float)
    rh = m["relative_humidity_2m"].to_numpy(float)
    p = m["surface_pressure"].to_numpy(float)
    ws = m["wind_speed_10m"].to_numpy(float)
    es = 0.6108 * np.exp(17.27 * t / (t + 237.3))            # kPa
    e_hpa = (rh / 100.0) * es * 10.0                          # hPa
    q = 622.0 * e_hpa / (p - 0.378 * e_hpa)                   # g/kg
    wet_bulb = (t * np.arctan(0.151977 * np.sqrt(rh + 8.313659))
                + np.arctan(t + rh) - np.arctan(rh - 1.676331)
                + 0.00391838 * rh ** 1.5 * np.arctan(0.023101 * rh) - 4.686035)
    out = df.copy()
    out["T2M"] = t
    out["QV2M"] = q
    out["PS"] = p
    out["WS10M"] = ws
    out["T2MWET"] = wet_bulb
    if "PRECTOTCORR" in out.columns:
        out["PRECTOTCORR"] = m["precipitation"].to_numpy(float)
    print(f"[data] repaired weather columns from Open-Meteo ({why})")
    return out


def _fill_short_gaps(s: pd.Series, max_gap: int) -> pd.Series:
    """Interpolate only gaps of length <= max_gap; longer gaps stay NaN (excluded later)."""
    na = s.isna()
    run = (na != na.shift()).cumsum()
    run_len = na.groupby(run).transform("sum")
    fillable = na & (run_len <= max_gap)
    interp = s.interpolate(limit_area="inside")
    out = s.copy()
    out[fillable] = interp[fillable]
    return out


def tidy_houses(raw: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict]:
    step = f"{cfg['time']['slot_minutes']}min"
    max_gap = cfg["data"]["max_gap_slots"]
    k = cfg["data"]["outlier_mad_k"]
    wcols = [c for c in cfg["weather_columns"] if c in raw.columns]
    qc: dict = {"rows_raw": int(len(raw)), "duplicates_removed": int(raw.duplicated(["house_id", "timestamp"]).sum())}
    raw = raw.drop_duplicates(["house_id", "timestamp"], keep="last")
    full = pd.date_range(raw["timestamp"].min(), raw["timestamp"].max(), freq=step)
    qc.update(expected_slots_per_house=int(len(full)), date_start=str(full[0]), date_end=str(full[-1]))
    per_house, parts = {}, []
    for hid, g in raw.groupby("house_id", sort=False):
        zone = g["zone_id"].iloc[0]
        nh = g["num_houses"].iloc[0] if "num_houses" in g else np.nan
        g = g.set_index("timestamp").sort_index().reindex(full)
        missing = int(g["load_kw"].isna().sum())
        negative = int((g[["load_kw", "solar_kw"]] < 0).sum().sum())
        for c in ("load_kw", "solar_kw"):
            g[c] = _fill_short_gaps(g[c].clip(lower=0), max_gap)
        for c in wcols:
            g[c] = g[c].interpolate(limit_direction="both").ffill().bfill()
        med = g["load_kw"].median()
        mad = (g["load_kw"] - med).abs().median()
        outliers = int(((g["load_kw"] - med).abs() > k * 1.4826 * mad).sum()) if mad > 0 else 0
        per_house[str(hid)] = {"missing_slots": missing, "negative_values_clipped": negative,
                               "long_gap_slots_left_nan": int(g["load_kw"].isna().sum()), "outliers_flagged": outliers}
        g["house_id"], g["zone_id"], g["num_houses"] = str(hid), zone, nh
        g.index.name = "timestamp"
        parts.append(g.reset_index())
    out = pd.concat(parts, ignore_index=True)
    out["net_load_kw"] = out["load_kw"] - out["solar_kw"]
    qc["per_house"] = per_house
    qc["totals"] = {k_: int(sum(v[k_] for v in per_house.values())) for k_ in next(iter(per_house.values()))}
    return out, qc


def _agg(houses: pd.DataFrame, keys: list[str], wcols: list[str]) -> pd.DataFrame:
    g = houses.groupby(keys)
    out = g[["load_kw", "solar_kw"]].sum(min_count=1)
    incomplete = g["load_kw"].count() < g["load_kw"].size()
    out.loc[incomplete, ["load_kw", "solar_kw"]] = np.nan      # never publish partial sums as complete
    for c in wcols:
        out[c] = g[c].mean()
    out["net_load_kw"] = out["load_kw"] - out["solar_kw"]
    return out.reset_index()


def aggregate(houses: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    wcols = [c for c in cfg["weather_columns"] if c in houses.columns]
    zone = _agg(houses, ["zone_id", "timestamp"], wcols)
    h2 = houses.assign(_all="all")
    port = _agg(h2, ["_all", "timestamp"], wcols).rename(columns={"_all": "entity_id"})
    return zone, port


def entities_dict(houses: pd.DataFrame) -> dict:
    key = lambda s: (0, int(s)) if str(s).isdigit() else (1, str(s))
    return {"portfolio": ["all"],
            "zone": sorted(houses["zone_id"].unique().tolist(), key=key),
            "house": sorted(houses["house_id"].unique().tolist(), key=key)}


def write_schema_doc(cfg: dict, raw: pd.DataFrame, houses: pd.DataFrame, qc: dict, ent: dict) -> None:
    zone_sizes = houses.groupby("zone_id")["house_id"].nunique().to_dict()
    lines = [
        "# DATA_SCHEMA (auto-generated by `python -m ml.data`)", "",
        f"- Source file: `{cfg['paths']['raw_csv']}`",
        f"- Raw rows: {qc['rows_raw']:,}  |  duplicates removed: {qc['duplicates_removed']}",
        f"- Date range: {qc['date_start']} -> {qc['date_end']} ({qc['expected_slots_per_house']:,} slots per house, 30 min)",
        f"- Houses: {len(ent['house'])}  |  Zones: {len(ent['zone'])}  |  Portfolio: 1",
        f"- Zone = raw `{cfg['raw_columns']['zone']}` column; house = raw `{cfg['raw_columns']['house']}` column (trailing number).",
        f"- Houses per zone: {zone_sizes}",
        "- Units: raw kWh per 30 min x 2 = kW.",
        "- Time: dataset is a 48-slots-per-day wall-clock grid. Tables use naive Australia/Sydney wall-clock `timestamp`; "
        "JSON outputs add the Sydney UTC offset.",
        "- Weather: taken from the dataset's own weather columns (not Open-Meteo). Output label: `dataset-oracle` "
        "(actual observed weather used as a perfect forecast).", "",
        "## Processed tables (`data/processed/`)", "",
        "| file | columns |", "|---|---|",
        "| house.parquet | timestamp, house_id, zone_id, num_houses, load_kw, solar_kw, net_load_kw, weather... |",
        "| zone.parquet | zone_id, timestamp, load_kw, solar_kw, net_load_kw, weather (mean) |",
        "| portfolio.parquet | entity_id('all'), timestamp, load_kw, solar_kw, net_load_kw, weather (mean) |", "",
        "## Quality (see `reports/data_quality.json`)", "", f"- Totals: {qc['totals']}", "",
        "Aggregates are NaN (not partial sums) in any slot where a member house is missing.", "",
    ]
    d = path(cfg, "docs_dir", "DATA_SCHEMA.md", mkdir=True)
    d.write_text("\n".join(lines))


def build_processed(cfg: dict) -> dict:
    raw = load_raw(cfg)
    houses, qc = tidy_houses(raw, cfg)
    zone, port = aggregate(houses, cfg)
    ent = entities_dict(houses)
    out = path(cfg, "processed_dir", mkdir=True)
    houses.to_parquet(out / "house.parquet", index=False)
    zone.to_parquet(out / "zone.parquet", index=False)
    port.to_parquet(out / "portfolio.parquet", index=False)
    dump_json(ent, out / "entities.json")
    cdir = path(cfg, "contracts_dir")
    if cdir.exists():
        dump_json(ent, cdir / "entities.json")
    dump_json(qc, path(cfg, "reports_dir", "data_quality.json", mkdir=True))
    write_schema_doc(cfg, raw, houses, qc, ent)
    print(f"houses={len(ent['house'])} zones={len(ent['zone'])} rows(house)={len(houses):,} "
          f"range={qc['date_start']}..{qc['date_end']}")
    print("QC totals:", qc["totals"])
    return {"house": houses, "zone": zone, "portfolio": port}


def _std(df: pd.DataFrame, level: str) -> pd.DataFrame:
    df = df.copy()
    df["entity_id"] = {"house": lambda: df["house_id"], "zone": lambda: df["zone_id"],
                       "portfolio": lambda: df["entity_id"] if "entity_id" in df else "all"}[level]()
    return df.sort_values(["entity_id", "timestamp"]).reset_index(drop=True)


def load_levels(cfg: dict, rebuild: bool = False) -> dict[str, pd.DataFrame]:
    """Return {'portfolio','zone','house'} frames with a common `entity_id` column, sorted, on one grid."""
    out_dir = path(cfg, "processed_dir")
    if rebuild or not (out_dir / "house.parquet").exists():
        tables = build_processed(cfg)
    else:
        tables = {k: pd.read_parquet(out_dir / f"{k}.parquet") for k in ("house", "zone", "portfolio")}
    return {k: _std(v, k) for k, v in tables.items()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build tidy house/zone/portfolio parquet + QC report")
    ap.add_argument("--config", default=None)
    build_processed(load_config(ap.parse_args().config))
