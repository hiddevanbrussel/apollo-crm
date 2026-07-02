"""Market research: run Apollo searches over criteria, snapshot and export them.

Results are stored separately from the CRM (in research_searches / research_results)
so market research never pollutes your real companies and contacts.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Contact, ResearchResult, ResearchSearch, SearchHistory
from app.services.apollo_filters import normalize_search_payload
from app.services.apollo_mapper import map_organization, map_person, employer_domain_from_person
from app.services.apollo_service import ApolloError, ApolloService
from app.services.company_domains import find_by_domain
from app.services.import_service import normalize_domain

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
    row["organization_domain"] = employer_domain_from_person(raw) or org_fields.get("domain")
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
        domain = normalize_domain(row.get("domain") or (result.raw_data or {}).get("primary_domain"))
        if domain and domain not in seen:
            seen.add(domain)
            domains.append(domain)
    return domains


def list_child_searches(db: Session, parent_search: ResearchSearch) -> list[ResearchSearch]:
    """People recordsets created from a company recordset (contact searches)."""
    parent_id = parent_search.id
    return list(
        db.execute(
            select(ResearchSearch)
            .where(
                or_(
                    ResearchSearch.criteria["_source_search_id"].astext == str(parent_id),
                    ResearchSearch.criteria["_source_search_id"].as_integer() == parent_id,
                )
            )
            .order_by(ResearchSearch.created_at.desc())
        )
        .scalars()
        .all()
    )


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
            key = apollo_id or f"_idx{page}_{len(seen)}"
            if key in seen:
                continue
            seen.add(key)
            if query_type == "people":
                employer_domain = employer_domain_from_person(raw)
                if employer_domain:
                    raw = dict(raw)
                    raw["_research_employer_domain"] = employer_domain
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
    skip_assign_employer_domains: bool = False,
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

    if query_type == "people" and not skip_assign_employer_domains:
        parent_id = (criteria or {}).get("_source_search_id")
        if parent_id is not None:
            parent = db.get(ResearchSearch, int(parent_id))
            if parent and parent.query_type == "organizations":
                collected = _assign_employer_domains_from_parent(db, parent, collected)

    for raw in collected:
        apollo_id = raw.get("id")
        db.add(
            ResearchResult(
                search_id=search.id,
                entity_type=entity_type,
                apollo_id=apollo_id,
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

    if query_type == "people":
        parent_id = (criteria or {}).get("_source_search_id")
        if parent_id is not None:
            from app.services.research_company_contacts import sync_people_search_to_vault

            parent = db.get(ResearchSearch, int(parent_id))
            if parent and parent.query_type == "organizations":
                company_result = None
                company_result_id = (criteria or {}).get("_source_company_result_id")
                if company_result_id is not None:
                    try:
                        company_result = db.get(ResearchResult, int(company_result_id))
                    except (TypeError, ValueError):
                        company_result = None
                sync_people_search_to_vault(
                    db,
                    parent_search=parent,
                    people_search=search,
                    company_result=company_result,
                )
    return search


def domain_from_result(result: ResearchResult) -> str | None:
    row = _flatten_org(result.raw_data or {})
    domain = normalize_domain(row.get("domain") or (result.raw_data or {}).get("primary_domain"))
    return domain


def result_detail(result: ResearchResult, search: ResearchSearch) -> dict[str, Any]:
    criteria = search.criteria or {}
    return {
        "id": result.id,
        "search_id": search.id,
        "search_name": search.name,
        "query_type": search.query_type,
        "editable": (
            search.query_type == "organizations"
            and criteria.get("_dataset_source") == "manual"
        )
        or (
            search.query_type == "people"
            and criteria.get("_dataset_source") == "manual"
            and criteria.get("_source_search_id") is not None
        ),
        "enriched": bool((result.raw_data or {}).get("_research_enriched")),
        "apollo_id": result.apollo_id or (result.raw_data or {}).get("id"),
        "name": result.name,
        "fields": flatten(search.query_type, result.raw_data or {}),
        "raw_data": result.raw_data or {},
    }


def _mark_existing_at_company_on_people(
    db: Session,
    *,
    parent_search: ResearchSearch,
    collected: list[dict[str, Any]],
    criteria: dict[str, Any],
    company_result: ResearchResult | None = None,
) -> list[dict[str, Any]]:
    """Tag people already on the company vault; merge enriched profile when matched."""
    from app.services.research_company_contacts import (
        company_result_ids_for_person,
        find_matching_prior_person_raw,
        find_matching_vault_contact,
        load_vault_contacts_by_company,
        merge_person_with_known_profile,
        merge_person_with_vault_contact,
        person_is_archived_for_company,
        sync_vault_from_child_searches,
    )

    sync_vault_from_child_searches(db, parent_search=parent_search)
    vault_by_company = load_vault_contacts_by_company(db, company_search_id=parent_search.id)

    marked: list[dict[str, Any]] = []
    for raw in collected:
        company_ids = company_result_ids_for_person(
            db,
            parent_search=parent_search,
            person_raw=raw,
            company_result=company_result,
            people_criteria=criteria,
        )
        if any(
            person_is_archived_for_company(db, company_result_id=cid, person_raw=raw)
            for cid in company_ids
        ):
            marked.append(dict(raw))
            continue

        contact = find_matching_vault_contact(
            db,
            parent_search=parent_search,
            person_raw=raw,
            vault_by_company=vault_by_company,
            company_result=company_result,
            people_criteria=criteria,
        )
        if contact:
            marked.append(merge_person_with_vault_contact(raw, contact))
            continue

        prior_raw = find_matching_prior_person_raw(
            db,
            parent_search=parent_search,
            person_raw=raw,
            company_result=company_result,
        )
        if prior_raw:
            marked.append(merge_person_with_known_profile(raw, prior_raw))
        else:
            marked.append(dict(raw))
    return marked


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
    parent_search: ResearchSearch | None = None,
    company_result: ResearchResult | None = None,
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
            collected.append(_tag_person_employer_domain(raw, candidate_domains=batch_domains))
            if len(collected) >= max_records:
                break

    if parent_search and parent_search.query_type == "organizations":
        collected = _assign_employer_domains_from_parent(db, parent_search, collected)
        collected = _mark_existing_at_company_on_people(
            db,
            parent_search=parent_search,
            collected=collected,
            criteria=stored_criteria,
            company_result=company_result,
        )
        already_count = sum(1 for raw in collected if raw.get("_already_at_company"))
        if already_count:
            stored_criteria["_already_at_company_count"] = already_count

    return _persist_search(
        db,
        name=name,
        query_type="people",
        criteria=stored_criteria,
        collected=collected,
        total_available=total_available,
        created_by=created_by,
        skip_assign_employer_domains=True,
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
        parent_search=parent_search,
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
        parent_search=parent_search,
        company_result=company_result,
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
    raw = result.raw_data or {}
    row = flatten(query_type, raw)
    row["id"] = result.id
    row["enriched"] = is_enriched(raw)
    if query_type == "people":
        row["already_at_company"] = bool(raw.get("_already_at_company"))
    return row


def _organization_lookup_fields(result: ResearchResult) -> tuple[str | None, str | None]:
    raw = result.raw_data or {}
    row = _flatten_org(raw)
    domain = (row.get("domain") or raw.get("primary_domain") or "").strip().lower() or None
    name = (row.get("name") or result.name or raw.get("name") or "").strip() or None
    return domain, name


def enrich_result_record(
    client: ApolloService,
    result: ResearchResult,
    *,
    query_type: str,
) -> dict[str, Any]:
    """Fetch complete Apollo profile and return updated raw payload."""
    if query_type == "people":
        apollo_id = _apollo_id_for_result(result)
        if not apollo_id:
            raise ApolloError("This record has no Apollo id.", status_code=400)
        response = client.get_person(apollo_id)
        entity = response.get("person") or {}
    else:
        apollo_id = _apollo_id_for_result(result)
        if not apollo_id:
            domain, name = _organization_lookup_fields(result)
            if not domain and not name:
                raise ApolloError(
                    "This record has no Apollo id. Add a domain or company name to look it up.",
                    status_code=400,
                )
            match = client.find_organization(domain=domain, name=name)
            if not match:
                label = domain or name or "this company"
                raise ApolloError(
                    f"No matching organization found in Apollo for {label}.",
                    status_code=404,
                )
            apollo_id = str(match.get("id") or "").strip()
            if not apollo_id:
                raise ApolloError("Apollo search returned a match without an id.", status_code=502)

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

    if search.query_type == "people" and enriched:
        parent_id = (search.criteria or {}).get("_source_search_id")
        if parent_id is not None:
            from app.services.research_company_contacts import sync_people_search_to_vault

            parent = db.get(ResearchSearch, int(parent_id))
            if parent and parent.query_type == "organizations":
                company_result = None
                company_result_id = (search.criteria or {}).get("_source_company_result_id")
                if company_result_id is not None:
                    try:
                        company_result = db.get(ResearchResult, int(company_result_id))
                    except (TypeError, ValueError):
                        company_result = None
                sync_people_search_to_vault(
                    db,
                    parent_search=parent,
                    people_search=search,
                    company_result=company_result,
                )

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


def _dedupe_key(*, apollo_id: str | None, email: str | None, name: str | None) -> str:
    if apollo_id:
        return f"apollo:{apollo_id.strip().lower()}"
    if email:
        return f"email:{email.strip().lower()}"
    if name:
        return f"name:{name.strip().lower()}"
    return ""


def _person_belongs_to_company(
    person_raw: dict[str, Any],
    *,
    company_domain: str,
    company_result_id: int,
    people_search: ResearchSearch,
    company_apollo_id: str | None = None,
) -> bool:
    """Return True when a saved person record belongs to a specific company row."""
    tagged_domain = normalize_domain(person_raw.get("_research_employer_domain"))
    person_domain = tagged_domain or employer_domain_from_person(person_raw)
    if company_domain and person_domain and person_domain == company_domain:
        return True

    criteria = people_search.criteria or {}
    source_result_id = criteria.get("_source_company_result_id")
    if source_result_id is not None:
        try:
            if int(source_result_id) == company_result_id:
                return True
        except (TypeError, ValueError):
            pass

    org = person_raw.get("organization") or {}
    org_apollo_id = str(org.get("id") or "").strip() or None
    if org_apollo_id and company_apollo_id and org_apollo_id == company_apollo_id:
        return True

    return False


def _tag_person_employer_domain(
    raw: dict[str, Any],
    *,
    candidate_domains: list[str] | None = None,
) -> dict[str, Any]:
    tagged = dict(raw)
    if normalize_domain(tagged.get("_research_employer_domain")):
        return tagged
    inferred = employer_domain_from_person(tagged)
    if inferred:
        tagged["_research_employer_domain"] = inferred
        return tagged
    if candidate_domains:
        normalized = [normalize_domain(d) for d in candidate_domains if normalize_domain(d)]
        if len(normalized) == 1:
            tagged["_research_employer_domain"] = normalized[0]
    return tagged


def _assign_employer_domains_from_parent(
    db: Session,
    parent_search: ResearchSearch,
    collected: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Stamp employer domain on people when Apollo search omits organization data."""
    if parent_search.query_type != "organizations":
        return collected

    companies = (
        db.execute(
            select(ResearchResult).where(
                ResearchResult.search_id == parent_search.id,
                ResearchResult.entity_type == "company",
            )
        )
        .scalars()
        .all()
    )
    domain_to_company: dict[str, ResearchResult] = {}
    apollo_to_company: dict[str, ResearchResult] = {}
    for company in companies:
        domain = domain_from_result(company)
        if domain:
            domain_to_company[domain] = company
        apollo_id = _apollo_id_for_result(company)
        if apollo_id:
            apollo_to_company[apollo_id] = company

    updated: list[dict[str, Any]] = []
    for raw in collected:
        tagged = _tag_person_employer_domain(raw)
        if normalize_domain(tagged.get("_research_employer_domain")):
            updated.append(tagged)
            continue

        org = tagged.get("organization") or {}
        org_apollo_id = str(org.get("id") or "").strip() or None
        if org_apollo_id and org_apollo_id in apollo_to_company:
            company = apollo_to_company[org_apollo_id]
            domain = domain_from_result(company)
            if domain:
                tagged["_research_employer_domain"] = domain
                updated.append(tagged)
                continue

        inferred = employer_domain_from_person(tagged)
        if inferred and inferred in domain_to_company:
            tagged["_research_employer_domain"] = inferred

        updated.append(tagged)
    return updated


