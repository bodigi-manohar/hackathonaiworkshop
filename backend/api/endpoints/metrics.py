from fastapi import APIRouter

from backend.dependencies import RunStoreDep
from backend.schemas.metrics import Metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_model=Metrics)
def get_metrics(
    run_id: str | None = None,
    store: RunStoreDep = None,  # type: ignore[assignment]
) -> dict:
    bundle = store.resolve(run_id)
    return store.load_json(bundle.path, "metrics.json", bundle.run_id)
