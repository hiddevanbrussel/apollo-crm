"""lusha settings and contact lusha fields

Revision ID: 0020_lusha_integration
Revises: 0019_groq_assistant_enabled
Create Date: 2026-06-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0020_lusha_integration"
down_revision: Union[str, None] = "0019_groq_assistant_enabled"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "lusha_settings" not in inspector.get_table_names():
        op.create_table(
            "lusha_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("api_key_encrypted", sa.Text(), nullable=True),
            sa.Column(
                "base_url",
                sa.String(length=255),
                nullable=False,
                server_default="https://api.lusha.com",
            ),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    columns = {c["name"] for c in inspector.get_columns("contacts")}
    if "lusha_id" not in columns:
        op.add_column("contacts", sa.Column("lusha_id", sa.String(length=120), nullable=True))
    if "lusha_data" not in columns:
        op.add_column(
            "contacts",
            sa.Column("lusha_data", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        )
    indexes = {idx["name"] for idx in inspector.get_indexes("contacts")}
    if "ix_contacts_lusha_id" not in indexes:
        op.create_index("ix_contacts_lusha_id", "contacts", ["lusha_id"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "contacts" in inspector.get_table_names():
        indexes = {idx["name"] for idx in inspector.get_indexes("contacts")}
        if "ix_contacts_lusha_id" in indexes:
            op.drop_index("ix_contacts_lusha_id", table_name="contacts")
        columns = {c["name"] for c in inspector.get_columns("contacts")}
        if "lusha_data" in columns:
            op.drop_column("contacts", "lusha_data")
        if "lusha_id" in columns:
            op.drop_column("contacts", "lusha_id")
    if "lusha_settings" in inspector.get_table_names():
        op.drop_table("lusha_settings")
