"""add company product_line

Revision ID: 0007_company_product_line
Revises: 0006_research_searches
Create Date: 2026-06-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_company_product_line"
down_revision: Union[str, None] = "0006_research_searches"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("product_line", sa.String(length=50), nullable=True))
    op.create_index("ix_companies_product_line", "companies", ["product_line"])

    op.execute(
        """
        UPDATE companies
        SET product_line = CASE lower(trim(COALESCE(extra_data->>'Product', extra_data->>'product', '')))
            WHEN 'xink' THEN 'Xink'
            WHEN 'xink product line' THEN 'Xink'
            WHEN 'xink product' THEN 'Xink'
            WHEN 'cgx' THEN 'CGX'
            WHEN 'officeatwork' THEN 'OfficeAtWork'
            WHEN 'office at work' THEN 'OfficeAtWork'
            WHEN 'office-at-work' THEN 'OfficeAtWork'
            WHEN 'eformity' THEN 'eFormity'
            WHEN 'e-formity' THEN 'eFormity'
            WHEN 'create' THEN 'Create'
            ELSE NULL
        END
        WHERE trim(COALESCE(extra_data->>'Product', extra_data->>'product', '')) <> ''
        """
    )


def downgrade() -> None:
    op.drop_index("ix_companies_product_line", table_name="companies")
    op.drop_column("companies", "product_line")
