from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import Company, Contact, SearchHistory, User
from app.schemas.company import CompanyOut
from app.schemas.dashboard import DashboardStats, NameCount, SearchHistoryOut
from app.services.settings_service import (
    get_or_create_groq_settings,
    get_or_create_logokit_settings,
    get_or_create_settings,
    groq_is_configured,
    is_configured,
    logokit_is_configured,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _top_counts(db: Session, column) -> list[NameCount]:
    rows = db.execute(
        select(column, func.count(Company.id))
        .where(column.is_not(None), func.trim(column) != "")
        .group_by(column)
        .order_by(func.count(Company.id).desc())
        .limit(5)
    ).all()
    return [NameCount(name=r[0], count=r[1]) for r in rows]


@router.get("", response_model=DashboardStats)
def get_dashboard(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    total_companies = db.scalar(select(func.count(Company.id))) or 0
    total_contacts = db.scalar(select(func.count(Contact.id))) or 0
    enriched_companies = (
        db.scalar(select(func.count(Company.id)).where(Company.enrichment_status == "enriched")) or 0
    )
    enriched_contacts = (
        db.scalar(select(func.count(Contact.id)).where(Contact.enrichment_status == "enriched")) or 0
    )
    companies_with_domain = (
        db.scalar(
            select(func.count(Company.id)).where(
                Company.domain.is_not(None), func.trim(Company.domain) != ""
            )
        )
        or 0
    )
    contacts_with_email = (
        db.scalar(
            select(func.count(Contact.id)).where(
                Contact.email.is_not(None), func.trim(Contact.email) != ""
            )
        )
        or 0
    )

    recent_companies = (
        db.execute(
            select(Company)
            .where(Company.enrichment_status == "enriched")
            .order_by(Company.updated_at.desc())
            .limit(6)
        )
        .scalars()
        .all()
    )
    recent_searches = (
        db.execute(select(SearchHistory).order_by(SearchHistory.created_at.desc()).limit(5))
        .scalars()
        .all()
    )

    row = get_or_create_settings(db)
    groq_row = get_or_create_groq_settings(db)
    logokit_row = get_or_create_logokit_settings(db)

    return DashboardStats(
        total_companies=total_companies,
        total_contacts=total_contacts,
        enriched_companies=enriched_companies,
        enriched_contacts=enriched_contacts,
        companies_with_domain=companies_with_domain,
        contacts_with_email=contacts_with_email,
        top_industries=_top_counts(db, Company.industry),
        top_countries=_top_counts(db, Company.country),
        recent_enriched_companies=[CompanyOut.model_validate(c) for c in recent_companies],
        recent_searches=[SearchHistoryOut.model_validate(s) for s in recent_searches],
        apollo_enabled=row.enabled,
        apollo_configured=is_configured(row),
        groq_enabled=groq_row.enabled,
        groq_configured=groq_is_configured(groq_row),
        logokit_enabled=logokit_row.enabled,
        logokit_configured=logokit_is_configured(logokit_row),
    )
