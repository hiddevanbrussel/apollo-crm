"""Manual company datasets for market research (no Apollo search required)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ResearchResult, ResearchSearch
from app.services.apollo_service import ApolloError
from app.services.country_normalize import normalize_country
from app.services.import_service import (
    ImportParseError,
    extract_company_row,
    normalize_domain,
    parse_spreadsheet,
)
from app.services.research_service import display_name

DATASET_SOURCE_MANUAL = "manual"
DATASET_SOURCE_APOLLO = "apollo"

MAX_IMPORT_BYTES = 5 * 1024 * 1024


def dataset_source(search: ResearchSearch) -> str:
    return (search.criteria or {}).get("_dataset_source") or DATASET_SOURCE_APOLLO


def is_manual_company_dataset(search: ResearchSearch) -> bool:
    return search.query_type == "organizations" and dataset_source(search) == DATASET_SOURCE_MANUAL


def _require_manual_company_dataset(search: ResearchSearch) -> None:
    if not is_manual_company_dataset(search):
        raise ApolloError(
            "This action is only available on manual company datasets.",
            status_code=400,
        )


def sync_result_count(db: Session, search: ResearchSearch) -> None:
    search.result_count = (
        db.scalar(
            select(func.count())
            .select_from(ResearchResult)
            .where(ResearchResult.search_id == search.id)
        )
        or 0
    )


def manual_org_raw_data(
    *,
    name: str,
    domain: str | None = None,
    website: str | None = None,
    industry: str | None = None,
    country: str | None = None,
    city: str | None = None,
    phone: str | None = None,
    linkedin_url: str | None = None,
    employee_count: int | None = None,
    revenue: int | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    domain = normalize_domain(domain) if domain else None
    website = website or (f"https://{domain}" if domain else None)
    raw: dict[str, Any] = {
        "name": name.strip(),
        "primary_domain": domain,
        "domain": domain,
        "website_url": website,
        "industry": industry,
        "country": country,
        "city": city,
        "phone": phone,
        "linkedin_url": linkedin_url,
        "_research_source": "manual",
    }
    if employee_count is not None:
        raw["estimated_num_employees"] = employee_count
    if revenue is not None:
        raw["annual_revenue"] = revenue
    if extra:
        raw["_extra"] = extra
    return {k: v for k, v in raw.items() if v not in (None, "")}


def create_manual_dataset(
    db: Session,
    *,
    name: str,
    created_by: int | None,
) -> ResearchSearch:
    search = ResearchSearch(
        name=name.strip(),
        query_type="organizations",
        criteria={"_dataset_source": DATASET_SOURCE_MANUAL},
        result_count=0,
        total_available=None,
        created_by=created_by,
    )
    db.add(search)
    db.commit()
    db.refresh(search)
    return search


def add_company_to_dataset(
    db: Session,
    search: ResearchSearch,
    *,
    name: str,
    domain: str | None = None,
    website: str | None = None,
    industry: str | None = None,
    country: str | None = None,
    city: str | None = None,
    phone: str | None = None,
    linkedin_url: str | None = None,
    employee_count: int | None = None,
    revenue: int | None = None,
) -> ResearchResult:
    _require_manual_company_dataset(search)
    name = name.strip()
    if not name:
        raise ApolloError("Company name is required.", status_code=400)

    raw = manual_org_raw_data(
        name=name,
        domain=domain,
        website=website,
        industry=industry,
        country=normalize_country(country),
        city=city,
        phone=phone,
        linkedin_url=linkedin_url,
        employee_count=employee_count,
        revenue=revenue,
    )
    result = ResearchResult(
        search_id=search.id,
        entity_type="company",
        apollo_id=None,
        name=display_name("organizations", raw),
        raw_data=raw,
    )
    db.add(result)
    sync_result_count(db, search)
    db.commit()
    db.refresh(result)
    return result


def import_companies_to_dataset(
    db: Session,
    search: ResearchSearch,
    *,
    filename: str,
    content: bytes,
) -> dict[str, Any]:
    _require_manual_company_dataset(search)
    if not content:
        raise ApolloError("Uploaded file is empty.", status_code=400)
    if len(content) > MAX_IMPORT_BYTES:
        raise ApolloError("File too large (max 5 MB).", status_code=400)

    try:
        rows = parse_spreadsheet(filename, content)
    except ImportParseError as exc:
        raise ApolloError(str(exc), status_code=400) from exc

    added = 0
    skipped = 0
    errors: list[str] = []
    seen: set[str] = set()

    for index, row in enumerate(rows, start=2):
        fields, extra = extract_company_row(row)
        name = (fields.get("customer_name") or "").strip()
        if not name:
            errors.append(f"Row {index}: customer_name is empty, skipped.")
            continue

        domain = normalize_domain(fields.get("domain"))
        dedup_key = f"{name.lower()}|{domain or ''}"
        if dedup_key in seen:
            skipped += 1
            continue
        seen.add(dedup_key)

        raw = manual_org_raw_data(
            name=name,
            domain=domain,
            country=normalize_country(fields.get("country")),
            extra=extra or None,
        )
        db.add(
            ResearchResult(
                search_id=search.id,
                entity_type="company",
                apollo_id=None,
                name=display_name("organizations", raw),
                raw_data=raw,
            )
        )
        added += 1

    sync_result_count(db, search)
    db.commit()
    return {
        "total_rows": len(rows),
        "added": added,
        "skipped": skipped,
        "errors": errors[:50],
    }


def delete_dataset_result(
    db: Session,
    search: ResearchSearch,
    result: ResearchResult,
) -> None:
    _require_manual_company_dataset(search)
    if result.search_id != search.id:
        raise ApolloError("Result does not belong to this dataset.", status_code=404)
    db.delete(result)
    sync_result_count(db, search)
    db.commit()
