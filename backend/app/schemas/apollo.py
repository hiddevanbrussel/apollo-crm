from typing import Any

from pydantic import BaseModel, Field


class RangeFilter(BaseModel):
    min: int | str | None = None
    max: int | str | None = None


class PeopleSearchFilters(BaseModel):
    """Filters for Apollo People API Search (/mixed_people/api_search)."""

    person_titles: list[str] | None = None
    include_similar_titles: bool | None = None
    q_keywords: str | None = None
    person_locations: list[str] | None = None
    person_seniorities: list[str] | None = None
    person_departments: list[str] | None = None
    organization_locations: list[str] | None = None
    organization_domains: list[str] | None = None
    q_organization_domains_list: list[str] | None = None
    q_organization_name: str | None = None
    contact_email_status: list[str] | None = None
    organization_ids: list[str] | None = None
    organization_num_employees_ranges: list[str] | str | None = None
    revenue_range: RangeFilter | None = None
    revenue_range_min: int | None = None
    revenue_range_max: int | None = None
    currently_using_all_of_technology_uids: list[str] | None = None
    currently_using_any_of_technology_uids: list[str] | None = None
    currently_not_using_any_of_technology_uids: list[str] | None = None
    q_organization_job_titles: list[str] | None = None
    organization_job_locations: list[str] | None = None
    organization_num_jobs_range: RangeFilter | None = None
    organization_num_jobs_range_min: int | None = None
    organization_num_jobs_range_max: int | None = None
    organization_job_posted_at_range: RangeFilter | None = None
    organization_job_posted_at_range_min: str | None = None
    organization_job_posted_at_range_max: str | None = None
    organization_industries: list[str] | None = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=100)


class OrganizationSearchFilters(BaseModel):
    """Filters for Apollo Organization Search (/mixed_companies/search)."""

    q_organization_name: str | None = None
    organization_domains: list[str] | None = None
    q_organization_domains_list: list[str] | None = None
    organization_locations: list[str] | None = None
    organization_not_locations: list[str] | None = None
    organization_num_employees_ranges: list[str] | str | None = None
    revenue_range: RangeFilter | None = None
    revenue_range_min: int | None = None
    revenue_range_max: int | None = None
    currently_using_all_of_technology_uids: list[str] | None = None
    currently_using_any_of_technology_uids: list[str] | None = None
    currently_not_using_any_of_technology_uids: list[str] | None = None
    q_organization_keyword_tags: list[str] | None = None
    organization_industries: list[str] | None = None
    organization_ids: list[str] | None = None
    organization_latest_funding_stage_cd: list[str] | None = None
    organization_founded_year_range: RangeFilter | None = None
    organization_founded_year_range_min: int | None = None
    organization_founded_year_range_max: int | None = None
    q_organization_job_titles: list[str] | None = None
    organization_job_locations: list[str] | None = None
    organization_num_jobs_range: RangeFilter | None = None
    organization_num_jobs_range_min: int | None = None
    organization_num_jobs_range_max: int | None = None
    organization_job_posted_at_range: RangeFilter | None = None
    organization_job_posted_at_range_min: str | None = None
    organization_job_posted_at_range_max: str | None = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=100)


class PersonEnrichInput(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    name: str | None = None
    email: str | None = None
    organization_name: str | None = None
    domain: str | None = None
    linkedin_url: str | None = None
    reveal_personal_emails: bool = True
    run_waterfall_email: bool = False
    webhook_url: str | None = None
    reveal_phone_number: bool = False


class BulkPersonEnrichInput(BaseModel):
    details: list[PersonEnrichInput]
    reveal_personal_emails: bool = False
    reveal_phone_number: bool = False


class OrganizationEnrichInput(BaseModel):
    domain: str | None = None
    organization_name: str | None = None


class ApolloResultItem(BaseModel):
    apollo_id: str | None = None
    raw: dict[str, Any]


class ApolloSearchResponse(BaseModel):
    results: list[dict[str, Any]]
    pagination: dict[str, Any] | None = None
    total: int = 0


class ApolloStatus(BaseModel):
    enabled: bool
    configured: bool
    base_url: str
    reachable: bool | None = None
    message: str | None = None


class ApolloCreditsOut(BaseModel):
    available: bool
    num_credits_remaining: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    message: str | None = None


class SaveSelection(BaseModel):
    """Save selected Apollo results into the CRM."""

    results: list[dict[str, Any]]
