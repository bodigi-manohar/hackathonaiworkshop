"""Run orchestration: POST /run triggers ml.run_cycle, then alerts + optimizer + DB index.

Idempotency (FR-801): same origin_time returns the existing run unless force=True.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from backend.config import AppConfig, PROJECT_ROOT, Settings
from backend.core.exceptions import RunError
from backend.models import Alert, Run
from backend.optimizer import build_plan
from backend.services.run_store import Bundle, RunStore
from backend.schemas.run import RunTriggerOut
from backend.alerts import evaluate

logger = logging.getLogger("gridsight.run")
SYD = ZoneInfo("Australia/Sydney")


def ensure_bundle(bundle: Bundle, config: AppConfig, db: Session | None = None, store: RunStore | None = None) -> None:
    """Compute and persist alerts.json / plan.json next to the run bundle if missing."""
    if bundle.is_sample:
        return
    if not (bundle.path / "alerts.json").is_file():
        forecast = json.loads((bundle.path / "forecast.json").read_text(encoding="utf-8"))
        metrics_path = bundle.path / "metrics.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.is_file() else None
        context_path = bundle.path / "explain_context.json"
        context = json.loads(context_path.read_text(encoding="utf-8")) if context_path.is_file() else None
        existing: list[dict] = []
        if store is not None:
            try:
                origin = datetime.fromisoformat(forecast.get("origin_time", ""))
                existing = store.recent_alerts(origin, config.cooldown_hours)
            except ValueError:
                existing = []
        alerts, suppressed = evaluate(forecast, metrics, context, config, existing)
        if suppressed:
            logger.info("suppressed %d alert(s) by cooldown for run %s", len(suppressed), bundle.run_id)
        (bundle.path / "alerts.json").write_text(json.dumps(alerts, indent=2), encoding="utf-8")
        if db is not None:
            for a in alerts:
                db.add(
                    Alert(
                        run_id=bundle.run_id,
                        type=a["type"],
                        severity=a["severity"],
                        level=a["level"],
                        entity_id=a["entity_id"],
                        window_start=a["window_start"],
                        window_end=a["window_end"],
                        value=a["value"],
                        threshold=a["threshold"],
                        message=a["message"],
                        created_at=datetime.now(tz=timezone.utc),
                    )
                )
            db.commit()
    if not (bundle.path / "plan.json").is_file():
        forecast = json.loads((bundle.path / "forecast.json").read_text(encoding="utf-8"))
        plan = build_plan(forecast, config)
        (bundle.path / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        logger.info("wrote plan.json for run %s (saving=%.2f)", bundle.run_id, plan.get("saving", 0.0))
    # Backfill explain_context.json so the chat/LLM sees the computed alerts and plan
    ctx_path = bundle.path / "explain_context.json"
    if ctx_path.is_file():
        try:
            ctx = json.loads(ctx_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            ctx = {}
        alerts_path = bundle.path / "alerts.json"
        if alerts_path.is_file():
            try:
                ctx["alerts_summary"] = _alert_summary(json.loads(alerts_path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                pass
        plan_path = bundle.path / "plan.json"
        if plan_path.is_file():
            try:
                plan_now = json.loads(plan_path.read_text(encoding="utf-8"))
                before = float(plan_now.get("peak_before_kw") or 0.0)
                after = float(plan_now.get("peak_after_kw") or 0.0)
                ctx["plan_summary"] = {"saving": plan_now.get("saving"),
                                       "peak_reduction_kw": round(before - after, 1)}
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        ctx_path.write_text(json.dumps(ctx, indent=2), encoding="utf-8")


def _alert_summary(alerts: list[dict]) -> list[str]:
    """Contract format, e.g. ["1 peak alert (warn)"]."""
    if not alerts:
        return []
    counts: dict[tuple[str, str], int] = {}
    for a in alerts:
        key = (str(a.get("type", "alert")), str(a.get("severity", "info")))
        counts[key] = counts.get(key, 0) + 1
    return [f"{n} {t} alert ({s})" for (t, s), n in counts.items()]


class RunService:
    def __init__(self, settings: Settings, config: AppConfig, store: RunStore, db: Session):
        self.settings = settings
        self.config = config
        self.store = store
        self.db = db

    def _upsert_run(self, run_id: str, forecast: dict) -> None:
        if self.db.get(Run, run_id) is None:
            self.db.add(
                Run(
                    run_id=run_id,
                    origin_time=str(forecast.get("origin_time", "")),
                    created_at=datetime.now(tz=timezone.utc),
                    status="complete",
                    model_version=forecast.get("model_version"),
                )
            )
        self.db.commit()

    def index_existing_runs(self) -> None:
        for item in self.store.list_runs():
            if item.run_id == "sample":
                continue
            try:
                fc = self.store.load_json(self.store.runs_dir / item.run_id, "forecast.json", item.run_id)
            except Exception:
                continue
            self._upsert_run(item.run_id, fc)
            ensure_bundle(
                Bundle(Path(self.store.runs_dir / item.run_id), item.run_id, False),
                self.config,
                self.db,
                None,
            )

    def trigger(self, origin: datetime, force: bool = False) -> RunTriggerOut:
        if origin.tzinfo is None:
            # naive inputs are Australia/Sydney local time (PRD §4.6)
            origin = origin.replace(tzinfo=SYD)
        origin_local = origin.astimezone(SYD)
        slug = origin_local.strftime("%Y-%m-%dT%H-%M")

        existing = self.store.find_run_by_origin(origin)
        if existing is not None and not force:
            return RunTriggerOut(run_id=existing.run_id, origin_time=origin_local, already_existed=True)

        target_dir = self.store.runs_dir / slug
        if force and target_dir.is_dir():
            for name in ("alerts.json", "plan.json"):
                stale = target_dir / name
                if stale.is_file():
                    stale.unlink()

        origin_iso = origin_local.isoformat()
        logger.info("triggering ml.run_cycle for origin=%s", origin_iso)
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "ml.run_cycle", "--origin", origin_iso],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=self.settings.run_cycle_timeout_seconds,
            )
        except subprocess.TimeoutExpired as e:
            raise RunError(
                f"ml.run_cycle timed out after {self.settings.run_cycle_timeout_seconds}s"
            ) from e
        except OSError as e:
            raise RunError(f"could not start ml.run_cycle: {e}") from e

        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip()[-500:]
            raise RunError(f"ml.run_cycle failed (exit {proc.returncode}): {tail}")

        if not (target_dir / "forecast.json").is_file():
            folders = self.store._run_folders()
            if not folders:
                raise RunError("ml.run_cycle finished but produced no run folder with forecast.json")
            target_dir = folders[-1]
        forecast = json.loads((target_dir / "forecast.json").read_text(encoding="utf-8"))

        bundle = Bundle(target_dir, target_dir.name, False)
        ensure_bundle(bundle, self.config, self.db, self.store)
        self._upsert_run(target_dir.name, forecast)
        logger.info("run %s complete", target_dir.name)
        return RunTriggerOut(run_id=target_dir.name, origin_time=origin_local, already_existed=False)