def _company_results_for_domain(
    db: Session,
    domain: str,
    *,
    apollo_id: str | None = None,
) -> list[tuple[ResearchResult, ResearchSearch]]:
    """Research company snapshots sharing a domain (or Apollo id)."""
    domain = normalize_domain(domain) or domain.strip().lower()
    match_clauses = []
    if domain:
        match_clauses.extend(
            [
                func.lower(ResearchResult.raw_data["primary_domain"].astext) == domain,
                func.lower(ResearchResult.raw_data["domain"].astext) == domain,
            ]
        )
    if apollo_id:
        match_clauses.append(ResearchResult.apollo_id == apollo_id)

    if not match_clauses:
        return []

    rows = (
        db.execute(
            select(ResearchResult, ResearchSearch)
            .join(ResearchSearch, ResearchResult.search_id == ResearchSearch.id)
            .where(
                ResearchResult.entity_type == "company",
                or_(*match_clauses),
            )
            .order_by(ResearchResult.id.desc())
        )
        .all()
    )

    verified: list[tuple[ResearchResult, ResearchSearch]] = []
    seen_ids: set[int] = set()
    for result, search in rows:
        if result.id in seen_ids:
            continue
        result_domain = domain_from_result(result)
        result_apollo = _apollo_id_for_result(result)
        if domain and result_domain == domain:
            verified.append((result, search))
            seen_ids.add(result.id)
        elif apollo_id and result_apollo == apollo_id:
            verified.append((result, search))
            seen_ids.add(result.id)
    return verified


