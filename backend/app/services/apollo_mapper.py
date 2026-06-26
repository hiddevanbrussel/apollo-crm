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
    run_waterfall_email: bool = False,
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


def build_name_org_match_payload(
    contact: Any,
    company: Any | None = None,
    *,
    reveal_personal_emails: bool = True,
    run_waterfall_email: bool = False,
) -> dict[str, Any]:
    """Minimal people/match payload: full name + employer name (Apollo-recommended combo)."""
    first, last, full = _contact_name_parts(contact)
    _, org_name = _contact_org_context(contact, company)
    person_name = full or " ".join(p for p in [first, last] if p) or None
    if not person_name or not org_name:
        return {}

    payload: dict[str, Any] = {
        "name": person_name,
        "organization_name": org_name,
        "reveal_personal_emails": reveal_personal_emails,
        "run_waterfall_email": run_waterfall_email,
    }
    apollo_id = (contact.apollo_id or "").strip() if contact.apollo_id else None
    if apollo_id:
        payload["id"] = apollo_id
    return payload


def build_person_match_payload(
    contact: Any,
    company: Any | None = None,
    *,
    reveal_personal_emails: bool = True,
    run_waterfall_email: bool = False,
) -> dict[str, Any]:
    """Build payload for POST /api/v1/people/match from a CRM contact."""
    first, last, full = _contact_name_parts(contact)
    domain, org_name = _contact_org_context(contact, company)

    payload: dict[str, Any] = {
        "name": full,
        "email": str(contact.email).strip() if contact.email else None,
        "linkedin_url": (contact.linkedin_url or "").strip() or None,
        "organization_name": org_name,
        "domain": domain,
        "reveal_personal_emails": reveal_personal_emails,
        "run_waterfall_email": run_waterfall_email,
    }
    # Apollo: use name OR first_name+last_name, not both.
    if not full:
        payload["first_name"] = first
        payload["last_name"] = last
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
    run_waterfall_email: bool = False,
) -> list[dict[str, Any]]:
    """Build ordered people/match payloads: email-only, name+org, then full criteria."""
    kwargs = {
        "reveal_personal_emails": reveal_personal_emails,
        "run_waterfall_email": run_waterfall_email,
    }
    attempts: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(payload: dict[str, Any]) -> None:
        if not has_person_match_criteria(payload):
            return
        key = str(sorted(payload.items()))
        if key in seen:
            return
        seen.add(key)
        attempts.append(payload)

    add(build_email_only_match_payload(contact, **kwargs))
    add(build_name_org_match_payload(contact, company, **kwargs))
    add(build_person_match_payload(contact, company, **kwargs))

    return attempts


def _contact_name_parts(contact: Any) -> tuple[str | None, str | None, str | None]:
    """Return (first_name, last_name, full_name) for a CRM contact."""
    first = (contact.first_name or "").strip() or None
    last = (contact.last_name or "").strip() or None
    full = (contact.full_name or "").strip() or None
    if not first and not last and full:
        first, last = _split_person_name(full)
    if not full and (first or last):
        full = " ".join(p for p in [first, last] if p)
    return first, last, full


def _contact_org_context(contact: Any, company: Any | None) -> tuple[str | None, str | None]:
    """Return (employer domain, employer name) for match/search filters."""
    from app.services.company_domains import email_domain

    domain = None
    org_name = None
    if company:
        domain = (company.domain or "").strip() or None
        org_name = (company.name or "").strip() or None
    if not domain and contact.email:
        domain = email_domain(str(contact.email))
    return domain, org_name


def build_person_search_attempts(
    contact: Any,
    company: Any | None = None,
    *,
    per_page: int = 10,
) -> list[dict[str, Any]]:
    """Build ordered People API Search payloads (mixed_people/api_search).

    Used when people/match returns no person — search by name/company, then enrich by id.
    """
    first, last, full = _contact_name_parts(contact)
    if not full and not (first and last):
        return []

    q_keywords = full or " ".join(p for p in [first, last] if p)
    domain, org_name = _contact_org_context(contact, company)
    title = (contact.title or "").strip() or None
    linkedin = (contact.linkedin_url or "").strip() or None

    base: dict[str, Any] = {"q_keywords": q_keywords, "page": 1, "per_page": per_page}
    attempts: list[dict[str, Any]] = []

    if linkedin:
        attempts.append({**base, "q_keywords": linkedin})

    if domain and title:
        attempts.append({**base, "q_organization_domains_list": [domain], "person_titles": [title]})
    if domain:
        attempts.append({**base, "q_organization_domains_list": [domain]})
    if org_name:
        attempts.append({**base, "q_keywords": f"{q_keywords} {org_name}".strip()})

    if not attempts:
        attempts.append(dict(base))

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for attempt in attempts:
        key = str(sorted(attempt.items()))
        if key in seen:
            continue
        seen.add(key)
        unique.append(attempt)
    return unique


def _normalize_name_token(value: str | None) -> str:
    return (value or "").strip().lower()


def _org_domain(person: dict[str, Any]) -> str | None:
    org = person.get("organization") or {}
    domain = _get(org, "primary_domain", "domain")
    if isinstance(domain, str):
        return domain.strip().lower() or None
    return None


def score_person_search_candidate(
    contact: Any,
    company: Any | None,
    person: dict[str, Any],
) -> int:
    """Score how well an Apollo search hit matches a CRM contact (higher = better)."""
    first, last, full = _contact_name_parts(contact)
    expected_domain, _ = _contact_org_context(contact, company)

    score = 0
    p_first = _normalize_name_token(person.get("first_name"))
    p_last = _normalize_name_token(person.get("last_name"))
    p_last_obf = _normalize_name_token(person.get("last_name_obfuscated"))
    p_name = _normalize_name_token(person.get("name"))

    if first and p_first == _normalize_name_token(first):
        score += 25
    if last:
        last_norm = _normalize_name_token(last)
        if p_last == last_norm:
            score += 25
        elif p_last_obf and last_norm.startswith(p_last_obf.rstrip("*")):
            score += 20
    if full and p_name and _normalize_name_token(full) == p_name:
        score += 15

    contact_title = _normalize_name_token(getattr(contact, "title", None))
    person_title = _normalize_name_token(person.get("title"))
    if contact_title and person_title:
        if contact_title == person_title:
            score += 15
        elif contact_title in person_title or person_title in contact_title:
            score += 8

    if expected_domain:
        person_domain = _org_domain(person)
        if person_domain and person_domain == expected_domain.lower():
            score += 25

    contact_li = (getattr(contact, "linkedin_url", None) or "").strip().lower()
    person_li = (person.get("linkedin_url") or "").strip().lower()
    if contact_li and person_li and contact_li.rstrip("/") == person_li.rstrip("/"):
        score += 40

    return score


def pick_best_person_search_match(
    contact: Any,
    company: Any | None,
    people: list[dict[str, Any]],
    *,
    min_score: int = 45,
) -> dict[str, Any] | None:
    """Pick the best Apollo search result for a CRM contact, or None if uncertain."""
    if not people:
        return None

    scored = [(score_person_search_candidate(contact, company, p), p) for p in people]
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best = scored[0]
    if best_score < min_score or not best.get("id"):
        return None

    if len(scored) > 1:
        second_score = scored[1][0]
        _, expected_domain = _contact_org_context(contact, company)
        if best_score - second_score < 10 and expected_domain:
            if _org_domain(best) != expected_domain.lower():
                return None

    return best


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
