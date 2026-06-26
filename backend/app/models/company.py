from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    employee_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    revenue: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(60), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    apollo_id: Mapped[str | None] = mapped_column(String(120), unique=True, index=True, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    enrichment_status: Mapped[str] = mapped_column(String(50), default="none", nullable=False)
    # Arbitrary extra fields preserved from imports (e.g. Tier, Sector, mcp_id).
    extra_data: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    # Additional domains beyond the primary ``domain`` column (stored lowercase).
    domains: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    tier: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    revenue_2025: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sector_confidence: Mapped[str | None] = mapped_column(String(50), nullable=True)
    partner_status: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    contacts: Mapped[list["Contact"]] = relationship(  # noqa: F821
        back_populates="company", cascade="all, delete-orphan"
    )
