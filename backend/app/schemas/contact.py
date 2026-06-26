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
    source: str
    enrichment_status: str
    apollo_data: dict | None = None
    created_at: datetime
    updated_at: datetime
    company: CompanyBrief | None = None


class ContactList(BaseModel):
    items: list[ContactOut]
    total: int
    page: int
    page_size: int


class BulkDeleteRequest(BaseModel):
    ids: list[int] = Field(default_factory=list)


class BulkDeleteResult(BaseModel):
    deleted: int


class ContactImportResult(BaseModel):
    total_rows: int
    created: int
    updated: int
    skipped_duplicates: int
    skipped_apollo: int
    errors: list[str]
    recognized_columns: list[str]
    extra_columns: list[str]


class FindPeopleResult(BaseModel):
    created: int
    updated: int
    total: int
    contacts: list[ContactOut]
