"""add groq_settings table

Revision ID: 0003_groq_settings
Revises: 0002_company_extra_data
Create Date: 2026-06-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_groq_settings"
down_revision: Union[str, None] = "0002_company_extra_data"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "groq_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("base_url", sa.String(length=255), nullable=False, server_default="https://api.groq.com"),
        sa.Column("model", sa.String(length=120), nullable=False, server_default="groq/compound"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("groq_settings")
