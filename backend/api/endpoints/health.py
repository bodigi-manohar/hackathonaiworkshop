from fastapi import APIRouter

from backend.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": get_settings().app_version}
