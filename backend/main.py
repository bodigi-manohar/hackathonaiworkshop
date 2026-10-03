"""GridSight FastAPI app factory (uvicorn backend.main:app --reload)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.router import router
from backend.config import get_app_config, get_settings
from backend.core.exception_handlers import register_exception_handlers
from backend.db.session import SessionLocal, init_db
from backend.scheduler import build_scheduler
from backend.services.run_service import RunService
from backend.services.run_store import RunStore

logger = logging.getLogger("gridsight.api")


def create_app() -> FastAPI:
    settings = get_settings()
    config = get_app_config()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db()
        store = RunStore(settings)
        scheduler = None
        try:
            db = SessionLocal()
            try:
                service = RunService(settings, config, store, db)
                service.index_existing_runs()

                def nightly(origin, force: bool = True):
                    db2 = SessionLocal()
                    try:
                        RunService(settings, config, store, db2).trigger(origin, force)
                    finally:
                        db2.close()

                scheduler = build_scheduler(nightly, config)
                if scheduler:
                    scheduler.start()
                    logger.info("nightly scheduler started (hour=%s)", config.scheduler_cron_hour)
            finally:
                db.close()
        except Exception:
            logger.exception("startup preparation failed; continuing in degraded mode")
        yield
        if scheduler is not None:
            scheduler.shutdown(wait=False)

    app = FastAPI(
        title="GridSight API",
        description="Short-term energy demand forecasting backend. Advisory only.",
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(router)
    return app


app = create_app()
