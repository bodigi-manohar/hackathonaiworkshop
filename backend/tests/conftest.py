import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from backend.config import get_settings, reset_caches
from backend.db import session as db_session
from backend.main import create_app


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "gridsight.db"))
    reset_caches()
    settings = get_settings()
    db_session.engine.dispose()
    db_session.engine = create_engine(
        f"sqlite:///{settings.db_path}", future=True, connect_args={"check_same_thread": False}
    )
    db_session.SessionLocal.configure(bind=db_session.engine)
    db_session.init_db()
    return settings


@pytest.fixture()
def client(env):
    app = create_app()
    with TestClient(app) as c:
        yield c
