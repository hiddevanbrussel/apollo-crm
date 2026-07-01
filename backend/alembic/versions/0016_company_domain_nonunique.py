"""allow duplicate company domains

Revision ID: 0016_company_domain_nonunique
Revises: 0015_company_saved_filters
Create Date: 2026-06-25

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0016_company_domain_nonunique"
down_revision: Union[str, None] = "0015_company_saved_filters"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_companies_domain", table_name="companies")
    op.create_index("ix_companies_domain", "companies", ["domain"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_companies_domain", table_name="companies")
    op.create_index("ix_companies_domain", "companies", ["domain"], unique=True)
