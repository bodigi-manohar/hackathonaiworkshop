import csv
import io

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.config import get_app_config
from backend.core.exceptions import NotFoundError
from backend.dependencies import DbSession, RunStoreDep
from backend.schemas.forecast import Forecast
from backend.services.run_service import ensure_bundle

VALID_LEVELS = {"portfolio", "zone", "house"}

router = APIRouter(tags=["forecast"])


def _validate_level(level: str) -> None:
    if level not in VALID_LEVELS:
        raise NotFoundError(f"level must be one of {sorted(VALID_LEVELS)} (got '{level}')")


def _forecast_payload(store: RunStoreDep, level: str, entity_id: str, run_id: str | None, db: DbSession) -> dict:
    _validate_level(level)
    bundle = store.resolve(run_id)
    ensure_bundle(bundle, get_app_config(), db, store)
    if level == "portfolio" and entity_id in ("all", "portfolio"):
        name = "forecast.json"
    else:
        name = f"forecast_{level}_{entity_id}.json"
    return store.load_json(bundle.path, name, bundle.run_id)


@router.get("/forecast", response_model=Forecast)
def get_forecast(
    level: str = "portfolio",
    entity_id: str = "all",
    run_id: str | None = None,
    store: RunStoreDep = None,  # type: ignore[assignment]
    db: DbSession = None,  # type: ignore[assignment]
) -> dict:
    return _forecast_payload(store, level, entity_id, run_id, db)


@router.get("/forecast/csv")
def get_forecast_csv(
    level: str = "portfolio",
    entity_id: str = "all",
    run_id: str | None = None,
    store: RunStoreDep = None,  # type: ignore[assignment]
    db: DbSession = None,  # type: ignore[assignment]
) -> StreamingResponse:
    data = _forecast_payload(store, level, entity_id, run_id, db)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "timestamp_local",
            "level",
            "entity_id",
            "horizon_slot",
            "load_kw_p10",
            "load_kw_p50",
            "load_kw_p90",
            "model_version",
            "run_id",
            "weather_source",
        ]
    )
    for p in data["points"]:
        writer.writerow(
            [
                p["timestamp"],
                data.get("level", level),
                data.get("entity_id", entity_id),
                p["slot"],
                p["p10"],
                p["p50"],
                p["p90"],
                data.get("model_version", ""),
                data.get("run_id", ""),
                data.get("weather_source", ""),
            ]
        )
    buf.seek(0)
    filename = f"forecast_{data.get('run_id', run_id or 'latest')}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
