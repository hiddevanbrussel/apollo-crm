"""Map Prospeo enrich-person payloads and responses to CRM fields."""

from __future__ import annotations

from typing import Any

from app.services.apollo_mapper import _contact_name_parts, _contact_org_context
from app.services.industry_normalize import normalize_industry


def build_prospeo_enrich_data(contact: Any, company: Any | None = None) -> dict[str, Any]:
    """Build the Prospeo `data` object from a CRM contact (+ linked company)."""
    first, last, full = _contact_name_parts(contact)
    domain, org_name = _contact_org_context(contact, company)

    data: dict[str, Any] = {}
    prospeo_id = (getattr(contact, "prospeo_id", None) or "").strip() or None
    if prospeo_id:
        data["person_id"] = prospeo_id

    email = (getattr(contact, "email", None) or "").strip() or None
    if email:
        data["email"] = email

    linkedin = (getattr(contact, "linkedin_url", None) or "").strip() or None
    if linkedin:
        data["linkedin_url"] = linkedin

    if full:
        data["full_name"] = full
    else:
        if first:
            data["first_name"] = first
        if last:
            data["last_name"] = last

    if org_name:
        data["company_name"] = org_name
    if domain:
        data["company_website"] = domain
    if company and (company.linkedin_url or "").strip():
        data["company_linkedin_url"] = company.linkedin_url.strip()

    return {k: v for k, v in data.items() if v not in (None, "")}


