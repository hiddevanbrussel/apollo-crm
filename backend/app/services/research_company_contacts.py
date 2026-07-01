"""Persistent research contacts per company row (survives contact recordset deletion)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import ResearchCompanyContact, ResearchResult, ResearchSearch
from app.services.apollo_mapper import employer_domain_from_person, map_person
from app.services.apollo_service import ApolloError
from app.services.import_service import normalize_domain
from app.services.research_service import (
    _dedupe_key,
    _flatten_person,
    _person_belongs_to_company,
    domain_from_result,
    is_enriched,
)


def _contact_row(contact: ResearchCompanyContact) -> dict[str, Any]:
    fields = _flatten_person(contact.raw_data or {})
    return {
        "source": "research",
        "id": contact.id,
        "vault_id": contact.id,
        "name": contact.name or fields.get("name"),
        "title": contact.title or fields.get("title"),
        "email": contact.email or fields.get("email"),
        "phone": contact.phone or fields.get("phone"),
        "seniority": contact.seniority or fields.get("seniority"),
        "linkedin_url": contact.linkedin_url or fields.get("linkedin_url"),
        "apollo_id": contact.apollo_id or fields.get("apollo_id"),
        "enriched": is_enriched(contact.raw_data),
        "enrichment_status": None,
        "contact_source": contact.source,
        "research_search_id": contact.people_search_id,
        "research_search_name": None,
        "company_id": None,
        "company_result_id": contact.company_result_id,
    }


def _find_existing(
    db: Session,
    *,
    company_result_id: int,
    apollo_id: str | None,
    email: str | None,
    name: str | None,
) -> ResearchCompanyContact | None:
    if apollo_id:
        row = db.execute(
            select(ResearchCompanyContact).where(
                ResearchCompanyContact.company_result_id == company_result_id,
                ResearchCompanyContact.apollo_id == apollo_id,
            )
        ).scalar_one_or_none()
        if row:
            return row
    if email:
        row = db.execute(
            select(ResearchCompanyContact).where(
                ResearchCompanyContact.company_result_id == company_result_id,
                ResearchCompanyContact.email == email,
            )
        ).scalar_one_or_none()
        if row:
            return row
    if name:
        return db.execute(
            select(ResearchCompanyContact).where(
                ResearchCompanyContact.company_result_id == company_result_id,
                ResearchCompanyContact.name == name,
                ResearchCompanyContact.apollo_id.is_(None),
                or_(
                    ResearchCompanyContact.email.is_(None),
                    ResearchCompanyContact.email == "",
                ),
            )
        ).scalar_one_or_none()
    return None


def upsert_company_contact(
    db: Session,
    *,
    company_search_id: int,
    company_result_id: int,
    person_raw: dict[str, Any],
    people_search_id: int | None = None,
    source: str = "apollo",
) -> ResearchCompanyContact:
    mapped = map_person(person_raw)
    org = mapped.pop("_organization", None) or {}
    fields = _flatten_person(person_raw)
    apollo_id = (mapped.get("apollo_id") or person_raw.get("id") or "").strip() or None
    name = fields.get("name") or person_raw.get("name")
    email = fields.get("email")
    existing = _find_existing(
        db,
        company_result_id=company_result_id,
        apollo_id=apollo_id,
        email=email,
        name=name,
    )
    payload = {
        "company_search_id": company_search_id,
        "company_result_id": company_result_id,
        "people_search_id": people_search_id,
        "apollo_id": apollo_id,
        "name": name,
        "title": fields.get("title"),
        "email": email,
        "phone": fields.get("phone"),
        "seniority": fields.get("seniority"),
        "linkedin_url": fields.get("linkedin_url"),
        "source": source,
        "raw_data": person_raw,
    }
    if existing:
        for key, value in payload.items():
            if value not in (None, ""):
                setattr(existing, key, value)
        db.flush()
        return existing

    row = ResearchCompanyContact(**payload)
    db.add(row)
    db.flush()
    return row


def resolve_company_results_for_person(
    db: Session,
    *,
    parent_search: ResearchSearch,
    company_result: ResearchResult | None,
    person_raw: dict[str, Any],
    people_search: ResearchSearch,
) -> list[ResearchResult]:
    if company_result is not None:
        return [company_result]

    criteria = people_search.criteria or {}
    source_result_id = criteria.get("_source_company_result_id")
    if source_result_id is not None:
        try:
            row = db.get(ResearchResult, int(source_result_id))
            if row and row.search_id == parent_search.id:
                return [row]
        except (TypeError, ValueError):
            pass

    domain = normalize_domain(person_raw.get("_research_employer_domain")) or employer_domain_from_person(
        person_raw
    )
    if not domain:
        return []

    rows = (
        db.execute(
            select(ResearchResult).where(
                ResearchResult.search_id == parent_search.id,
                ResearchResult.entity_type == "company",
            )
        )
        .scalars()
        .all()
    )
    return [row for row in rows if domain_from_result(row) == domain]


def sync_person_result_to_vault(
    db: Session,
    *,
    parent_search: ResearchSearch,
    people_search: ResearchSearch,
    person_result: ResearchResult,
    company_result: ResearchResult | None = None,
) -> None:
    person_raw = person_result.raw_data or {}
    company_domain = domain_from_result(company_result) if company_result else None
    if company_result and company_domain:
        if not _person_belongs_to_company(
            person_raw,
            company_domain=company_domain,
            company_result_id=company_result.id,
            people_search=people_search,
        ):
            return
        upsert_company_contact(
            db,
            company_search_id=parent_search.id,
            company_result_id=company_result.id,
            person_raw=person_raw,
            people_search_id=people_search.id,
            source=(person_raw.get("_research_source") or "apollo"),
        )
        return

    for target in resolve_company_results_for_person(
        db,
        parent_search=parent_search,
        company_result=company_result,
        person_raw=person_raw,
        people_search=people_search,
    ):
        company_domain = domain_from_result(target)
        if not company_domain:
            continue
        if not _person_belongs_to_company(
            person_raw,
            company_domain=company_domain,
            company_result_id=target.id,
            people_search=people_search,
        ):
            continue
        upsert_company_contact(
            db,
            company_search_id=parent_search.id,
            company_result_id=target.id,
            person_raw=person_raw,
            people_search_id=people_search.id,
            source=(person_raw.get("_research_source") or "apollo"),
        )


def sync_people_search_to_vault(
    db: Session,
    *,
    parent_search: ResearchSearch,
    people_search: ResearchSearch,
    company_result: ResearchResult | None = None,
) -> int:
    results = (
        db.execute(
            select(ResearchResult).where(
                ResearchResult.search_id == people_search.id,
                ResearchResult.entity_type == "person",
            )
        )
        .scalars()
        .all()
    )
    for result in results:
        sync_person_result_to_vault(
            db,
            parent_search=parent_search,
            people_search=people_search,
            person_result=result,
            company_result=company_result,
        )
    db.commit()
    return len(results)


def backfill_company_contacts_from_searches(
    db: Session,
    *,
    parent_search: ResearchSearch,
    company_result: ResearchResult,
) -> None:
    """One-time style backfill from existing people recordsets into the vault."""
    domain = domain_from_result(company_result)
    if not domain:
        return

    existing = db.scalar(
        select(ResearchCompanyContact.id)
        .where(ResearchCompanyContact.company_result_id == company_result.id)
        .limit(1)
    )
    if existing:
        return

    people_searches = (
        db.execute(
            select(ResearchSearch).where(
                ResearchSearch.query_type == "people",
                or_(
                    ResearchSearch.criteria["_source_search_id"].astext == str(parent_search.id),
                    ResearchSearch.criteria["_source_company_result_id"].astext == str(company_result.id),
                    ResearchSearch.criteria["_source_company_domain"].astext == domain,
                ),
            )
        )
        .scalars()
        .all()
    )
    for people_search in people_searches:
        sync_people_search_to_vault(
            db,
            parent_search=parent_search,
            people_search=people_search,
            company_result=company_result,
        )


def list_vault_contacts_for_company(
    db: Session,
    *,
    parent_search: ResearchSearch,
    company_result: ResearchResult,
) -> list[dict[str, Any]]:
    backfill_company_contacts_from_searches(
        db, parent_search=parent_search, company_result=company_result
    )
    rows = (
        db.execute(
            select(ResearchCompanyContact)
            .where(
                ResearchCompanyContact.company_search_id == parent_search.id,
                ResearchCompanyContact.company_result_id == company_result.id,
            )
            .order_by(ResearchCompanyContact.updated_at.desc())
        )
        .scalars()
        .all()
    )
    people_search_names: dict[int, str] = {}
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for contact in rows:
        item = _contact_row(contact)
        if contact.people_search_id:
            if contact.people_search_id not in people_search_names:
                search = db.get(ResearchSearch, contact.people_search_id)
                people_search_names[contact.people_search_id] = search.name if search else ""
            item["research_search_name"] = people_search_names.get(contact.people_search_id)
        key = _dedupe_key(
            apollo_id=item.get("apollo_id"),
            email=item.get("email"),
            name=item.get("name"),
        )
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        items.append(item)
    return items


def require_company_result(
    db: Session,
    *,
    parent_search: ResearchSearch,
    company_result_id: int,
) -> ResearchResult:
    result = db.get(ResearchResult, company_result_id)
    if not result or result.search_id != parent_search.id or result.entity_type != "company":
        raise ApolloError("Company not found in this recordset.", status_code=404)
    return result
