from fastapi import APIRouter

from backend.api.endpoints import alerts, chat, control, entities, forecast, health, metrics, plan, run, runs

router = APIRouter()
router.include_router(health.router)
router.include_router(entities.router)
router.include_router(runs.router)
router.include_router(forecast.router)
router.include_router(alerts.router)
router.include_router(plan.router)
router.include_router(metrics.router)
router.include_router(chat.router)
router.include_router(control.router)
router.include_router(run.router)
