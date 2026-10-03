from fastapi import APIRouter

from backend.dependencies import RunStoreDep
from backend.schemas.entities import Entities

router = APIRouter(tags=["entities"])


@router.get("/entities", response_model=Entities)
def get_entities(store: RunStoreDep) -> Entities:
    return Entities(**store.entities())
