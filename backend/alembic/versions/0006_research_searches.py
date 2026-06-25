"""add market research tables

Revision ID: 0006_research_searches
Revises: 0005_contact_apollo_data
Create Date: 2026-06-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_research_searches"
down_revision: Union[str, None] = "0005_contact_apollo_data"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_searches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("query_type", sa.String(length=50), nullable=False),
        sa.Column("criteria", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_available", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "research_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "search_id",
            sa.Integer(),
            sa.ForeignKey("research_searches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("apollo_id", sa.String(length=120), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_research_results_search_id", "research_results", ["search_id"])
    op.create_index("ix_research_results_apollo_id", "research_results", ["apollo_id"])


def downgrade() -> None:
    op.drop_index("ix_research_results_apollo_id", table_name="research_results")
    op.drop_index("ix_research_results_search_id", table_name="research_results")
    op.drop_table("research_results")
    op.drop_table("research_searches")
