"""Market research: run Apollo searches over criteria, snapshot and export them.

Results are stored separately from the CRM (in research_searches / research_results)
so market research never pollutes your real companies and contacts.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ResearchResult, ResearchSearch, SearchHistory
from app.services.apollo_filters import normalize_search_payload
from app.services.apollo_mapper import map_organization, map_person
from app.services.apollo_service import ApolloError, ApolloService

logger = logging.getLogger("research.service")

MAX_RECORDS_CAP = 2000
PAGE_SIZE = 100
DOMAIN_BATCH_SIZE = 1000

ORG_COLUMNS = [
    "name",
    "domain",
    "website",
    "industry",
    "employee_count",
    "revenue",
    "country",
    "city",
    "phone",
    "linkedin_url",
    "apollo_id",
]

PERSON_COLUMNS = [
    "name",
    "title",
    "email",
    "phone",
    "seniority",
    "department",
    "city",
    "country",
    "organization_name",
    "organization_domain",
    "linkedin_url",
    "apollo_id",
]


def columns_for(query_type: str) -> list[str]:
    return ORG_COLUMNS if query_type == "organizations" else PERSON_COLUMNS


def _flatten_org(raw: dict[str, Any]) -> dict[str, Any]:
    f = map_organization(raw)
    return {c: f.get(c) for c in ORG_COLUMNS}


def _flatten_person(raw: dict[str, Any]) -> dict[str, Any]:
    f = map_person(raw)
    org = f.pop("_organization", None) or {}
    org_fields = map_organization(org) if org else {}
    row = {c: f.get(c) for c in PERSON_COLUMNS}
    row["name"] = f.get("full_name")
    row["organization_name"] = org_fields.get("name") or (raw.get("organization") or {}).get("name")
    row["organization_domain"] = org_fields.get("domain")
    return row


def flatten(query_type: str, raw: dict[str, Any]) -> dict[str, Any]:
    return _flatten_org(raw) if query_type == "organizations" else _flatten_person(raw)


def display_name(query_type: str, raw: dict[str, Any]) -> str | None:
    if query_type == "organizations":
        return raw.get("name")
    return raw.get("name") or " ".join(
        p for p in [raw.get("first_name"), raw.get("last_name")] if p
    ) or None


def domains_from_company_search(db: Session, search: ResearchSearch) -> list[str]:
    """Unique domains from a saved company research snapshot."""
    if search.query_type != "organizations":
        return []

    rows = (
        db.execute(
            select(ResearchResult)
            .where(ResearchResult.search_id == search.id)
            .order_by(ResearchResult.id)
        )
        .scalars()
        .all()
    )

    domains: list[str] = []
    seen: set[str] = set()
    for result in rows:
        row = _flatten_org(result.raw_data or {})
        domain = (row.get("domain") or "").strip().lower()
        if domain and domain not in seen:
            seen.add(domain)
            domains.append(domain)
    return domains


def _collect_from_apollo(
    client: ApolloService,
    *,
    query_type: str,
    criteria: dict[str, Any],
    max_records: int,
) -> tuple[list[dict[str, Any]], int | None]:
    """Paginate an Apollo search until ``max_records`` unique rows are collected."""
    max_records = max(1, min(max_records, MAX_RECORDS_CAP))
    per_page = min(PAGE_SIZE, max_records)

    collected: list[dict[str, Any]] = []
    seen: set[str] = set()
    total_available: int | None = None
    page = 1

    while len(collected) < max_records:
        payload = normalize_search_payload(criteria)
        payload = {k: v for k, v in payload.items() if v not in (None, "", [])}
        payload["page"] = page
        payload["per_page"] = per_page
        if query_type == "organizations":
            response = client.search_organizations(payload)
            batch = response.get("organizations") or response.get("accounts") or []
        else:
            response = client.search_people_api(payload)
            batch = response.get("people") or response.get("contacts") or []

        pagination = response.get("pagination") or {}
        if total_available is None:
            total_available = pagination.get("total_entries")

        if not batch:
            break

        for raw in batch:
            apollo_id = raw.get("id")
            key = apollo_id or f"_idx{len(collected)}"
            if key in seen:
                continue
            seen.add(key)
            collected.append(raw)
            if len(collected) >= max_records:
                break

        total_pages = pagination.get("total_pages")
        if total_pages and page >= total_pages:
            break
        page += 1

    return collected, total_available


def _persist_search(
    db: Session,
    *,
    name: str,
    query_type: str,
    criteria: dict[str, Any],
    collected: list[dict[str, Any]],
    total_available: int | None,
    created_by: int | None,
) -> ResearchSearch:
    entity_type = "company" if query_type == "organizations" else "person"
    search = ResearchSearch(
        name=name,
        query_type=query_type,
        criteria=criteria,
        result_count=len(collected),
        total_available=total_available,
        created_by=created_by,
    )
    db.add(search)
    db.flush()

    for raw in collected:
        db.add(
            ResearchResult(
                search_id=search.id,
                entity_type=entity_type,
                apollo_id=raw.get("id"),
                name=display_name(query_type, raw),
                raw_data=raw,
            )
        )

    db.add(
        SearchHistory(
            query_type=query_type,
            query_payload=criteria,
            result_count=len(collected),
            created_by=created_by,
        )
    )
    db.commit()
    db.refresh(search)
    return search


def domain_from_result(result: ResearchResult) -> str | None:
    row = _flatten_org(result.raw_data or {})
    domain = (row.get("domain") or "").strip().lower()
    return domain or None


def result_detail(result: ResearchResult, search: ResearchSearch) -> dict[str, Any]:
    return {
        "id": result.id,
        "search_id": search.id,
        "search_name": search.name,
        "query_type": search.query_type,
        "enriched": bool((result.raw_data or {}).get("_research_enriched")),
        "apollo_id": result.apollo_id or (result.raw_data or {}).get("id"),
        "name": result.name,
        "fields": flatten(search.query_type, result.raw_data or {}),
        "raw_data": result.raw_data or {},
    }


def run_people_for_domains(
    db: Session,
    client: ApolloService,
    *,
    name: str,
    criteria: dict[str, Any],
    max_records: int,
    domains: list[str],
    created_by: int | None,
    source_meta: dict[str, Any],
) -> ResearchSearch:
    if not domains:
        raise ApolloError("No domains to search people for.", status_code=400)

    max_records = max(1, min(max_records, MAX_RECORDS_CAP))
    people_criteria = {k: v for k, v in criteria.items() if not str(k).startswith("_")}
    stored_criteria = {
        **people_criteria,
        **source_meta,
        "organization_domains": domains,
    }

    collected: list[dict[str, Any]] = []
    seen: set[str] = set()
    total_available: int | None = None

    for batch_start in range(0, len(domains), DOMAIN_BATCH_SIZE):
        if len(collected) >= max_records:
            break
        batch_domains = domains[batch_start : batch_start + DOMAIN_BATCH_SIZE]
        batch_criteria = {**people_criteria, "organization_domains": batch_domains}
        batch_collected, batch_total = _collect_from_apollo(
            client,
            query_type="people",
            criteria=batch_criteria,
            max_records=max_records - len(collected),
        )
        if batch_total is not None:
            total_available = (total_available or 0) + batch_total

        for raw in batch_collected:
            apollo_id = raw.get("id")
            key = apollo_id or f"_idx{len(collected)}"
            if key in seen:
                continue
            seen.add(key)
            collected.append(raw)
            if len(collected) >= max_records:
                break

    return _persist_search(
        db,
        name=name,
        query_type="people",
        criteria=stored_criteria,
        collected=collected,
        total_available=total_available,
        created_by=created_by,
    )


def run_people_for_company_search(
    db: Session,
    client: ApolloService,
    *,
    parent_search: ResearchSearch,
    name: str,
    criteria: dict[str, Any],
    max_records: int,
    created_by: int | None,
) -> ResearchSearch:
    """Find people at companies from a saved company research, with extra people filters."""
    if parent_search.query_type != "organizations":
        raise ApolloError("People search can only be run from company research.", status_code=400)

    domains = domains_from_company_search(db, parent_search)
    if not domains:
        raise ApolloError(
            "This company research has no domains to search people for.",
            status_code=400,
        )

    return run_people_for_domains(
        db,
        client,
        name=name,
        criteria=criteria,
        max_records=max_records,
        domains=domains,
        created_by=created_by,
        source_meta={
            "_source_search_id": parent_search.id,
            "_source_search_name": parent_search.name,
        },
    )


def run_people_for_company_result(
    db: Session,
    client: ApolloService,
    *,
    parent_search: ResearchSearch,
    company_result: ResearchResult,
    name: str,
    criteria: dict[str, Any],
    max_records: int,
    created_by: int | None,
) -> ResearchSearch:
    if parent_search.query_type != "organizations":
        raise ApolloError("People search can only be run from company research.", status_code=400)
    if company_result.entity_type != "company":
        raise ApolloError("This record is not a company.", status_code=400)

    domain = domain_from_result(company_result)
    if not domain:
        raise ApolloError("This company has no domain to search people for.", status_code=400)

    company_name = company_result.name or (company_result.raw_data or {}).get("name")
    return run_people_for_domains(
        db,
        client,
        name=name,
        criteria=criteria,
        max_records=max_records,
        domains=[domain],
        created_by=created_by,
        source_meta={
            "_source_search_id": parent_search.id,
            "_source_search_name": parent_search.name,
            "_source_company_result_id": company_result.id,
            "_source_company_name": company_name,
            "_source_company_domain": domain,
        },
    )


def run_and_store(
    db: Session,
    client: ApolloService,
    *,
    name: str,
    query_type: str,
    criteria: dict[str, Any],
    max_records: int,
    created_by: int | None,
) -> ResearchSearch:
    """Run a paginated Apollo search and persist the snapshot."""
    if query_type not in ("organizations", "people"):
        raise ApolloError("Unknown search type.", status_code=400)

    collected, total_available = _collect_from_apollo(
        client,
        query_type=query_type,
        criteria=criteria,
        max_records=max_records,
    )
    return _persist_search(
        db,
        name=name,
        query_type=query_type,
        criteria=criteria,
        collected=collected,
        total_available=total_available,
        created_by=created_by,
    )


MAX_BULK_ENRICH = 100


def is_enriched(raw: dict[str, Any] | None) -> bool:
    return bool((raw or {}).get("_research_enriched"))


def _mark_enriched(entity: dict[str, Any]) -> dict[str, Any]:
    from datetime import datetime, timezone

    marked = dict(entity)
    marked["_research_enriched"] = True
    marked["_research_enriched_at"] = datetime.now(timezone.utc).isoformat()
    return marked


def _apollo_id_for_result(result: ResearchResult) -> str | None:
    raw = result.raw_data or {}
    apollo_id = (result.apollo_id or raw.get("id") or "").strip()
    return apollo_id or None


def result_item(result: ResearchResult, query_type: str) -> dict[str, Any]:
    row = flatten(query_type, result.raw_data or {})
    row["id"] = result.id
    row["enriched"] = is_enriched(result.raw_data)
    return row


def enrich_result_record(
    client: ApolloService,
    result: ResearchResult,
    *,
    query_type: str,
) -> dict[str, Any]:
    """Fetch complete Apollo profile and return updated raw payload."""
    apollo_id = _apollo_id_for_result(result)
    if not apollo_id:
        raise ApolloError("This record has no Apollo id.", status_code=400)

    if query_type == "people":
        response = client.get_person(apollo_id)
        entity = response.get("person") or {}
    else:
        response = client.get_organization(apollo_id)
        entity = response.get("organization") or response.get("account") or {}

    if not entity:
        raise ApolloError("Apollo returned no profile details.", status_code=502)

    return _mark_enriched(entity)


def enrich_results(
    db: Session,
    client: ApolloService,
    search: ResearchSearch,
    *,
    result_ids: list[int] | None = None,
    all_unenriched: bool = False,
) -> dict[str, Any]:
    """Enrich one or more research records via Apollo complete-info endpoints."""
    stmt = select(ResearchResult).where(ResearchResult.search_id == search.id)
    if result_ids:
        stmt = stmt.where(ResearchResult.id.in_(result_ids))
    rows = db.execute(stmt.order_by(ResearchResult.id)).scalars().all()

    if all_unenriched:
        rows = [row for row in rows if not is_enriched(row.raw_data)]

    if result_ids and not all_unenriched:
        found_ids = {row.id for row in rows}
        missing = [rid for rid in result_ids if rid not in found_ids]
        if missing:
            raise ApolloError(f"Unknown result ids for this search: {missing[:5]}", status_code=404)

    limit = MAX_RECORDS_CAP if all_unenriched else MAX_BULK_ENRICH
    if len(rows) > limit:
        raise ApolloError(
            f"Enrich at most {limit} records per request.",
            status_code=400,
        )

    enriched = 0
    skipped = 0
    failed = 0
    errors: list[str] = []

    for row in rows:
        if not all_unenriched and result_ids and is_enriched(row.raw_data):
            skipped += 1
            continue
        try:
            payload = enrich_result_record(client, row, query_type=search.query_type)
        except ApolloError as exc:
            failed += 1
            label = row.name or row.apollo_id or str(row.id)
            errors.append(f"{label}: {exc.message}")
            continue

        row.raw_data = payload
        row.apollo_id = payload.get("id") or row.apollo_id
        row.name = display_name(search.query_type, payload) or row.name
        enriched += 1

    db.commit()
    return {
        "enriched": enriched,
        "skipped": skipped,
        "failed": failed,
        "total": len(rows),
        "errors": errors[:20],
    }


def export_csv(search: ResearchSearch, results: list[ResearchResult]) -> str:
    cols = columns_for(search.query_type)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(cols)
    for r in results:
        row = flatten(search.query_type, r.raw_data or {})
        writer.writerow(["" if row.get(c) is None else row.get(c) for c in cols])
    return buffer.getvalue()


def export_xlsx(search: ResearchSearch, results: list[ResearchResult]) -> bytes:
    from openpyxl import Workbook

    cols = columns_for(search.query_type)
    wb = Workbook()
    ws = wb.active
    ws.title = "Results"
    ws.append(cols)
    for r in results:
        row = flatten(search.query_type, r.raw_data or {})
        ws.append(["" if row.get(c) is None else row.get(c) for c in cols])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
