"""Map Lusha search-and-enrich payloads and responses to CRM fields."""

from __future__ import annotations

from typing import Any

from app.services.apollo_mapper import _contact_name_parts, _contact_org_context


def build_lusha_contact_payload(contact: Any, company: Any | None = None) -> dict[str, Any]:
    """Build one Lusha contact identifier object from a CRM contact."""
    first, last, full = _contact_name_parts(contact)
    domain, org_name = _contact_org_context(contact, company)

    payload: dict[str, Any] = {}
    lusha_id = (getattr(contact, "lusha_id", None) or "").strip() or None
    if lusha_id:
        payload["id"] = lusha_id

    email = (getattr(contact, "email", None) or "").strip() or None
    if email:
        payload["email"] = email

    linkedin = (getattr(contact, "linkedin_url", None) or "").strip() or None
    if linkedin:
        payload["linkedinUrl"] = linkedin

    if first:
        payload["firstName"] = first
    if last:
        payload["lastName"] = last
    if org_name:
        payload["companyName"] = org_name
    if domain:
        payload["companyDomain"] = domain

    return {k: v for k, v in payload.items() if v not in (None, "")}


def has_lusha_match_criteria(payload: dict[str, Any]) -> bool:
    if payload.get("id") or payload.get("email") or payload.get("linkedinUrl"):
        return True
    company_key = payload.get("companyName") or payload.get("companyDomain")
    if payload.get("firstName") and payload.get("lastName") and company_key:
        return True
    return False


def _best_phone(phones: list[Any] | None) -> str | None:
    if not isinstance(phones, list):
        return None
    priority = {"mobile": 0, "direct": 1, "work": 2, "unknown": 3}
    candidates: list[tuple[int, str]] = []
    for item in phones:
        if not isinstance(item, dict):
            continue
        if item.get("doNotCall"):
            continue
        number = item.get("number")
        if not number or not isinstance(number, str):
            continue
        phone_type = str(item.get("type") or "unknown").lower()
        candidates.append((priority.get(phone_type, 3), number.strip()))
    if not candidates:
        return None
    candidates.sort(key=lambda row: row[0])
    return candidates[0][1]


def _best_email(emails: list[Any] | None) -> tuple[str | None, str | None]:
    if not isinstance(emails, list):
        return None, None
    confidence_rank = {"A+": 0, "A": 1, "B": 2, "C": 3}
    candidates: list[tuple[int, int, str, str | None]] = []
    for item in emails:
        if not isinstance(item, dict):
            continue
        email = item.get("email")
        if not email or not isinstance(email, str):
            continue
        email_type = str(item.get("type") or "unknown").lower()
        type_rank = 0 if email_type == "work" else 1
        conf = confidence_rank.get(str(item.get("confidence") or ""), 9)
        candidates.append((type_rank, conf, email.strip(), item.get("confidence")))
    if not candidates:
        return None, None
    candidates.sort(key=lambda row: (row[0], row[1]))
    return candidates[0][2], candidates[0][3]


def map_lusha_contact(result: dict[str, Any]) -> dict[str, Any]:
    """Map a Lusha search-and-enrich result row to Contact fields."""
    if not result or result.get("error"):
        return {}

    phone = _best_phone(result.get("phones"))
    email, email_confidence = _best_email(result.get("emails"))

    job = result.get("jobTitle") if isinstance(result.get("jobTitle"), dict) else {}
    location = result.get("location") if isinstance(result.get("location"), dict) else {}
    social = result.get("socialLinks") if isinstance(result.get("socialLinks"), dict) else {}

    departments = job.get("departments")
    department = departments[0] if isinstance(departments, list) and departments else None

    mapped: dict[str, Any] = {
        "first_name": result.get("firstName"),
        "last_name": result.get("lastName"),
        "full_name": result.get("fullName"),
        "title": job.get("title"),
        "email": email,
        "email_status": email_confidence,
        "phone": phone,
        "linkedin_url": social.get("linkedin"),
        "city": location.get("city"),
        "country": location.get("country"),
        "seniority": job.get("seniority"),
        "department": department,
        "lusha_id": result.get("id"),
        "source": "lusha",
    }
    return {k: v for k, v in mapped.items() if v not in (None, "")}
