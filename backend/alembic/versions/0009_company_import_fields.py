"""add company import fields (tier, revenue_2025, sector_confidence, partner_status)

Revision ID: 0009_company_import_fields
Revises: 0008_company_domains
Create Date: 2026-06-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_company_import_fields"
down_revision: Union[str, None] = "0008_company_domains"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _extra_val_sql(*keys: str) -> str:
    parts = [f"NULLIF(trim(extra_data->>'{k}'), '')" for k in keys]
    return f"COALESCE({', '.join(parts)})"


def upgrade() -> None:
    op.add_column("companies", sa.Column("tier", sa.String(length=50), nullable=True))
    op.add_column("companies", sa.Column("revenue_2025", sa.BigInteger(), nullable=True))
    op.add_column("companies", sa.Column("sector_confidence", sa.String(length=50), nullable=True))
    op.add_column("companies", sa.Column("partner_status", sa.String(length=120), nullable=True))
    op.create_index("ix_companies_tier", "companies", ["tier"])
    op.create_index("ix_companies_partner_status", "companies", ["partner_status"])

    tier_src = _extra_val_sql("Tier", "tier")
    rev_src = _extra_val_sql("Revenue 2025", "revenue_2025", "Revenue_2025")
    conf_src = _extra_val_sql(
        "Sector_confidence",
        "Sector Confidence",
        "sector_confidence",
        "Sector confidence",
    )
    partner_src = _extra_val_sql("Partner_status", "Partner Status", "partner_status")

    op.execute(f"UPDATE companies SET tier = {tier_src} WHERE tier IS NULL AND {tier_src} IS NOT NULL")
    op.execute(
        f"""
        UPDATE companies SET revenue_2025 = NULLIF(
            regexp_replace({rev_src}, '[^0-9]', '', 'g'), ''
        )::bigint
        WHERE revenue_2025 IS NULL AND {rev_src} IS NOT NULL
        """
    )
    op.execute(
        f"UPDATE companies SET sector_confidence = {conf_src} "
        f"WHERE sector_confidence IS NULL AND {conf_src} IS NOT NULL"
    )
    op.execute(
        f"UPDATE companies SET partner_status = {partner_src} "
        f"WHERE partner_status IS NULL AND {partner_src} IS NOT NULL"
    )

    op.execute(
        """
        UPDATE companies SET tier = CASE lower(trim(tier))
            WHEN 'tier 1' THEN 'Tier 1'
            WHEN 'tier1' THEN 'Tier 1'
            WHEN 'tier 2' THEN 'Tier 2'
            WHEN 'tier2' THEN 'Tier 2'
            ELSE tier
        END
        WHERE tier IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE companies SET sector_confidence = CASE lower(trim(sector_confidence))
            WHEN 'assumed' THEN 'Assumed'
            WHEN 'high' THEN 'High'
            WHEN 'verify' THEN 'Verify'
            WHEN 'verifiy' THEN 'Verify'
            WHEN 'verified' THEN 'Verify'
            ELSE sector_confidence
        END
        WHERE sector_confidence IS NOT NULL
        """
    )

    from sqlalchemy.orm import Session

    from app.models.company import Company
    from app.services.country_normalize import normalize_country

    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        for company in session.query(Company).filter(Company.country.is_not(None)):
            normalized = normalize_country(company.country)
            if normalized and normalized != company.country:
                company.country = normalized
        session.commit()
    finally:
        session.close()


def downgrade() -> None:
    op.drop_index("ix_companies_partner_status", table_name="companies")
    op.drop_index("ix_companies_tier", table_name="companies")
    op.drop_column("companies", "partner_status")
    op.drop_column("companies", "sector_confidence")
    op.drop_column("companies", "revenue_2025")
    op.drop_column("companies", "tier")
