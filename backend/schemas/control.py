from pydantic import BaseModel


class ControlOut(BaseModel):
    control_enabled: bool
    dry_run: bool = True
