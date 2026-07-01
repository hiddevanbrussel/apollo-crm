"""Export CRM companies to CSV or XLSX."""

from __future__ import annotations

import csv
import io
from typing import Any

from app.models import Company
from app.services.company_domains import list_domains

EXPORT_COLUMNS = [
    "name",
    "domain",
    "domains",
    "website",
    "linkedin_url",
    "industry",
    "tier",
    "employee_count",
    "revenue",
    "revenue_2025",
    "country",
    "city",
    "phone",
    "partner_status",
    "sector_confidence",
    "enrichment_status",
    "source",
    "contact_count",
    "apollo_id",
    "description",
]


def _row(company: Company, *, contact_count: int = 0) -> dict[str, Any]:
    domains = list_domains(company)
    return {
        "name": company.name,
        "domain": company.domain,
        "domains": ", ".join(domains),
        "website": company.website,
        "linkedin_url": company.linkedin_url,
        "industry": company.industry,
        "tier": company.tier,
        "employee_count": company.employee_count,
        "revenue": company.revenue,
        "revenue_2025": company.revenue_2025,
        "country": company.country,
        "city": company.city,
        "phone": company.phone,
        "partner_status": company.partner_status,
        "sector_confidence": company.sector_confidence,
        "enrichment_status": company.enrichment_status,
        "source": company.source,
        "contact_count": contact_count,
        "apollo_id": company.apollo_id,
        "description": company.description,
    }


def export_csv(companies: list[Company], contact_counts: dict[int, int]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(EXPORT_COLUMNS)
    for company in companies:
        row = _row(company, contact_count=contact_counts.get(company.id, 0))
        writer.writerow(["" if row.get(c) is None else row.get(c) for c in EXPORT_COLUMNS])
    return buffer.getvalue()


def export_xlsx(companies: list[Company], contact_counts: dict[int, int]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Companies"
    ws.append(EXPORT_COLUMNS)
    for company in companies:
        row = _row(company, contact_count=contact_counts.get(company.id, 0))
        ws.append(["" if row.get(c) is None else row.get(c) for c in EXPORT_COLUMNS])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
