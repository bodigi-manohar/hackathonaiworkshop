from pydantic import BaseModel


class Entities(BaseModel):
    portfolio: list[str]
    zone: list[str] = []
    house: list[str] = []
