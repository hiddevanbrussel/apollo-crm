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
