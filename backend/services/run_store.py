"""Run bundle store: reads runs/<run_id>/ files, falls back to contracts/sample (mock mode)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SYD = ZoneInfo("Australia/Sydney")

from backend.config import Settings
from backend.core.exceptions import ApiError, NotFoundError
from backend.schemas.run import RunListItem


@dataclass
class Bundle:
    path: Path
    run_id: str
    is_sample: bool


class RunStore:
    def __init__(self, settings: Settings):
        self.runs_dir = Path(settings.runs_dir)
        self.sample_dir = Path(settings.sample_dir)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def _run_folders(self) -> list[Path]:
        if not self.runs_dir.exists():
            return []
        return sorted(
            (p for p in self.runs_dir.iterdir() if p.is_dir() and (p / "forecast.json").is_file()),
            key=lambda p: (p / "forecast.json").stat().st_mtime,
        )

    @property
    def is_mock(self) -> bool:
        return not self._run_folders()

    def list_runs(self) -> list[RunListItem]:
        folders = self._run_folders()
        out: list[RunListItem] = []
        for p in reversed(folders):
            fc = json.loads((p / "forecast.json").read_text(encoding="utf-8"))
            created = datetime.fromtimestamp((p / "forecast.json").stat().st_mtime, tz=timezone.utc)
            out.append(RunListItem(run_id=p.name, origin_time=fc.get("origin_time", ""), created_at=created.isoformat()))
        if not out:
            s = self.load_sample("forecast.json")
            out.append(
                RunListItem(
                    run_id="sample",
                    origin_time=str(s.get("origin_time", "")),
                    created_at=datetime.now(tz=timezone.utc).isoformat(),
                )
            )
        return out

    def resolve(self, run_id: str | None) -> Bundle:
        if run_id in (None, "sample"):
            if self.is_mock:
                return Bundle(self.sample_dir, "sample", True)
            folders = self._run_folders()
            latest = folders[-1]
            return Bundle(latest, latest.name, False)
        p = self.runs_dir / run_id
        if (p / "forecast.json").is_file():
            return Bundle(p, run_id, False)
        if self.is_mock:
            return Bundle(self.sample_dir, "sample", True)
        known = ", ".join(f.name for f in self._run_folders()) or "none"
        raise NotFoundError(f"run '{run_id}' not found (known runs: {known})")

    def load_json(self, path: Path, name: str, run_id: str, default: object = None):
        f = Path(path) / name
        if f.is_file():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                raise ApiError(f"{name} for run '{run_id}' is not valid JSON: {e}") from e
        if default is not None:
            return default
        raise NotFoundError(f"{name} not found for run '{run_id}'")

    def load_sample(self, name: str):
        f = self.sample_dir / name
        if not f.is_file():
            raise NotFoundError(f"contract sample '{name}' missing from contracts/sample/")
        return json.loads(f.read_text(encoding="utf-8"))

    def entities(self) -> dict:
        return self.load_sample("entities.json")

    def find_run_by_origin(self, origin: datetime) -> Bundle | None:
        target = origin.astimezone(SYD) if origin.tzinfo else origin.replace(tzinfo=SYD)
        for p in self._run_folders():
            fc = json.loads((p / "forecast.json").read_text(encoding="utf-8"))
            raw = fc.get("origin_time", "")
            try:
                run_origin = datetime.fromisoformat(raw)
            except ValueError:
                continue
            if run_origin.tzinfo is None:
                run_origin = run_origin.replace(tzinfo=SYD)
            if run_origin.astimezone(SYD) == target:
                return Bundle(p, p.name, False)
        return None

    def recent_alerts(self, origin: datetime, hours: float) -> list[dict]:
        out: list[dict] = []
        window = timedelta(hours=hours)
        for p in self._run_folders():
            try:
                fc = json.loads((p / "forecast.json").read_text(encoding="utf-8"))
                run_origin = datetime.fromisoformat(fc.get("origin_time", ""))
            except (json.JSONDecodeError, ValueError):
                continue
            if abs(run_origin - origin) <= window:
                alerts = self.load_json(p, "alerts.json", p.name, default=[])
                out.extend(alerts)
        return out
