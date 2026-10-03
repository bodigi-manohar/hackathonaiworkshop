from pydantic import BaseModel


class PlanSlot(BaseModel):
    slot: int
    price: float
    grid_before_kw: float
    grid_after_kw: float
    battery_charge_kw: float
    battery_discharge_kw: float
    soc_kwh: float


class Plan(BaseModel):
    mode: str = "advisory"
    assumptions: str
    slots: list[PlanSlot]
    cost_before: float
    cost_after: float
    saving: float
    peak_before_kw: float
    peak_after_kw: float
    generator_recommendation: list[dict] = []
    shifted_loads: list[dict] = []
    note: str | None = None
