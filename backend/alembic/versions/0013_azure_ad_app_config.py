"""azure ad settings credentials in app

Revision ID: 0013_azure_ad_app_config
Revises: 0012_azure_ad_auth
Create Date: 2026-06-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_azure_ad_app_config"
down_revision: Union[str, None] = "0012_azure_ad_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_AUTHORITY = "https://login.microsoftonline.com/organizations"


def upgrade() -> None:
    op.add_column("azure_ad_settings", sa.Column("client_id", sa.String(length=128), nullable=True))
    op.add_column("azure_ad_settings", sa.Column("client_secret_encrypted", sa.Text(), nullable=True))
    op.add_column(
        "azure_ad_settings",
        sa.Column(
            "authority",
            sa.String(length=512),
            nullable=False,
            server_default=DEFAULT_AUTHORITY,
        ),
    )
    op.add_column("azure_ad_settings", sa.Column("redirect_uri", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("azure_ad_settings", "redirect_uri")
    op.drop_column("azure_ad_settings", "authority")
    op.drop_column("azure_ad_settings", "client_secret_encrypted")
    op.drop_column("azure_ad_settings", "client_id")
