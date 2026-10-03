"""SQLite session factory (SQLAlchemy 2.0)."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import get_settings
from backend.models import Base

_settings = get_settings()
engine = create_engine(
    f"sqlite:///{_settings.db_path}",
    future=True,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
