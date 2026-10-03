from datetime import datetime
from typing import Literal

from pydantic import BaseModel

AlertType = Literal["peak", "ramp", "low_confidence", "model_drift", "heatwave"]
Severity = Literal["info", "warn", "critical"]


class Alert(BaseModel):
    id: str
    type: AlertType
    severity: Severity
    level: str
    entity_id: str
    window_start: datetime
    window_end: datetime
    value: float
    threshold: float
    message: str
