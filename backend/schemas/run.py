from datetime import datetime

from pydantic import BaseModel


class RunListItem(BaseModel):
    run_id: str
    origin_time: str
    created_at: str


class RunTriggerIn(BaseModel):
    origin_time: datetime
    force: bool = False


class RunTriggerOut(BaseModel):
    run_id: str
    origin_time: datetime
    already_existed: bool = False
