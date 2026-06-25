from typing import Any

from pydantic import BaseModel, Field


class PeopleSearchFilters(BaseModel):
    """Filters for Apollo People Search (mixed people/org filters)."""

    person_titles: list[str] | None = None
    person_seniorities: list[str] | None = None
    person_departments: list[str] | None = None
    organization_domains: list[str] | None = None
    q_organization_name: str | None = None
    person_locations: list[str] | None = None
    organization_industries: list[str] | None = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=100)


class OrganizationSearchFilters(BaseModel):
    """Filters for Apollo Organization Search."""

    q_organization_name: str | None = None
    organization_domains: list[str] | None = None
    organization_industries: list[str] | None = None
    organization_locations: list[str] | None = None
    organization_num_employees_ranges: list[str] | None = None
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
    reveal_personal_emails: bool = False
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


class SaveSelection(BaseModel):
    """Save selected Apollo results into the CRM."""

    results: list[dict[str, Any]]
