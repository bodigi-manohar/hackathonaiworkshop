from pydantic import BaseModel


class ByModel(BaseModel):
    model: str
    mae: float
    rmse: float
    nmae: float
    skill: float


class ByHour(BaseModel):
    hour: int
    mae: float


class ByDay(BaseModel):
    weekday: int
    mae: float


class Metrics(BaseModel):
    scope: str
    by_model: list[ByModel]
    by_hour: list[ByHour] = []
    by_weekday: list[ByDay] = []
    coverage_p10_p90: float | None = None
    last_7_days_mae: float | None = None
    drift_ratio: float | None = None
