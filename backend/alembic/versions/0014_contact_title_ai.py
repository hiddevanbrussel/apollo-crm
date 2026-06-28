"""contact title_ai field

Revision ID: 0014_contact_title_ai
Revises: 0013_azure_ad_app_config
Create Date: 2026-06-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_contact_title_ai"
down_revision: Union[str, None] = "0013_azure_ad_app_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contacts", sa.Column("title_ai", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("contacts", "title_ai")
