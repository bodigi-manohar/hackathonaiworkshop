from fastapi import APIRouter

from backend.config import get_app_config
from backend.dependencies import DbSession, RunStoreDep
from backend.schemas.alerts import Alert
from backend.services.run_service import ensure_bundle

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=list[Alert])
def get_alerts(
    run_id: str | None = None,
    store: RunStoreDep = None,  # type: ignore[assignment]
    db: DbSession = None,  # type: ignore[assignment]
) -> list[dict]:
    bundle = store.resolve(run_id)
    ensure_bundle(bundle, get_app_config(), db, store)
    return store.load_json(bundle.path, "alerts.json", bundle.run_id, default=[])
