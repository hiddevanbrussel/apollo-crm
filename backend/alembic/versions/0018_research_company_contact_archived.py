"""archive research company contacts

Revision ID: 0018_research_company_contact_archived
Revises: 0017_research_company_contacts
Create Date: 2026-06-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_research_company_contact_archived"
down_revision: Union[str, None] = "0017_research_company_contacts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "research_company_contacts" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("research_company_contacts")}
    if "archived_at" not in columns:
        op.add_column(
            "research_company_contacts",
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        )

    indexes = {idx["name"] for idx in inspector.get_indexes("research_company_contacts")}
    if "ix_research_company_contacts_archived_at" not in indexes:
        op.create_index(
            "ix_research_company_contacts_archived_at",
            "research_company_contacts",
            ["archived_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "research_company_contacts" not in inspector.get_table_names():
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("research_company_contacts")}
    if "ix_research_company_contacts_archived_at" in indexes:
        op.drop_index("ix_research_company_contacts_archived_at", table_name="research_company_contacts")

    columns = {col["name"] for col in inspector.get_columns("research_company_contacts")}
    if "archived_at" in columns:
        op.drop_column("research_company_contacts", "archived_at")
