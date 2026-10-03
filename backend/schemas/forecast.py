from datetime import datetime

from pydantic import BaseModel, Field


class ForecastPoint(BaseModel):
    slot: int
    timestamp: datetime
    p10: float
    p50: float
    p90: float


class HistoryPoint(BaseModel):
    timestamp: datetime
    actual: float


class Forecast(BaseModel):
    run_id: str
    origin_time: datetime
    level: str
    entity_id: str
    unit: str = "kW"
    slot_minutes: int = 30
    model_version: str
    weather_source: str
    points: list[ForecastPoint] = Field(min_length=48, max_length=48)
    history: list[HistoryPoint] = []
