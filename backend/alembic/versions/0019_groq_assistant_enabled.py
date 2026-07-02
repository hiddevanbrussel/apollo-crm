"""add groq assistant_enabled setting

Revision ID: 0019_groq_assistant_enabled
Revises: 0018_vault_contact_archive
Create Date: 2026-06-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_groq_assistant_enabled"
down_revision: Union[str, None] = "0018_vault_contact_archive"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "groq_settings" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("groq_settings")}
    if "assistant_enabled" not in columns:
        op.add_column(
            "groq_settings",
            sa.Column("assistant_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "groq_settings" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("groq_settings")}
    if "assistant_enabled" in columns:
        op.drop_column("groq_settings", "assistant_enabled")
