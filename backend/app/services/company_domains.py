"""Helpers for companies with multiple domains (primary + extras)."""

from __future__ import annotations

from sqlalchemy import func, or_, select
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


def find_by_domain(db: Session, domain: str) -> list[Company]:
    """All companies that use a domain (primary or extra)."""
    normalized = normalize_domain(domain)
    if not normalized:
        return []
    return (
        db.execute(
            select(Company)
            .where(
                or_(
                    func.lower(Company.domain) == normalized,
                    Company.domains.contains([normalized]),
                )
            )
            .order_by(Company.id)
        )
        .scalars()
        .all()
    )


def find_owner(db: Session, domain: str, *, exclude_id: int | None = None) -> Company | None:
    """First company matching a domain (legacy helper when only one match is needed)."""
    companies = find_by_domain(db, domain)
    for company in companies:
        if exclude_id is not None and company.id == exclude_id:
            continue
        return company
    return None


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

    if not company.domain and set_primary_if_empty:
        company.domain = domain
        return True, None

    extras = [d for d in (company.domains or []) if d]
    extras.append(domain)
    company.domains = extras
    return True, None
