"""Helpers for companies with multiple domains (primary + extras)."""

from __future__ import annotations

from sqlalchemy import func, select
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


def find_owner(db: Session, domain: str, *, exclude_id: int | None = None) -> Company | None:
    normalized = normalize_domain(domain)
    if not normalized:
        return None

    stmt = select(Company).where(func.lower(Company.domain) == normalized)
    if exclude_id is not None:
        stmt = stmt.where(Company.id != exclude_id)
    owner = db.execute(stmt).scalar_one_or_none()
    if owner:
        return owner

    stmt = select(Company).where(Company.domains.contains([normalized]))
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
        return True, None

    extras = [d for d in (company.domains or []) if d]
    extras.append(domain)
    company.domains = extras
    return True, None
