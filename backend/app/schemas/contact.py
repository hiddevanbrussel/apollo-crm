from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CompanyBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    domain: str | None = None


class ContactBase(BaseModel):
    company_id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    title: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    city: str | None = None
    country: str | None = None
    seniority: str | None = None
    department: str | None = None


class ContactCreate(ContactBase):
    apollo_id: str | None = None
    source: str = "manual"


class ContactUpdate(BaseModel):
    company_id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    title: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    city: str | None = None
    country: str | None = None
    seniority: str | None = None
    department: str | None = None


class ContactOut(ContactBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    headline: str | None = None
    email_status: str | None = None
    photo_url: str | None = None
    apollo_id: str | None = None
    prospeo_id: str | None = None
    source: str
    enrichment_status: str
    apollo_data: dict | None = None
    prospeo_data: dict | None = None
    created_at: datetime
    updated_at: datetime
    company: CompanyBrief | None = None


class ContactList(BaseModel):
    items: list[ContactOut]
    total: int
    page: int
    page_size: int


class ContactCompanyOption(BaseModel):
    id: int
    name: str


class ContactFilterOptions(BaseModel):
    countries: list[str]
    cities: list[str]
    seniorities: list[str]
    departments: list[str]
    titles: list[str]
    tiers: list[str]
    companies: list[ContactCompanyOption]


class BulkDeleteRequest(BaseModel):
    ids: list[int] = Field(default_factory=list)


class BulkDeleteResult(BaseModel):
    deleted: int


class BulkEnrichRequest(BaseModel):
    ids: list[int] = Field(default_factory=list)


class BulkEnrichResult(BaseModel):
    enriched: int = 0
    pending: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class BulkEnrichFilteredResult(BulkEnrichResult):
    total_matched: int = 0
    processed: int = 0
    remaining: int = 0


class WaterfallContactItem(BaseModel):
    id: int
    full_name: str | None = None
    email: str | None = None
    company_name: str | None = None
    enrichment_status: str
    waterfall_status: str
    request_id: str | None = None
    requested_at: datetime | None = None
    completed_at: datetime | None = None
    webhook_updated: bool | None = None


class WaterfallStatusOut(BaseModel):
    waterfall_enabled: bool
    webhook_configured: bool
    pending: int
    completed: int
    total_triggered: int
    items: list[WaterfallContactItem]


class ContactEnrichJobFilters(BaseModel):
    search: str | None = None
    company_id: int | None = None
    source: str | None = None
    enrichment_status: str | None = None
    country: str | None = None
    city: str | None = None
    seniority: str | None = None
    department: str | None = None
    title: str | None = None
    titles: list[str] = Field(default_factory=list)
    tier: str | None = None


class ContactEnrichJobStart(BaseModel):
    ids: list[int] | None = None
    filters: ContactEnrichJobFilters | None = None


class ContactEnrichBatchOut(BaseModel):
    index: int
    contact_count: int
    status: str
    enriched: int
    pending: int
    failed: int
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class ContactEnrichJobLogEntry(BaseModel):
    at: float
    message: str


class ContactEnrichJobOut(BaseModel):
    id: str
    status: str
    source: str
    filters: dict | None = None
    total_contacts: int
    batch_size: int
    batch_count: int
    processed_contacts: int
    enriched: int
    pending: int
    failed: int
    skipped: int
    current_batch: int | None = None
    current_contact: str | None = None
    batches: list[ContactEnrichBatchOut]
    log: list[ContactEnrichJobLogEntry]
    error: str | None = None
    started_at: float
    finished_at: float | None = None


class ContactEnrichJobStartResult(BaseModel):
    job: ContactEnrichJobOut
    started: bool


class ContactImportResult(BaseModel):
    total_rows: int
    created: int
    updated: int
    skipped_duplicates: int
    skipped_apollo: int
    domains_added: int
    errors: list[str]
    recognized_columns: list[str]
    extra_columns: list[str]


class FindPeopleResult(BaseModel):
    created: int
    updated: int
    total: int
    contacts: list[ContactOut]
