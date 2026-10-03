"""Control service: guardrail-checked, logged actuation; override is persisted (FR-6xx)."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from backend.config import AppConfig
from backend.control import GuardrailLimits, SimulatedBatteryAdapter, check_plan
from backend.models import ControlState

logger = logging.getLogger("gridsight.control")


class ControlService:
    def __init__(self, db: Session, config: AppConfig):
        self.db = db
        self.config = config
        self._adapter = SimulatedBatteryAdapter(
            soc_initial_kwh=float(config.battery.get("soc_initial_kwh", 0.0)),
            max_kw=config.control_max_kw,
        )

    def _row(self) -> ControlState:
        row = self.db.get(ControlState, 1)
        if row is None:
            row = ControlState(
                id=1,
                enabled=self.config.control_enabled,
                dry_run=self.config.control_dry_run,
            )
            self.db.add(row)
            self.db.commit()
        return row

    def state(self) -> dict:
        row = self._row()
        return {"control_enabled": row.enabled, "dry_run": row.dry_run}

    def override(self) -> dict:
        """POST /control/override: disable control immediately and persist (FR-604)."""
        row = self._row()
        row.enabled = False
        self.db.commit()
        logger.warning("control override: control disabled (persisted)")
        return self.state()

    def apply_plan(self, plan: dict, run_id: str | None = None) -> dict:
        row = self._row()
        if not row.enabled:
            return {"applied": False, "reason": "control disabled"}
        if row.dry_run:
            return {"applied": False, "reason": "dry_run", "plan_run_id": run_id}

        limits = GuardrailLimits(
            max_kw=config_kw_limit(self),
            soc_min_kwh=float(self.config.battery.get("soc_min_kwh", 0.0)),
            soc_max_kwh=float(self.config.battery.get("capacity_kwh", float("inf"))),
            max_setpoint_change_kw=self.config.control_max_setpoint_change_kw,
        )
        violations = check_plan(plan, limits)
        if violations:
            logger.error("plan rejected by guardrails (run=%s): %s", run_id, violations)
            return {"applied": False, "reason": "guardrail violation", "violations": violations}

        before = self._adapter.read_state()
        try:
            result = self._adapter.apply_setpoints(plan)
        except ValueError as e:
            logger.error("apply_setpoints failed: %s", e)
            return {"applied": False, "reason": str(e)}
        after = self._adapter.read_state()
        logger.info("control applied run=%s before=%s after=%s", run_id, before, after)
        return {"applied": True, "before": before, "after": after, **result}


def config_kw_limit(service: ControlService) -> float:
    return service.config.control_max_kw
