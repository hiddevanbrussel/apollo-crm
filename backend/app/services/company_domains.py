"""Helpers for companies with multiple domains (primary + extras)."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Company
from app.services.import_service import normalize_domain


def email_domain(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return normalize_domain(email.rsplit("@", 1)[-1])


def list_domains(company: Company) -> list[str]:
    """All domains for a company: primary first, then extras, deduplicated."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in [company.domain, *(company.domains or [])]:
        domain = normalize_domain(raw) if raw else None
        if domain and domain not in seen:
            seen.add(domain)
            result.append(domain)
    return result


def _company_owns_domain(company: Company, normalized: str) -> bool:
    return normalized in list_domains(company)


def find_owner(db: Session, domain: str, *, exclude_id: int | None = None) -> Company | None:
    normalized = normalize_domain(domain)
    if not normalized:
        return None

    # Include unflushed changes in this session (e.g. during bulk contact import).
    for obj in db:
        if not isinstance(obj, Company):
            continue
        if exclude_id is not None and obj.id == exclude_id:
            continue
        if _company_owns_domain(obj, normalized):
            return obj

    stmt = select(Company).where(
        or_(
            func.lower(Company.domain) == normalized,
            Company.domains.contains([normalized]),
        )
    )
    if exclude_id is not None:
        stmt = stmt.where(Company.id != exclude_id)
    return db.execute(stmt).scalar_one_or_none()


def add_domain(
    db: Session,
    company: Company,
    raw_domain: str | None,
    *,
    set_primary_if_empty: bool = True,
) -> tuple[bool, str | None]:
    """Attach a domain to a company. Returns (added, error_message)."""
    domain = normalize_domain(raw_domain)
    if not domain:
        return False, None

    if domain in list_domains(company):
        return False, None

    owner = find_owner(db, domain, exclude_id=company.id)
    if owner:
        return False, f"Domain '{domain}' is already used by '{owner.name}'."

    if not company.domain and set_primary_if_empty:
        company.domain = domain
        try:
            with db.begin_nested():
                db.flush()
        except IntegrityError:
            company.domain = None
            owner = find_owner(db, domain, exclude_id=company.id)
            name = owner.name if owner else "another company"
            return False, f"Domain '{domain}' is already used by '{name}'."
        return True, None

    extras = [d for d in (company.domains or []) if d]
    extras.append(domain)
    company.domains = extras
    return True, None
