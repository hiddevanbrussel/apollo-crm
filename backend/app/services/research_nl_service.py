"""Natural-language planning for Market Research recordsets (Apollo searches)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.apollo_filters import normalize_search_payload
from app.services.apollo_service import ApolloError, ApolloService
from app.services.groq_service import GroqError, GroqService, _extract_json
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
    "q_organization_name": "Employer name",
}

_CLASSIFIER_SYSTEM = (
    "Classify the user message for a CRM assistant.\n"
    '- "crm": questions about existing CRM data (companies/contacts counts, lists, filters).\n'
    '- "research": requests to find NEW companies/people via Apollo and save as a Market Research recordset.\n'
    "Examples of research: 'top 20 energy companies', 'maak recordset van fintech bedrijven in NL', "
    "'zoek 50 sales directors in Germany'.\n"
    "Examples of crm: 'how many companies do we have', 'contacts without email'.\n"
    'Respond ONLY with minified JSON: {"intent":"crm"|"research","reason":string}'
)

_PLANNER_SYSTEM = (
    "You plan Apollo Market Research recordsets for a B2B CRM. Translate the request into search filters.\n\n"
    "query_type:\n"
    '- "organizations" for company lists (default for industry/sector/company size requests)\n'
    '- "people" for contact/person searches\n\n'
    "criteria keys (organizations):\n"
    "- organization_industries: list of keyword tags (e.g. energy, utilities, software, fintech)\n"
    "- organization_locations: HQ locations (countries/regions, e.g. Netherlands, Germany)\n"
    "- organization_not_locations: exclude locations\n"
    "- organization_num_employees_ranges: list like [\"1001,5000\", \"5001,10000\"] for size bands\n"
    "- q_organization_name: partial company name\n"
    "- organization_domains: domain list\n"
    "- revenue_range_min / revenue_range_max: integers USD\n"
    "- organization_founded_year_range_min / max: year integers\n"
    "- currently_using_any_of_technology_uids: e.g. salesforce, hubspot\n\n"
    "criteria keys (people):\n"
    "- person_titles, person_seniorities, person_locations\n"
    "- organization_locations, organization_domains, q_organization_name\n"
    "- contact_email_status: verified, likely to engage, etc.\n\n"
    "sort_by (organizations only, when user asks for largest/biggest/top N by size):\n"
    '- "employee_count_desc" (default for grootste/grootste bedrijven/largest companies)\n'
    '- "revenue_desc" when revenue/omzet is explicit\n'
    "- null when order does not matter\n\n"
    "max_records: how many rows to save (respect explicit N in the request, default 50, max 2000).\n"
    "name: short Dutch or English recordset title (max 80 chars).\n"
    "summary: 1-2 sentences in the user's language explaining what will be searched.\n"
    "needs_apollo: true unless the request is impossible.\n\n"
    'Respond ONLY with minified JSON:\n'
    '{"needs_apollo":boolean,"name":string,"query_type":"organizations"|"people",'
    '"criteria":object,"max_records":number,"sort_by":"employee_count_desc"|"revenue_desc"|null,'
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


def plan_research(client: GroqService, prompt: str) -> dict[str, Any]:
    prompt = (prompt or "").strip()
    if not prompt:
        raise ResearchNlError("Describe what you want to research.")

    try:
        content = client.chat(
            [
                {"role": "system", "content": _PLANNER_SYSTEM},
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

    query_type = str(parsed.get("query_type") or "organizations").strip().lower()
    if query_type not in ("organizations", "people"):
        query_type = "organizations"

    name = str(parsed.get("name") or "Market research").strip()[:255]
    if not name:
        name = "Market research"

    try:
        max_records = int(parsed.get("max_records") or 50)
    except (TypeError, ValueError):
        max_records = 50
    max_records = max(1, min(max_records, MAX_RECORDS_CAP))

    sort_by = parsed.get("sort_by")
    if sort_by not in SORT_BY_VALUES:
        sort_by = None
    if query_type != "organizations":
        sort_by = None

    criteria = _sanitize_criteria(parsed.get("criteria"), query_type=query_type)
    if not criteria:
        raise ResearchNlError(
            "Could not derive Apollo filters from your request. Try being more specific "
            "(industry, country, company size, or job titles).",
            status_code=400,
        )

    try:
        normalize_search_payload(criteria)
    except Exception as exc:  # noqa: BLE001
        raise ResearchNlError(f"Invalid search filters: {exc}", status_code=400) from exc

    summary = str(parsed.get("summary") or "").strip() or f"Apollo {query_type} search with {max_records} records."

    return {
        "name": name,
        "query_type": query_type,
        "criteria": criteria,
        "max_records": max_records,
        "sort_by": sort_by,
        "summary": summary,
        "filter_preview": _filter_preview(criteria),
        "uses_apollo_credits": query_type == "organizations",
    }


def create_research_from_plan(
    db: Session,
    apollo_client: ApolloService,
    *,
    name: str,
    query_type: str,
    criteria: dict[str, Any],
    max_records: int,
    sort_by: str | None,
    created_by: int | None,
) -> Any:
    if query_type not in ("organizations", "people"):
        raise ResearchNlError("Unknown search type.", status_code=400)

    clean_criteria = _sanitize_criteria(criteria, query_type=query_type)
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
