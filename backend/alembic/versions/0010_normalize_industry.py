"""normalize company industry casing

Revision ID: 0010_normalize_industry
Revises: 0009_company_import_fields
Create Date: 2026-06-25

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.orm import Session

revision: str = "0010_normalize_industry"
down_revision: Union[str, None] = "0009_company_import_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.models.company import Company
    from app.services.industry_normalize import normalize_industry

    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        for company in session.query(Company).filter(Company.industry.is_not(None)):
            normalized = normalize_industry(company.industry)
            if normalized and normalized != company.industry:
                company.industry = normalized
        session.commit()
    finally:
        session.close()


def downgrade() -> None:
    pass
