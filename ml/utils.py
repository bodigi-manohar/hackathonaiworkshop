"""Small shared helpers: time formatting, JSON writing, markdown tables."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


def iso(ts, tz: str) -> str:
    """Wall-clock timestamp -> ISO-8601 string with the Australia/Sydney offset."""
    t = pd.Timestamp(ts).tz_localize(tz, ambiguous=True, nonexistent="shift_forward")
    return t.isoformat()


def run_id_for(origin) -> str:
    return pd.Timestamp(origin).strftime("%Y-%m-%dT%H-%M")


def parse_origin(s: str, tz: str) -> pd.Timestamp:
    """Accepts '2013-02-15T00:00' (local Sydney) or with an offset / Z (converted to Sydney)."""
    t = pd.Timestamp(s)
    if t.tzinfo is not None:
        t = t.tz_convert(tz).tz_localize(None)
    return t


def _san(o):
    if isinstance(o, dict):
        return {str(k): _san(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_san(v) for v in o]
    if isinstance(o, (bool, np.bool_)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return float(o) if math.isfinite(o) else None
    if isinstance(o, (pd.Timestamp, np.datetime64)):
        return str(o)
    return o


def dump_json(obj, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_san(obj), indent=2, allow_nan=False))


def md_table(df: pd.DataFrame, nd: int = 3) -> str:
    if df.empty:
        return "_(no rows)_\n"
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for r in df.astype(object).itertuples(index=False):
        cells = [f"{v:.{nd}f}" if isinstance(v, (float, np.floating)) else str(v) for v in r]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"
