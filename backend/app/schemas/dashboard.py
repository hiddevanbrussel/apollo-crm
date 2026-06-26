from datetime import datetime

from pydantic import BaseModel

from app.schemas.company import CompanyOut


class SearchHistoryOut(BaseModel):
    id: int
    query_type: str
    query_payload: dict
    result_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class NameCount(BaseModel):
    name: str
    count: int


class DashboardStats(BaseModel):
    total_companies: int
    total_contacts: int
    enriched_companies: int
    enriched_contacts: int
    enriched_contacts_with_title: int
    companies_with_domain: int
    contacts_with_email: int
    top_industries: list[NameCount]
    top_countries: list[NameCount]
    recent_enriched_companies: list[CompanyOut]
    recent_searches: list[SearchHistoryOut]
    apollo_enabled: bool
    apollo_configured: bool
    groq_enabled: bool
    groq_configured: bool
    logokit_enabled: bool
    logokit_configured: bool
