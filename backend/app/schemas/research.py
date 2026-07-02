from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResearchCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    query_type: str  # 'people' | 'organizations'
    criteria: dict[str, Any] = {}
    max_records: int = Field(default=500, ge=1, le=2000)


class ResearchDatasetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ResearchContactDatasetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ResearchContactAdd(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    company_result_id: int
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    seniority: str | None = None
    linkedin_url: str | None = None


class ResearchContactVaultImport(BaseModel):
    vault_ids: list[int] = Field(..., min_length=1)


class ResearchContactVaultImportResult(BaseModel):
    added: int = 0
    skipped: int = 0


class ResearchCompanyOption(BaseModel):
    id: int
    name: str | None = None
    domain: str | None = None


class ResearchCompanyOptionList(BaseModel):
    items: list[ResearchCompanyOption] = []


class ResearchCompanyAdd(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    domain: str | None = None
    website: str | None = None
    industry: str | None = None
    country: str | None = None
    city: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    employee_count: int | None = None
    revenue: int | None = None


class ResearchDatasetImportResult(BaseModel):
    total_rows: int = 0
    added: int = 0
    skipped: int = 0
    errors: list[str] = []


class ResearchPeopleFromCompanies(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    criteria: dict[str, Any] = {}
    max_records: int = Field(default=500, ge=1, le=2000)


class ResearchSearchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    query_type: str
    criteria: dict
    result_count: int
    total_available: int | None = None
    created_at: datetime
    updated_at: datetime


class ResearchSearchList(BaseModel):
    items: list[ResearchSearchOut]


class ResearchDetail(ResearchSearchOut):
    columns: list[str] = []
    rows: list[dict[str, Any]] = []


class ResearchResultsPage(BaseModel):
    search: ResearchSearchOut
    columns: list[str] = []
    items: list[dict[str, Any]] = []
    total: int = 0
    page: int = 1
    page_size: int = 20


class ResearchEnrichRequest(BaseModel):
    result_ids: list[int] = Field(default_factory=list)
    all_unenriched: bool = False


class ResearchEnrichResult(BaseModel):
    enriched: int = 0
    skipped: int = 0
    failed: int = 0
    total: int = 0
    errors: list[str] = []


class ResearchResultDetail(BaseModel):
    id: int
    search_id: int
    search_name: str
    query_type: str
    editable: bool = False
    enriched: bool = False
    apollo_id: str | None = None
    name: str | None = None
    fields: dict[str, Any] = {}
    raw_data: dict[str, Any] = {}


class ResearchCompanyContactOut(BaseModel):
    source: str  # research | crm
    id: int
    name: str | None = None
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    seniority: str | None = None
    linkedin_url: str | None = None
    apollo_id: str | None = None
    enriched: bool = False
    enrichment_status: str | None = None
    contact_source: str | None = None
    research_search_id: int | None = None
    research_search_name: str | None = None
    company_id: int | None = None
    vault_id: int | None = None
    company_result_id: int | None = None


class ResearchCompanyContactsOut(BaseModel):
    domain: str | None = None
    total: int = 0
    items: list[ResearchCompanyContactOut] = []


class ResearchRelatedCompanyOut(BaseModel):
    source: str  # research | crm
    id: int
    search_id: int | None = None
    search_name: str | None = None
    name: str | None = None
    domain: str | None = None
    apollo_id: str | None = None
    enriched: bool = False
    is_current: bool = False
    record_source: str | None = None


class ResearchRelatedCompaniesOut(BaseModel):
    domain: str | None = None
    total: int = 0
    items: list[ResearchRelatedCompanyOut] = []
