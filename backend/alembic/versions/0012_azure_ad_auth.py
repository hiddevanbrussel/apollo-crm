"""azure ad auth and user oauth fields

Revision ID: 0012_azure_ad_auth
Revises: 0011_prospeo_integration
Create Date: 2026-06-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0012_azure_ad_auth"
down_revision: Union[str, None] = "0011_prospeo_integration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "azure_ad_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("allowed_domains", JSONB(), nullable=False, server_default="[]"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.add_column("users", sa.Column("auth_provider", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("azure_oid", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("azure_tenant_id", sa.String(length=64), nullable=True))
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=True)

    op.execute("UPDATE users SET auth_provider = 'local' WHERE auth_provider IS NULL")
    op.alter_column("users", "auth_provider", nullable=False, server_default="local")

    op.create_index("ix_users_azure_oid", "users", ["azure_oid"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_azure_oid", table_name="users")
    op.drop_column("users", "azure_tenant_id")
    op.drop_column("users", "azure_oid")
    op.drop_column("users", "auth_provider")
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=False)
    op.drop_table("azure_ad_settings")
