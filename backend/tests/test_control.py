"""Control service tests: override persistence, guardrail rejection, dry-run."""
from backend.config import get_app_config
from backend.db import session as db_session
from backend.services.control_service import ControlService


def make_service():
    db = db_session.SessionLocal()
    return db, ControlService(db, get_app_config())


def _big_plan():
    slots = []
    for t in range(48):
        slots.append(
            {
                "slot": t,
                "price": 0.2,
                "grid_before_kw": 100.0,
                "grid_after_kw": 100.0,
                "battery_charge_kw": 20.0 if t % 2 == 0 else 0.0,  # exceeds max_kw=12
                "battery_discharge_kw": 0.0,
                "soc_kwh": 50.0,
            }
        )
    return {"mode": "advisory", "slots": slots}


def test_override_disables_control(env):
    db, service = make_service()
    state = service.override()
    assert state["control_enabled"] is False
    # persisted: a fresh service sees the same state
    db2, service2 = make_service()
    assert service2.state()["control_enabled"] is False
    db.close()
    db2.close()


def test_apply_blocked_when_disabled(env):
    db, service = make_service()
    out = service.apply_plan(_big_plan())
    assert out["applied"] is False
    assert out["reason"] == "control disabled"
    db.close()


def test_guardrail_rejects_violating_plan(env):
    db, service = make_service()
    # enable control, disable dry-run, to reach the guardrail check
    from backend.models import ControlState

    row = db.get(ControlState, 1) or ControlState(id=1, enabled=True, dry_run=False)
    row.enabled = True
    row.dry_run = False
    db.add(row)
    db.commit()

    out = service.apply_plan(_big_plan(), run_id="test-run")
    assert out["applied"] is False
    assert out["reason"] == "guardrail violation"
    assert any("exceeds max" in v for v in out["violations"])
    db.close()


def test_valid_plan_applies_when_enabled(env):
    db, service = make_service()
    from backend.models import ControlState

    row = db.get(ControlState, 1) or ControlState(id=1, enabled=True, dry_run=False)
    row.enabled = True
    row.dry_run = False
    db.add(row)
    db.commit()

    slots = [
        {
            "slot": t,
            "battery_charge_kw": 5.0,
            "battery_discharge_kw": 0.0,
            "soc_kwh": 50.0 + t * 2.5,
        }
        for t in range(4)
    ]
    out = service.apply_plan({"mode": "advisory", "slots": slots})
    assert out["applied"] is True
    assert out["before"]["soc_kwh"] != out["after"]["soc_kwh"] or out["after"]["commands_applied"] > 0
    db.close()
