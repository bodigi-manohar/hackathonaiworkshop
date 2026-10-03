from fastapi import APIRouter

from backend.config import get_app_config
from backend.dependencies import DbSession
from backend.schemas.control import ControlOut
from backend.services.control_service import ControlService

router = APIRouter(tags=["control"])


@router.post("/control/override", response_model=ControlOut)
def control_override(
    db: DbSession = None,  # type: ignore[assignment]
) -> ControlOut:
    state = ControlService(db, get_app_config()).override()
    return ControlOut(control_enabled=state["control_enabled"], dry_run=state["dry_run"])