def list_related_companies_for_result(
    db: Session,
    *,
    parent_search: ResearchSearch,
    company_result: ResearchResult,
) -> dict[str, Any]:
    """Link research and CRM records that share this company's domain."""
    if parent_search.query_type != "organizations":
        raise ApolloError("Related companies are only available for company research.", status_code=400)
    if company_result.entity_type != "company":
        raise ApolloError("This record is not a company.", status_code=400)

    domain = domain_from_result(company_result)
    apollo_id = _apollo_id_for_result(company_result)
    if not domain and not apollo_id:
        return {"domain": None, "total": 0, "items": []}

    items: list[dict[str, Any]] = []

    for result, search in _company_results_for_domain(db, domain or "", apollo_id=apollo_id):
        row = _flatten_org(result.raw_data or {})
        rid = _apollo_id_for_result(result)
        items.append(
            {
                "source": "research",
                "id": result.id,
                "search_id": search.id,
                "search_name": search.name,
                "name": row.get("name") or result.name,
                "domain": row.get("domain") or domain,
                "apollo_id": rid,
                "enriched": is_enriched(result.raw_data),
                "is_current": result.id == company_result.id,
                "record_source": None,
            }
        )

    if domain:
        for crm in find_by_domain(db, domain):
            crm_apollo = (crm.apollo_id or "").strip() or None
            items.append(
                {
                    "source": "crm",
                    "id": crm.id,
                    "search_id": None,
                    "search_name": None,
                    "name": crm.name,
                    "domain": crm.domain or domain,
                    "apollo_id": crm_apollo,
                    "enriched": crm.enrichment_status == "enriched",
                    "is_current": False,
                    "record_source": crm.source,
                }
            )

    items.sort(key=lambda row: (not row["is_current"], row["source"] != "crm", row["name"] or ""))
    return {"domain": domain, "total": len(items), "items": items}


