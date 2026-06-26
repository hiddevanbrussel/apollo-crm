"""Helpers to translate raw Apollo payloads into CRM field dictionaries."""

from __future__ import annotations

from typing import Any

from app.services.industry_normalize import normalize_industry


def _get(d: dict[str, Any] | None, *keys: str) -> Any:
    if not d:
        return None
    for key in keys:
        value = d.get(key)
        if value not in (None, "", []):
            return value
    return None


def map_organization(org: dict[str, Any]) -> dict[str, Any]:
    """Map an Apollo organization object to Company fields."""
    if not org:
        return {}
    location_parts = org.get("raw_address") or ""
    return {
        "name": _get(org, "name") or "Unknown company",
        "domain": _get(org, "primary_domain", "domain", "website_url"),
        "website": _get(org, "website_url", "domain"),
        "linkedin_url": _get(org, "linkedin_url"),
        "industry": normalize_industry(_get(org, "industry")),
        "employee_count": _get(org, "estimated_num_employees", "organization_num_employees"),
        "revenue": _to_int(_get(org, "annual_revenue")),
        "country": _get(org, "country"),
        "city": _get(org, "city"),
        "phone": _get(org, "phone", "sanitized_phone")
        or _get(org.get("primary_phone"), "number")
        if isinstance(org.get("primary_phone"), dict)
        else _get(org, "phone", "sanitized_phone"),
        "description": _get(org, "short_description", "description") or location_parts or None,
        "apollo_id": _get(org, "id"),
        "source": "apollo",
    }


def _split_person_name(full: str) -> tuple[str | None, str | None]:
    parts = full.strip().split(None, 1)
    if not parts:
        return None, None
    return parts[0], parts[1] if len(parts) > 1 else None


def build_email_only_match_payload(
    contact: Any,
    *,
    reveal_personal_emails: bool = True,
    run_waterfall_email: bool = True,
) -> dict[str, Any]:
    """Minimal people/match payload: email only (strongest identifier when present)."""
    email = str(contact.email).strip() if contact.email else None
    payload: dict[str, Any] = {
        "email": email,
        "reveal_personal_emails": reveal_personal_emails,
        "run_waterfall_email": run_waterfall_email,
    }
    apollo_id = (contact.apollo_id or "").strip() if contact.apollo_id else None
    if apollo_id:
        payload["id"] = apollo_id
    return {k: v for k, v in payload.items() if v not in (None, "")}


def build_person_match_payload(
    contact: Any,
    company: Any | None = None,
    *,
    reveal_personal_emails: bool = True,
    run_waterfall_email: bool = True,
) -> dict[str, Any]:
    """Build payload for POST /api/v1/people/match from a CRM contact."""
    from app.services.company_domains import email_domain

    first = (contact.first_name or "").strip() or None
    last = (contact.last_name or "").strip() or None
    full = (contact.full_name or "").strip() or None

    if not first and not last and full:
        first, last = _split_person_name(full)

    if not full and (first or last):
        full = " ".join(p for p in [first, last] if p)

    domain = None
    org_name = None
    if company:
        domain = (company.domain or "").strip() or None
        org_name = (company.name or "").strip() or None
    if not domain and contact.email:
        domain = email_domain(str(contact.email))

    payload: dict[str, Any] = {
        "first_name": first,
        "last_name": last,
        "name": full,
        "email": str(contact.email).strip() if contact.email else None,
        "linkedin_url": (contact.linkedin_url or "").strip() or None,
        "organization_name": org_name,
        "domain": domain,
        "reveal_personal_emails": reveal_personal_emails,
        "run_waterfall_email": run_waterfall_email,
    }
    apollo_id = (contact.apollo_id or "").strip() if contact.apollo_id else None
    if apollo_id:
        payload["id"] = apollo_id

    return {k: v for k, v in payload.items() if v not in (None, "")}


def person_match_is_empty(person: dict[str, Any] | None) -> bool:
    """Return True when Apollo returned no usable person from people/match."""
    if not person:
        return True
    if person.get("id"):
        return False
    return not any(
        person.get(k)
        for k in ("email", "first_name", "last_name", "name", "linkedin_url", "title")
    )


def build_person_match_attempts(
    contact: Any,
    company: Any | None = None,
    *,
    reveal_personal_emails: bool = True,
    run_waterfall_email: bool = True,
) -> list[dict[str, Any]]:
    """Build ordered people/match payloads: email-only first, then full criteria."""
    kwargs = {
        "reveal_personal_emails": reveal_personal_emails,
        "run_waterfall_email": run_waterfall_email,
    }
    attempts: list[dict[str, Any]] = []

    email_only = build_email_only_match_payload(contact, **kwargs)
    if email_only.get("email"):
        attempts.append(email_only)

    full = build_person_match_payload(contact, company, **kwargs)
    if has_person_match_criteria(full) and full not in attempts:
        attempts.append(full)

    return attempts


def has_person_match_criteria(payload: dict[str, Any]) -> bool:
    """Return True if payload has enough fields for Apollo people/match."""
    if payload.get("email") or payload.get("linkedin_url") or payload.get("id"):
        return True
    if payload.get("name"):
        return True
    if payload.get("first_name") and payload.get("last_name"):
        return True
    return False


def map_person(person: dict[str, Any]) -> dict[str, Any]:
    """Map an Apollo person object to Contact fields (without company_id)."""
    if not person:
        return {}
    org = person.get("organization") or {}
    first = _get(person, "first_name")
    last = _get(person, "last_name")
    # Search results (api_search) only return an obfuscated last name.
    last_display = last or _get(person, "last_name_obfuscated")
    full = _get(person, "name") or " ".join(p for p in [first, last_display] if p) or None
    return {
        "first_name": first,
        "last_name": last,
        "full_name": full,
        "title": _get(person, "title"),
        "headline": _get(person, "headline"),
        "email": _normalize_email(_get(person, "email")),
        "email_status": _get(person, "email_status"),
        "phone": _extract_phone(person),
        "linkedin_url": _get(person, "linkedin_url"),
        "photo_url": _get(person, "photo_url"),
        "city": _get(person, "city"),
        "country": _get(person, "country"),
        "seniority": _get(person, "seniority"),
        "department": _first_list(_get(person, "departments"))
        or _first_list(_get(person, "subdepartments")),
        "apollo_id": _get(person, "id"),
        "source": "apollo",
        # Convenience: org info travels alongside so callers can upsert a company.
        "_organization": org,
    }


def _normalize_email(email: Any) -> str | None:
    if not email or not isinstance(email, str):
        return None
    # Apollo sometimes returns locked placeholders.
    if "not_unlocked" in email or "email_not_unlocked" in email:
        return None
    return email


def _extract_phone(person: dict[str, Any]) -> str | None:
    phone = person.get("phone_numbers")
    if isinstance(phone, list) and phone:
        first = phone[0]
        if isinstance(first, dict):
            return first.get("sanitized_number") or first.get("raw_number")
    return _get(person, "sanitized_phone", "phone")


def _first_list(value: Any) -> str | None:
    if isinstance(value, list) and value:
        return str(value[0])
    if isinstance(value, str):
        return value
    return None


def _to_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None
