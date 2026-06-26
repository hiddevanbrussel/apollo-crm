from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CompanyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    domain: str | None = None
    website: str | None = None
    linkedin_url: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    revenue: int | None = None
    country: str | None = None
    city: str | None = None
    phone: str | None = None
    description: str | None = None


class CompanyCreate(CompanyBase):
    apollo_id: str | None = None
    source: str = "manual"


class CompanyUpdate(BaseModel):
    name: str | None = None
    domain: str | None = None
    website: str | None = None
    linkedin_url: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    revenue: int | None = None
    country: str | None = None
    city: str | None = None
    phone: str | None = None
    description: str | None = None


class CompanyOut(CompanyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    apollo_id: str | None = None
    source: str
    enrichment_status: str
    extra_data: dict | None = None
    created_at: datetime
    updated_at: datetime
    contact_count: int | None = None


class CompanyList(BaseModel):
    items: list[CompanyOut]
    total: int
    page: int
    page_size: int


class ImportResult(BaseModel):
    total_rows: int
    created: int
    updated: int
    skipped_duplicates: int
    enriched: int
    errors: list[str]
    created_names: list[str]
    recognized_columns: list[str]
    extra_columns: list[str]


class DomainLookupResult(BaseModel):
    found: bool
    domain: str | None = None
    confidence: str | None = None
    reason: str | None = None
    applied: bool = False
    message: str | None = None
    company: CompanyOut | None = None


class BulkDomainItem(BaseModel):
    company_id: int
    name: str
    found: bool
    domain: str | None = None
    applied: bool = False
    reason: str | None = None


class BulkDomainResult(BaseModel):
    processed: int
    found: int
    applied: int
    items: list[BulkDomainItem]


class CompanyFilterOptions(BaseModel):
    industries: list[str]
    countries: list[str]
    cities: list[str]
    segments: list[str]


class BulkEnrichRequest(BaseModel):
    company_ids: list[int] = Field(..., min_length=1)


class BulkEnrichItem(BaseModel):
    company_id: int
    name: str
    status: str  # enriched | failed | skipped
    reason: str | None = None


class BulkEnrichResult(BaseModel):
    requested: int
    enriched: int
    failed: int
    skipped: int
    items: list[BulkEnrichItem]


class BulkDeleteRequest(BaseModel):
    ids: list[int] = Field(default_factory=list)


class BulkDeleteResult(BaseModel):
    deleted: int


class DomainJobOut(BaseModel):
    id: str
    status: str
    total: int
    processed: int
    found: int
    applied: int
    current: str | None = None
    error: str | None = None
    started_at: float | None = None
    finished_at: float | None = None