def list_contacts_for_company_result(
    db: Session,
    *,
    parent_search: ResearchSearch,
    company_result: ResearchResult,
) -> dict[str, Any]:
    """Contacts already known for a research company: saved people research + CRM."""
    if parent_search.query_type != "organizations":
        raise ApolloError("Contacts are only available for company research.", status_code=400)
    if company_result.entity_type != "company":
        raise ApolloError("This record is not a company.", status_code=400)

    domain = domain_from_result(company_result)

    from app.services.research_company_contacts import list_vault_contacts_for_company

    items: list[dict[str, Any]] = list_vault_contacts_for_company(
        db, parent_search=parent_search, company_result=company_result
    )
    seen: set[str] = set()
    for item in items:
        key = _dedupe_key(
            apollo_id=item.get("apollo_id"),
            email=item.get("email"),
            name=item.get("name"),
        )
        if key:
            seen.add(key)

    if not domain:
        return {"domain": None, "total": len(items), "items": items}

    for crm_company in find_by_domain(db, domain):
        crm_contacts = (
            db.execute(
                select(Contact)
                .where(Contact.company_id == crm_company.id)
                .order_by(Contact.full_name, Contact.id)
            )
            .scalars()
            .all()
        )
        for contact in crm_contacts:
            apollo_id = contact.apollo_id
            name = contact.full_name or " ".join(
                p for p in [contact.first_name, contact.last_name] if p
            ).strip() or None
            key = _dedupe_key(apollo_id=apollo_id, email=contact.email, name=name)
            if key and key in seen:
                continue
            if key:
                seen.add(key)

            items.append(
                {
                    "source": "crm",
                    "id": contact.id,
                    "name": name,
                    "title": contact.title or contact.title_ai,
                    "email": contact.email,
                    "phone": contact.phone,
                    "seniority": contact.seniority,
                    "linkedin_url": contact.linkedin_url,
                    "apollo_id": apollo_id,
                    "enriched": contact.enrichment_status == "enriched",
                    "enrichment_status": contact.enrichment_status,
                    "contact_source": contact.source,
                    "research_search_id": None,
                    "research_search_name": None,
                    "company_id": crm_company.id,
                }
            )

    return {"domain": domain, "total": len(items), "items": items}


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
