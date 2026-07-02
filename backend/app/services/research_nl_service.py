"""Natural-language planning for Market Research recordsets."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.apollo_filters import normalize_search_payload
from app.services.apollo_service import ApolloError, ApolloService
from app.services.groq_service import GroqError, GroqService, _extract_json
from app.services.research_dataset import create_groq_company_dataset
from app.services.research_service import MAX_RECORDS_CAP, run_and_store

ORG_CRITERIA_KEYS = {
    "q_organization_name",
    "organization_domains",
    "organization_locations",
    "organization_not_locations",
    "organization_num_employees_ranges",
    "organization_industries",
    "organization_ids",
    "organization_latest_funding_stage_cd",
    "currently_using_any_of_technology_uids",
    "currently_using_all_of_technology_uids",
    "currently_not_using_any_of_technology_uids",
    "revenue_range_min",
    "revenue_range_max",
    "organization_founded_year_range_min",
    "organization_founded_year_range_max",
    "q_organization_job_titles",
    "organization_job_locations",
    "organization_num_jobs_range_min",
    "organization_num_jobs_range_max",
    "organization_job_posted_at_range_min",
    "organization_job_posted_at_range_max",
}

PEOPLE_CRITERIA_KEYS = {
    "person_titles",
    "include_similar_titles",
    "q_keywords",
    "person_seniorities",
    "person_locations",
    "organization_locations",
    "organization_domains",
    "q_organization_name",
    "contact_email_status",
    "organization_ids",
    "organization_num_employees_ranges",
    "revenue_range_min",
    "revenue_range_max",
    "currently_using_any_of_technology_uids",
    "currently_using_all_of_technology_uids",
    "currently_not_using_any_of_technology_uids",
    "q_organization_job_titles",
    "organization_job_locations",
    "organization_num_jobs_range_min",
    "organization_num_jobs_range_max",
    "organization_job_posted_at_range_min",
    "organization_job_posted_at_range_max",
}

SORT_BY_VALUES = {"employee_count_desc", "revenue_desc"}

FILTER_LABELS: dict[str, str] = {
    "q_organization_name": "Company name",
    "organization_domains": "Domains",
    "organization_locations": "HQ locations",
    "organization_not_locations": "Exclude HQ locations",
    "organization_num_employees_ranges": "Employee ranges",
    "organization_industries": "Industries / keyword tags",
    "organization_ids": "Organization IDs",
    "organization_latest_funding_stage_cd": "Funding stages",
    "currently_using_any_of_technology_uids": "Uses any technology",
    "currently_using_all_of_technology_uids": "Uses all technologies",
    "currently_not_using_any_of_technology_uids": "Does not use technology",
    "revenue_range_min": "Min revenue",
    "revenue_range_max": "Max revenue",
    "organization_founded_year_range_min": "Founded after",
    "organization_founded_year_range_max": "Founded before",
    "q_organization_job_titles": "Active job titles",
    "organization_job_locations": "Job locations",
    "organization_num_jobs_range_min": "Min active jobs",
    "organization_num_jobs_range_max": "Max active jobs",
    "organization_job_posted_at_range_min": "Jobs posted after",
    "organization_job_posted_at_range_max": "Jobs posted before",
    "person_titles": "Job titles",
    "include_similar_titles": "Include similar titles",
    "q_keywords": "Keywords",
    "person_seniorities": "Seniorities",
    "person_locations": "Person locations",
    "contact_email_status": "Email status",
}

_CLASSIFIER_SYSTEM = (
    "Classify the user message for a CRM assistant.\n"
    '- "crm": questions about existing CRM data (companies/contacts counts, lists, filters).\n'
    '- "research": requests to find NEW companies/people and save as a Market Research recordset.\n'
    "Examples of research: 'top 20 energy companies', 'maak recordset van fintech bedrijven in NL', "
    "'zoek 50 sales directors in Germany'.\n"
    "Examples of crm: 'how many companies do we have', 'contacts without email'.\n"
    'Respond ONLY with minified JSON: {"intent":"crm"|"research","reason":string}'
)

_QUERY_TYPE_SYSTEM = (
    "Classify a Market Research request.\n"
    '- "organizations" for company/organization lists (default)\n'
    '- "people" for contact/person searches (job titles, roles, seniorities)\n'
    'Respond ONLY with minified JSON: {"query_type":"organizations"|"people"}'
)

_ORG_FINDER_SYSTEM = (
    "You help build B2B company recordsets for a CRM. Given a user request, return a list of real "
    "companies that match the criteria.\n\n"
    "Rules:\n"
    "- Prefer well-known, real companies in the requested region/industry.\n"
    "- Include primary_domain when you know it (e.g. vattenfall.com), otherwise null.\n"
    "- Include country, industry, and estimated employee_count when reasonable.\n"
    "- When the user asks for top/largest/biggest N, sort by size and return exactly that many.\n"
    "- Respect an explicit N in the request (default 20, max 200).\n"
    "- name: short recordset title (max 80 chars).\n"
    "- summary: 1-2 sentences in the user's language; mention data is AI-suggested and can be enriched later.\n"
    "- needs_data: false only if the request is impossible.\n\n"
    'Respond ONLY with minified JSON:\n'
    '{"needs_data":boolean,"name":string,"max_records":number,"summary":string,'
    '"companies":[{"name":string,"domain":string|null,"country":string|null,'
    '"industry":string|null,"employee_count":number|null,"city":string|null}],'
    '"reason":string|null}'
)

_PEOPLE_PLANNER_SYSTEM = (
    "You plan Apollo Market Research people searches for a B2B CRM. Translate the request into search filters.\n\n"
    "criteria keys (people):\n"
    "- person_titles, person_seniorities, person_locations\n"
    "- organization_locations, organization_domains, q_organization_name\n"
    "- contact_email_status: verified, likely to engage, etc.\n\n"
    "max_records: how many rows to save (respect explicit N, default 50, max 2000).\n"
    "name: short Dutch or English recordset title (max 80 chars).\n"
    "summary: 1-2 sentences in the user's language.\n"
    "needs_apollo: true unless the request is impossible.\n\n"
    'Respond ONLY with minified JSON:\n'
    '{"needs_apollo":boolean,"name":string,"criteria":object,"max_records":number,'
    '"summary":string,"reason":string|null}'
)


class ResearchNlError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def classify_intent(client: GroqService, prompt: str) -> str:
    content = client.chat(
        [
            {"role": "system", "content": _CLASSIFIER_SYSTEM},
            {"role": "user", "content": prompt.strip()},
        ],
        temperature=0.0,
    )
    parsed = _extract_json(content) or {}
    intent = str(parsed.get("intent") or "crm").strip().lower()
    return "research" if intent == "research" else "crm"


def _classify_query_type(client: GroqService, prompt: str) -> str:
    content = client.chat(
        [
            {"role": "system", "content": _QUERY_TYPE_SYSTEM},
            {"role": "user", "content": prompt.strip()},
        ],
        temperature=0.0,
    )
    parsed = _extract_json(content) or {}
    query_type = str(parsed.get("query_type") or "organizations").strip().lower()
    return query_type if query_type in ("organizations", "people") else "organizations"


def _allowed_keys(query_type: str) -> set[str]:
    return ORG_CRITERIA_KEYS if query_type == "organizations" else PEOPLE_CRITERIA_KEYS


def _sanitize_criteria(criteria: dict[str, Any] | None, *, query_type: str) -> dict[str, Any]:
    allowed = _allowed_keys(query_type)
    clean: dict[str, Any] = {}
    for key, value in (criteria or {}).items():
        if key.startswith("_") or key not in allowed:
            continue
        if value in (None, "", []):
            continue
        clean[key] = value
    return clean


def _filter_preview(criteria: dict[str, Any]) -> list[dict[str, str]]:
    preview: list[dict[str, str]] = []
    for key, value in criteria.items():
        if key.startswith("_"):
            continue
        label = FILTER_LABELS.get(key, key)
        if isinstance(value, list):
            display = ", ".join(str(v) for v in value)
        elif isinstance(value, bool):
            display = "yes" if value else "no"
        else:
            display = str(value)
        preview.append({"key": key, "label": label, "value": display})
    return preview


def _sanitize_companies(raw: Any, *, max_records: int) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    companies: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        domain = item.get("domain")
        domain = str(domain).strip().lower() if domain not in (None, "") else None
        if domain:
            domain = domain.removeprefix("https://").removeprefix("http://").removeprefix("www.").split("/")[0]

        dedup = f"{name.lower()}|{domain or ''}"
        if dedup in seen:
            continue
        seen.add(dedup)

        employee_count = item.get("employee_count")
        try:
            employee_count = int(employee_count) if employee_count not in (None, "") else None
        except (TypeError, ValueError):
            employee_count = None

        companies.append(
            {
                "name": name[:255],
                "domain": domain,
                "country": str(item.get("country")).strip() if item.get("country") else None,
                "industry": str(item.get("industry")).strip() if item.get("industry") else None,
                "employee_count": employee_count,
                "city": str(item.get("city")).strip() if item.get("city") else None,
            }
        )
        if len(companies) >= max_records:
            break
    return companies


def _plan_groq_companies(client: GroqService, prompt: str) -> dict[str, Any]:
    try:
        content = client.chat(
            [
                {"role": "system", "content": _ORG_FINDER_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
    except GroqError as exc:
        raise ResearchNlError(exc.message, status_code=exc.status_code or 502) from exc

    parsed = _extract_json(content) or {}
    if not parsed.get("needs_data", True):
        reason = parsed.get("reason") or parsed.get("summary") or "Could not find matching companies."
        raise ResearchNlError(reason, status_code=400)

    name = str(parsed.get("name") or "Market research").strip()[:255] or "Market research"

    try:
        max_records = int(parsed.get("max_records") or 20)
    except (TypeError, ValueError):
        max_records = 20
    max_records = max(1, min(max_records, MAX_RECORDS_CAP))

    companies = _sanitize_companies(parsed.get("companies"), max_records=max_records)
    if not companies:
        raise ResearchNlError(
            "Could not derive a company list from your request. Try being more specific "
            "(industry, country, or company size).",
            status_code=400,
        )

    summary = (
        str(parsed.get("summary") or "").strip()
        or f"Groq-suggested list of {len(companies)} companies."
    )

    return {
        "name": name,
        "query_type": "organizations",
        "source": "groq",
        "criteria": {},
        "companies": companies,
        "max_records": len(companies),
        "sort_by": None,
        "summary": summary,
        "filter_preview": [],
        "uses_apollo_credits": False,
    }


def _plan_apollo_people(client: GroqService, prompt: str) -> dict[str, Any]:
    try:
        content = client.chat(
            [
                {"role": "system", "content": _PEOPLE_PLANNER_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
    except GroqError as exc:
        raise ResearchNlError(exc.message, status_code=exc.status_code or 502) from exc

    parsed = _extract_json(content) or {}
    if not parsed.get("needs_apollo", True):
        reason = parsed.get("reason") or parsed.get("summary") or "This request cannot be turned into an Apollo search."
        raise ResearchNlError(reason, status_code=400)

    name = str(parsed.get("name") or "Market research").strip()[:255] or "Market research"

    try:
        max_records = int(parsed.get("max_records") or 50)
    except (TypeError, ValueError):
        max_records = 50
    max_records = max(1, min(max_records, MAX_RECORDS_CAP))

    criteria = _sanitize_criteria(parsed.get("criteria"), query_type="people")
    if not criteria:
        raise ResearchNlError(
            "Could not derive Apollo filters from your request. Try being more specific "
            "(job titles, country, or company).",
            status_code=400,
        )

    try:
        normalize_search_payload(criteria)
    except Exception as exc:  # noqa: BLE001
        raise ResearchNlError(f"Invalid search filters: {exc}", status_code=400) from exc

    summary = str(parsed.get("summary") or "").strip() or f"Apollo people search with {max_records} records."

    return {
        "name": name,
        "query_type": "people",
        "source": "apollo",
        "criteria": criteria,
        "companies": [],
        "max_records": max_records,
        "sort_by": None,
        "summary": summary,
        "filter_preview": _filter_preview(criteria),
        "uses_apollo_credits": False,
    }


def plan_research(client: GroqService, prompt: str) -> dict[str, Any]:
    prompt = (prompt or "").strip()
    if not prompt:
        raise ResearchNlError("Describe what you want to research.")

    try:
        query_type = _classify_query_type(client, prompt)
    except GroqError as exc:
        raise ResearchNlError(exc.message, status_code=exc.status_code or 502) from exc

    if query_type == "organizations":
        return _plan_groq_companies(client, prompt)
    return _plan_apollo_people(client, prompt)


def create_research_from_plan(
    db: Session,
    apollo_client: ApolloService | None,
    *,
    name: str,
    query_type: str,
    source: str = "apollo",
    criteria: dict[str, Any] | None = None,
    companies: list[dict[str, Any]] | None = None,
    max_records: int,
    sort_by: str | None,
    created_by: int | None,
    summary: str | None = None,
) -> Any:
    if query_type not in ("organizations", "people"):
        raise ResearchNlError("Unknown search type.", status_code=400)

    if query_type == "organizations" and source == "groq":
        company_rows = companies or []
        if not company_rows:
            raise ResearchNlError("Company list is empty.", status_code=400)
        try:
            max_records = max(1, min(int(max_records), MAX_RECORDS_CAP))
        except (TypeError, ValueError):
            max_records = len(company_rows)
        trimmed = company_rows[:max_records]
        return create_groq_company_dataset(
            db,
            name=name.strip(),
            companies=trimmed,
            created_by=created_by,
            summary=summary,
        )

    if not apollo_client:
        raise ResearchNlError(
            "Apollo is required for people searches. Enable Apollo in Settings.",
            status_code=400,
        )

    clean_criteria = _sanitize_criteria(criteria or {}, query_type=query_type)
    if not clean_criteria:
        raise ResearchNlError("Search filters are empty.", status_code=400)

    try:
        max_records = max(1, min(int(max_records), MAX_RECORDS_CAP))
    except (TypeError, ValueError):
        max_records = 50

    if sort_by not in SORT_BY_VALUES:
        sort_by = None

    try:
        return run_and_store(
            db,
            apollo_client,
            name=name.strip(),
            query_type=query_type,
            criteria=clean_criteria,
            max_records=max_records,
            created_by=created_by,
            sort_by=sort_by,
        )
    except ApolloError as exc:
        raise ResearchNlError(exc.message, status_code=exc.status_code or 502) from exc
