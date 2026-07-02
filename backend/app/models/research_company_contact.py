from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ResearchCompanyContact(Base):
    """Persistent contacts linked to a company row in a research recordset.

    Survives deletion of contact recordsets (people searches).
    """

    __tablename__ = "research_company_contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_search_id: Mapped[int] = mapped_column(
        ForeignKey("research_searches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_result_id: Mapped[int] = mapped_column(
        ForeignKey("research_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    people_search_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_searches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    apollo_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(60), nullable=True)
    seniority: Mapped[str | None] = mapped_column(String(80), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="apollo", nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
