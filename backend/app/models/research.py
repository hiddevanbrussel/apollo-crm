from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ResearchSearch(Base):
    """A saved market-research search: the criteria plus a snapshot of results."""

    __tablename__ = "research_searches"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    query_type: Mapped[str] = mapped_column(String(50), nullable=False)  # people | organizations
    criteria: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_available: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    results: Mapped[list["ResearchResult"]] = relationship(
        back_populates="search", cascade="all, delete-orphan"
    )


class ResearchResult(Base):
    """One captured record (company or person) belonging to a research search."""

    __tablename__ = "research_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    search_id: Mapped[int] = mapped_column(
        ForeignKey("research_searches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # company | person
    apollo_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_data: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    search: Mapped["ResearchSearch"] = relationship(back_populates="results")
