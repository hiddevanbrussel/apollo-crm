"""add apollo person fields to contacts

Revision ID: 0005_contact_apollo_data
Revises: 0004_logokit_settings
Create Date: 2026-06-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_contact_apollo_data"
down_revision: Union[str, None] = "0004_logokit_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contacts", sa.Column("headline", sa.String(length=500), nullable=True))
    op.add_column("contacts", sa.Column("email_status", sa.String(length=60), nullable=True))
    op.add_column("contacts", sa.Column("photo_url", sa.String(length=500), nullable=True))
    op.add_column(
        "contacts",
        sa.Column(
            "apollo_data",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("contacts", "apollo_data")
    op.drop_column("contacts", "photo_url")
    op.drop_column("contacts", "email_status")
    op.drop_column("contacts", "headline")