def _normalize_website(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = str(value).strip().lower()
    if "://" in cleaned:
        cleaned = cleaned.split("://", 1)[1]
    cleaned = cleaned.split("/")[0]
    if cleaned.startswith("www."):
        cleaned = cleaned[4:]
    return cleaned or None


def build_prospeo_search_filters(
    contact: Any,
    company: Any | None = None,
) -> dict[str, Any] | None:
    """Build Prospeo search-person filters (person_name only for now)."""
    first, last, full = _contact_name_parts(contact)
    person_name = full or " ".join(p for p in [first, last] if p)
    if not person_name:
        return None
    return {"person_name": {"include": [person_name]}}


def build_prospeo_search_attempts(contact: Any, company: Any | None = None) -> list[dict[str, Any]]:
    """Search-person filter payloads — currently person_name only."""
    payload = build_prospeo_search_filters(contact, company)
    return [payload] if payload else []


def has_prospeo_search_criteria(contact: Any, company: Any | None = None) -> bool:
    return bool(build_prospeo_search_attempts(contact, company))


def _normalize_name_token(value: str | None) -> str:
    return (value or "").strip().lower()


def score_prospeo_search_candidate(
    contact: Any,
    company: Any | None,
    result: dict[str, Any],
) -> int:
    """Score a Prospeo search-person hit against a CRM contact."""
    person = result.get("person") or {}
    comp = result.get("company") or {}
    first, last, full = _contact_name_parts(contact)
    expected_domain, expected_org = _contact_org_context(contact, company)

    score = 0
    p_first = _normalize_name_token(person.get("first_name"))
    p_last = _normalize_name_token(person.get("last_name"))
    p_name = _normalize_name_token(person.get("full_name"))

    if first and p_first == _normalize_name_token(first):
        score += 25
    if last and p_last == _normalize_name_token(last):
        score += 25
    if full and p_name == _normalize_name_token(full):
        score += 20

    contact_title = _normalize_name_token(getattr(contact, "title", None))
    person_title = _normalize_name_token(person.get("current_job_title"))
    if contact_title and person_title:
        if contact_title == person_title:
            score += 15
        elif contact_title in person_title or person_title in contact_title:
            score += 8

    result_domain = _normalize_website(comp.get("domain") or comp.get("website"))
    if expected_domain:
        expected = _normalize_website(expected_domain)
        if expected and result_domain == expected:
            score += 30
    if expected_org and comp.get("name"):
        if expected_org.lower() in str(comp.get("name")).lower():
            score += 15

    return score


def pick_best_prospeo_search_match(
    contact: Any,
    company: Any | None,
    results: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not results:
        return None

    scored = [(score_prospeo_search_candidate(contact, company, r), r) for r in results]
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best = scored[0]
    if not (best.get("person") or {}).get("person_id"):
        return None

    if len(results) == 1:
        return best

    if best_score < 20:
        return None

    if len(scored) > 1 and best_score - scored[1][0] < 10:
        expected_domain, _ = _contact_org_context(contact, company)
        if expected_domain:
            comp = best.get("company") or {}
            result_domain = _normalize_website(comp.get("domain") or comp.get("website"))
            if result_domain != _normalize_website(expected_domain):
                return None

    return best


def has_prospeo_match_criteria(data: dict[str, Any]) -> bool:
    """Return True when Prospeo minimum matching requirements are met."""
    if data.get("person_id") or data.get("email") or data.get("linkedin_url"):
        return True

    company_key = any(data.get(k) for k in ("company_name", "company_website", "company_linkedin_url"))
    if data.get("full_name") and company_key:
        return True
    if data.get("first_name") and data.get("last_name") and company_key:
        return True
    return False


def _revealed_email(email_obj: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if not isinstance(email_obj, dict):
        return None, None
    if not email_obj.get("revealed"):
        return None, email_obj.get("status")
    raw = email_obj.get("email")
    if not raw or not isinstance(raw, str):
        return None, email_obj.get("status")
    if "*" in raw:
        return None, email_obj.get("status")
    return raw.strip(), email_obj.get("status")


def _revealed_mobile(mobile_obj: dict[str, Any] | None) -> str | None:
    if not isinstance(mobile_obj, dict):
        return None
    if not mobile_obj.get("revealed"):
        return None
    for key in ("mobile_international", "mobile", "mobile_national"):
        value = mobile_obj.get(key)
        if value and isinstance(value, str) and "*" not in value:
            return value.strip()
    return None


def _current_job(person: dict[str, Any]) -> dict[str, Any] | None:
    history = person.get("job_history")
    if isinstance(history, list):
        for job in history:
            if isinstance(job, dict) and job.get("current"):
                return job
    return None


def map_prospeo_organization(org: dict[str, Any] | None) -> dict[str, Any]:
    if not org:
        return {}
    location = org.get("location") if isinstance(org.get("location"), dict) else {}
    phone_hq = org.get("phone_hq") if isinstance(org.get("phone_hq"), dict) else {}
    revenue = org.get("revenue_range") if isinstance(org.get("revenue_range"), dict) else {}
    return {
        "name": org.get("name") or "Unknown company",
        "domain": org.get("domain") or org.get("website"),
        "website": org.get("website") or org.get("domain"),
        "linkedin_url": org.get("linkedin_url"),
        "industry": normalize_industry(org.get("industry")),
        "employee_count": org.get("employee_count"),
        "revenue": revenue.get("min") or revenue.get("max"),
        "country": location.get("country"),
        "city": location.get("city"),
        "phone": phone_hq.get("phone_hq") or phone_hq.get("phone_hq_international"),
        "description": org.get("description") or org.get("description_ai"),
        "apollo_id": None,
        "source": "prospeo",
    }


def map_prospeo_person(response: dict[str, Any]) -> dict[str, Any]:
    """Map a Prospeo enrich-person response to Contact fields (+ `_organization`)."""
    person = response.get("person") or {}
    if not person:
        return {}

    org = response.get("company") or {}
    location = person.get("location") if isinstance(person.get("location"), dict) else {}
    job = _current_job(person) or {}
    email, email_status = _revealed_email(person.get("email"))
    phone = _revealed_mobile(person.get("mobile"))

    departments = job.get("departments")
    department = departments[0] if isinstance(departments, list) and departments else None

    return {
        "first_name": person.get("first_name"),
        "last_name": person.get("last_name"),
        "full_name": person.get("full_name"),
        "title": person.get("current_job_title") or job.get("title"),
        "headline": person.get("headline"),
        "email": email,
        "email_status": email_status,
        "phone": phone,
        "linkedin_url": person.get("linkedin_url"),
        "photo_url": None,
        "city": location.get("city"),
        "country": location.get("country"),
        "seniority": job.get("seniority"),
        "department": department,
        "prospeo_id": person.get("person_id"),
        "source": "prospeo",
        "_organization": org if org else None,
    }
