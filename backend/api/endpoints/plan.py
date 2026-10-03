from fastapi import APIRouter

from backend.config import get_app_config
from backend.dependencies import DbSession, RunStoreDep
from backend.schemas.plan import Plan
from backend.services.run_service import ensure_bundle

router = APIRouter(tags=["plan"])


@router.get("/plan", response_model=Plan)
def get_plan(
    run_id: str | None = None,
    store: RunStoreDep = None,  # type: ignore[assignment]
    db: DbSession = None,  # type: ignore[assignment]
) -> dict:
    bundle = store.resolve(run_id)
    ensure_bundle(bundle, get_app_config(), db, store)
    return store.load_json(bundle.path, "plan.json", bundle.run_id)
