from fastapi import APIRouter

from backend.dependencies import RunStoreDep
from backend.schemas.run import RunListItem

router = APIRouter(tags=["runs"])


@router.get("/runs", response_model=list[RunListItem])
def list_runs(store: RunStoreDep) -> list[RunListItem]:
    return store.list_runs()
