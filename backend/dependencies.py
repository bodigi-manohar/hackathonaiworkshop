"""Shared FastAPI dependencies."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db.session import get_db
from backend.services.run_store import RunStore

DbSession = Annotated[Session, Depends(get_db)]


def get_store() -> RunStore:
    return RunStore(get_settings())


RunStoreDep = Annotated[RunStore, Depends(get_store)]
