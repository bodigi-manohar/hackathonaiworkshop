from pydantic import BaseModel, Field


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    run_id: str | None = None


class ChatOut(BaseModel):
    answer: str
    used_llm: bool
    run_id: str
