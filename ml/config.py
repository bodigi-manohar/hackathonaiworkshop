"""Config loading and path helpers. No hardcoded paths anywhere else."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_config(path: str | None = None) -> dict:
    p = Path(path) if path else Path(__file__).with_name("config.yaml")
    cfg = yaml.safe_load(p.read_text())
    cfg["_config_path"] = str(p)
    env = os.environ.get("GRIDSIGHT_RAW_CSV")
    if env:
        cfg["paths"]["raw_csv"] = env
    return cfg


def path(cfg: dict, key: str, *parts: str, mkdir: bool = False) -> Path:
    """Resolve cfg['paths'][key]/parts relative to the repo root. mkdir creates the directory
    (or the parent directory when the result looks like a file)."""
    p = Path(cfg["paths"][key])
    p = p if p.is_absolute() else ROOT / p
    p = p.joinpath(*parts)
    if mkdir:
        (p.parent if p.suffix else p).mkdir(parents=True, exist_ok=True)
    return p
