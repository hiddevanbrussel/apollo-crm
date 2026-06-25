from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class AskResponse(BaseModel):
    answer: str
    sql: str | None = None
    columns: list[str] = []
    rows: list[list[Any]] = []
    row_count: int = 0
    used_data: bool = False


class AiStatus(BaseModel):
    enabled: bool
    configured: bool
    model: str | None = None
    message: str | None = None
