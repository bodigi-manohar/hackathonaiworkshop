from fastapi import APIRouter

from backend.config import get_app_config, get_settings
from backend.dependencies import DbSession, RunStoreDep
from backend.schemas.run import RunTriggerIn, RunTriggerOut
from backend.services.run_service import RunService

router = APIRouter(tags=["run"])


@router.post("/run", response_model=RunTriggerOut)
def post_run(
    body: RunTriggerIn,
    store: RunStoreDep = None,  # type: ignore[assignment]
    db: DbSession = None,  # type: ignore[assignment]
) -> RunTriggerOut:
    return RunService(get_settings(), get_app_config(), store, db).trigger(body.origin_time, body.force)
