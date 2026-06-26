"""prospeo settings and contact prospeo fields

Revision ID: 0011_prospeo_integration
Revises: 0010_normalize_industry
Create Date: 2026-06-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0011_prospeo_integration"
down_revision: Union[str, None] = "0010_normalize_industry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prospeo_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column(
            "base_url",
            sa.String(length=255),
            nullable=False,
            server_default="https://api.prospeo.io",
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column("contacts", sa.Column("prospeo_id", sa.String(length=120), nullable=True))
    op.add_column(
        "contacts",
        sa.Column("prospeo_data", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_contacts_prospeo_id", "contacts", ["prospeo_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_contacts_prospeo_id", table_name="contacts")
    op.drop_column("contacts", "prospeo_data")
    op.drop_column("contacts", "prospeo_id")
    op.drop_table("prospeo_settings")
