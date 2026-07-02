"""research company contacts vault

Revision ID: 0017_research_company_contacts
Revises: 0016_company_domain_nonunique
Create Date: 2026-06-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_research_company_contacts"
down_revision: Union[str, None] = "0016_company_domain_nonunique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "research_company_contacts" in inspector.get_table_names():
        return

    op.create_table(
        "research_company_contacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_search_id", sa.Integer(), nullable=False),
        sa.Column("company_result_id", sa.Integer(), nullable=False),
        sa.Column("people_search_id", sa.Integer(), nullable=True),
        sa.Column("apollo_id", sa.String(length=120), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=60), nullable=True),
        sa.Column("seniority", sa.String(length=80), nullable=True),
        sa.Column("linkedin_url", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="apollo"),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_search_id"], ["research_searches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_result_id"], ["research_results.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["people_search_id"], ["research_searches.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_research_company_contacts_company_result_id",
        "research_company_contacts",
        ["company_result_id"],
    )
    op.create_index(
        "ix_research_company_contacts_company_search_id",
        "research_company_contacts",
        ["company_search_id"],
    )
    op.create_index(
        "ix_research_company_contacts_apollo_id",
        "research_company_contacts",
        ["apollo_id"],
    )
    op.create_index(
        "ix_research_company_contacts_email",
        "research_company_contacts",
        ["email"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_company_contacts_email", table_name="research_company_contacts")
    op.drop_index("ix_research_company_contacts_apollo_id", table_name="research_company_contacts")
    op.drop_index("ix_research_company_contacts_company_search_id", table_name="research_company_contacts")
    op.drop_index("ix_research_company_contacts_company_result_id", table_name="research_company_contacts")
    op.drop_table("research_company_contacts")
