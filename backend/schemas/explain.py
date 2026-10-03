from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PeakInfo(BaseModel):
    time: datetime
    p50_kw: float
    p90_kw: float


class AccuracyInfo(BaseModel):
    mae_kw: float
    skill_vs_naive: float


class PlanSummary(BaseModel):
    saving: float
    peak_reduction_kw: float


class ExplainContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    run_id: str
    peak: PeakInfo
    total_kwh_next_24h: float
    drivers: list[str] = []
    band_width_note: str | None = None
    accuracy_last_7_days: AccuracyInfo
    alerts_summary: list[str] = []
    plan_summary: PlanSummary
    weather: dict = {}
