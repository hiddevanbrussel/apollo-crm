from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class ResearchFilterPreview(BaseModel):
    key: str
    label: str
    value: str


class ResearchPlanOut(BaseModel):
    name: str
    query_type: str
    criteria: dict[str, Any] = {}
    max_records: int = 50
    sort_by: str | None = None
    summary: str
    filter_preview: list[ResearchFilterPreview] = []
    uses_apollo_credits: bool = True


class ResearchPlanRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)


class ResearchCreateFromPlan(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    query_type: str
    criteria: dict[str, Any] = {}
    max_records: int = Field(default=50, ge=1, le=2000)
    sort_by: str | None = None


class AskResponse(BaseModel):
    answer: str
    sql: str | None = None
    columns: list[str] = []
    rows: list[list[Any]] = []
    row_count: int = 0
    used_data: bool = False
    intent: str = "crm"
    research_plan: ResearchPlanOut | None = None


class AiStatus(BaseModel):
    enabled: bool
    configured: bool
    model: str | None = None
    message: str | None = None
