"""Shared company list/export filter helpers."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Company, Contact

EMPLOYEE_BUCKETS: dict[str, tuple[int, int | None]] = {
    "1-10": (1, 10),
    "11-50": (11, 50),
    "51-200": (51, 200),
    "201-500": (201, 500),
    "501-1000": (501, 1000),
    "1001+": (1001, None),
}

SEGMENT_KEYS = (
    "market segment",
    "market_segment",
    "market segments",
    "market_segments",
    "segment",
    "segments",
    "sector",
)


def employee_range(employees: str | None) -> tuple[int | None, int | None]:
    if not employees:
        return None, None
    bucket = EMPLOYEE_BUCKETS.get(employees)
    if not bucket:
        return None, None
    return bucket


def segment_exists_clause(value: str):
    from sqlalchemy import bindparam, text

    return text(
        "EXISTS (SELECT 1 FROM jsonb_each_text(companies.extra_data) e "
        "WHERE lower(e.key) IN :seg_keys AND lower(e.value) = :seg_val)"
    ).bindparams(
        bindparam("seg_keys", value=list(SEGMENT_KEYS), expanding=True),
        bindparam("seg_val", value=value.lower()),
    )


def apply_company_filters(
    stmt,
    *,
    search: str | None = None,
    industry: str | None = None,
    country: str | None = None,
    city: str | None = None,
    market_segment: str | None = None,
    tier: str | None = None,
    min_employees: int | None = None,
    max_employees: int | None = None,
    enrichment_status: str | None = None,
):
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Company.name).like(like),
                func.lower(Company.domain).like(like),
                func.lower(Company.industry).like(like),
                func.lower(Company.country).like(like),
            )
        )
    if industry:
        stmt = stmt.where(func.lower(Company.industry) == industry.lower())
    if country:
        stmt = stmt.where(func.lower(Company.country) == country.lower())
    if city:
        stmt = stmt.where(func.lower(Company.city) == city.lower())
    if min_employees is not None:
        stmt = stmt.where(Company.employee_count >= min_employees)
    if max_employees is not None:
        stmt = stmt.where(Company.employee_count <= max_employees)
    if market_segment:
        stmt = stmt.where(segment_exists_clause(market_segment))
    if tier:
        stmt = stmt.where(func.lower(Company.tier) == tier.lower())
    if enrichment_status:
        stmt = stmt.where(Company.enrichment_status == enrichment_status)
    return stmt


def contact_counts(db: Session, company_ids: list[int]) -> dict[int, int]:
    if not company_ids:
        return {}
    rows = db.execute(
        select(Contact.company_id, func.count(Contact.id))
        .where(Contact.company_id.in_(company_ids))
        .group_by(Contact.company_id)
    ).all()
    return {company_id: count for company_id, count in rows}
