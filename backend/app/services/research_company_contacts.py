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
    _apollo_id_for_result,
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
        if is_enriched(existing.raw_data or {}) and not is_enriched(person_raw):
            payload.pop("raw_data", None)
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
    if domain:
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
        matched = [row for row in rows if domain_from_result(row) == domain]
        if matched:
            return matched

    org = person_raw.get("organization") or {}
    org_apollo_id = str(org.get("id") or "").strip() or None
    if org_apollo_id:
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
        matched = [row for row in rows if _apollo_id_for_result(row) == org_apollo_id]
        if matched:
            return matched

    return []


def sync_person_result_to_vault(
    db: Session,
    *,
    parent_search: ResearchSearch,
    people_search: ResearchSearch,
    person_result: ResearchResult,
    company_result: ResearchResult | None = None,
) -> None:
    person_raw = person_result.raw_data or {}

    if company_result is not None:
        targets = [company_result]
    else:
        targets = resolve_company_results_for_person(
            db,
            parent_search=parent_search,
            company_result=company_result,
            person_raw=person_raw,
            people_search=people_search,
        )

    for target in targets:
        company_domain = domain_from_result(target) or ""
        if not _person_belongs_to_company(
            person_raw,
            company_domain=company_domain,
            company_result_id=target.id,
            people_search=people_search,
            company_apollo_id=_apollo_id_for_result(target),
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
    """Backfill vault rows from existing people recordsets linked to this company."""
    domain = domain_from_result(company_result)
    parent_id = parent_search.id
    company_id = company_result.id

    match_clauses = [
        ResearchSearch.criteria["_source_search_id"].astext == str(parent_id),
        ResearchSearch.criteria["_source_search_id"].as_integer() == parent_id,
        ResearchSearch.criteria["_source_company_result_id"].astext == str(company_id),
        ResearchSearch.criteria["_source_company_result_id"].as_integer() == company_id,
    ]
    if domain:
        match_clauses.append(ResearchSearch.criteria["_source_company_domain"].astext == domain)

    people_searches = (
        db.execute(
            select(ResearchSearch).where(
                ResearchSearch.query_type == "people",
                or_(*match_clauses),
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


def sync_vault_from_child_searches(
    db: Session,
    *,
    parent_search: ResearchSearch,
) -> None:
    """Ensure the company vault reflects contacts from all linked people recordsets."""
    parent_id = parent_search.id
    people_searches = (
        db.execute(
            select(ResearchSearch).where(
                ResearchSearch.query_type == "people",
                or_(
                    ResearchSearch.criteria["_source_search_id"].astext == str(parent_id),
                    ResearchSearch.criteria["_source_search_id"].as_integer() == parent_id,
                ),
            )
        )
        .scalars()
        .all()
    )
    for people_search in people_searches:
        company_result = None
        company_result_id = (people_search.criteria or {}).get("_source_company_result_id")
        if company_result_id is not None:
            try:
                row = db.get(ResearchResult, int(company_result_id))
                if row and row.search_id == parent_search.id:
                    company_result = row
            except (TypeError, ValueError):
                company_result = None
        sync_people_search_to_vault(
            db,
            parent_search=parent_search,
            people_search=people_search,
            company_result=company_result,
        )
    db.commit()


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


class _CriteriaSearch:
    """Minimal stand-in for resolve_company_results_for_person."""

    def __init__(self, criteria: dict[str, Any]):
        self.criteria = criteria


def load_vault_contacts_by_company(
    db: Session,
    *,
    company_search_id: int,
) -> dict[int, list[ResearchCompanyContact]]:
    """Vault contacts grouped by company row id."""
    rows = (
        db.execute(
            select(ResearchCompanyContact)
            .where(ResearchCompanyContact.company_search_id == company_search_id)
            .order_by(ResearchCompanyContact.updated_at.desc())
        )
        .scalars()
        .all()
    )
    grouped: dict[int, list[ResearchCompanyContact]] = {}
    for row in rows:
        grouped.setdefault(int(row.company_result_id), []).append(row)
    return grouped


def _normalize_linkedin(url: str | None) -> str | None:
    if not url or not str(url).strip():
        return None
    value = str(url).strip().lower().rstrip("/")
    for prefix in ("https://", "http://", "www."):
        if value.startswith(prefix):
            value = value[len(prefix) :]
    return value.split("?")[0] or None


def _person_identity(
    person_raw: dict[str, Any],
    *,
    apollo_id: str | None = None,
    email: str | None = None,
    name: str | None = None,
    linkedin_url: str | None = None,
) -> tuple[str | None, str | None, str | None, str | None]:
    fields = _flatten_person(person_raw)
    resolved_apollo = (
        str(apollo_id or person_raw.get("id") or fields.get("apollo_id") or "").strip() or None
    )
    resolved_email = (email or fields.get("email") or person_raw.get("email") or "").strip().lower() or None
    resolved_name = (name or fields.get("name") or person_raw.get("name") or "").strip().lower() or None
    resolved_linkedin = _normalize_linkedin(
        linkedin_url or fields.get("linkedin_url") or person_raw.get("linkedin_url")
    )
    return resolved_apollo, resolved_email, resolved_name, resolved_linkedin


def person_raw_matches_person(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Match two person payloads (apollo id, email, linkedin, name)."""
    person_apollo, person_email, person_name, person_linkedin = _person_identity(left)
    contact_apollo, contact_email, contact_name, contact_linkedin = _person_identity(right)

    if person_apollo and contact_apollo and str(person_apollo) == str(contact_apollo):
        return True
    if person_email and contact_email and person_email == contact_email:
        return True
    if person_linkedin and contact_linkedin and person_linkedin == contact_linkedin:
        return True
    if person_name and contact_name and person_name == contact_name:
        if person_apollo and contact_apollo and str(person_apollo) != str(contact_apollo):
            return False
        return True
    return False


def vault_contact_matches_person(
    contact: ResearchCompanyContact,
    person_raw: dict[str, Any],
) -> bool:
    """Match a search hit to an existing vault row (apollo id, email, linkedin, name)."""
    vault_raw = contact.raw_data or {}
    vault_fields = _flatten_person(vault_raw)
    known = {
        **vault_raw,
        "id": contact.apollo_id or vault_raw.get("id") or vault_fields.get("apollo_id"),
        "email": contact.email or vault_fields.get("email"),
        "name": contact.name or vault_fields.get("name"),
        "linkedin_url": contact.linkedin_url or vault_fields.get("linkedin_url"),
    }
    return person_raw_matches_person(person_raw, known)


def find_matching_vault_contact(
    db: Session,
    *,
    parent_search: ResearchSearch,
    person_raw: dict[str, Any],
    vault_by_company: dict[int, list[ResearchCompanyContact]],
    company_result: ResearchResult | None = None,
    people_criteria: dict[str, Any] | None = None,
) -> ResearchCompanyContact | None:
    if not vault_by_company:
        return None

    if company_result is not None:
        targets = [company_result]
    else:
        criteria = people_criteria or {}
        fake_search = _CriteriaSearch(criteria)
        targets = resolve_company_results_for_person(
            db,
            parent_search=parent_search,
            company_result=None,
            person_raw=person_raw,
            people_search=fake_search,  # type: ignore[arg-type]
        )

    for target in targets:
        for contact in vault_by_company.get(target.id, []):
            if vault_contact_matches_person(contact, person_raw):
                return contact

    if company_result is not None:
        return None

    criteria = people_criteria or {}
    fake_search = _CriteriaSearch(criteria)
    for company_result_id, contacts in vault_by_company.items():
        target_row = db.get(ResearchResult, company_result_id)
        if not target_row:
            continue
        company_domain = domain_from_result(target_row) or ""
        for contact in contacts:
            if not vault_contact_matches_person(contact, person_raw):
                continue
            if _person_belongs_to_company(
                person_raw,
                company_domain=company_domain,
                company_result_id=company_result_id,
                people_search=fake_search,  # type: ignore[arg-type]
                company_apollo_id=_apollo_id_for_result(target_row),
            ):
                return contact
    return None


def find_matching_prior_person_raw(
    db: Session,
    *,
    parent_search: ResearchSearch,
    person_raw: dict[str, Any],
    company_result: ResearchResult | None = None,
) -> dict[str, Any] | None:
    """Fallback: match against saved rows in earlier people recordsets."""
    parent_id = parent_search.id
    people_searches = (
        db.execute(
            select(ResearchSearch).where(
                ResearchSearch.query_type == "people",
                or_(
                    ResearchSearch.criteria["_source_search_id"].astext == str(parent_id),
                    ResearchSearch.criteria["_source_search_id"].as_integer() == parent_id,
                ),
            )
            .order_by(ResearchSearch.created_at.desc())
        )
        .scalars()
        .all()
    )

    best: dict[str, Any] | None = None
    for people_search in people_searches:
        criteria = people_search.criteria or {}
        source_result_id = criteria.get("_source_company_result_id")
        if company_result is not None and source_result_id is not None:
            try:
                if int(source_result_id) != company_result.id:
                    continue
            except (TypeError, ValueError):
                pass

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
            prior_raw = result.raw_data or {}
            if not person_raw_matches_person(person_raw, prior_raw):
                continue
            if is_enriched(prior_raw):
                return prior_raw
            if best is None:
                best = prior_raw
    return best


def merge_person_with_known_profile(
    person_raw: dict[str, Any],
    known_raw: dict[str, Any],
    *,
    vault_contact_id: int | None = None,
) -> dict[str, Any]:
    """Use an enriched profile already known for this company in a new recordset row."""
    search_apollo_id = person_raw.get("id")

    if is_enriched(known_raw):
        merged = dict(known_raw)
    else:
        merged = {**dict(known_raw), **{k: v for k, v in person_raw.items() if v not in (None, "")}}

    merged = dict(merged)
    if search_apollo_id:
        merged["id"] = search_apollo_id
    merged["_already_at_company"] = True
    if vault_contact_id is not None:
        merged["_vault_contact_id"] = vault_contact_id
    employer_domain = person_raw.get("_research_employer_domain") or merged.get("_research_employer_domain")
    if employer_domain:
        merged["_research_employer_domain"] = employer_domain
    return merged


def merge_person_with_vault_contact(
    person_raw: dict[str, Any],
    contact: ResearchCompanyContact,
) -> dict[str, Any]:
    """Use enriched vault profile in the new recordset row when already known at the company."""
    return merge_person_with_known_profile(
        person_raw,
        contact.raw_data or {},
        vault_contact_id=contact.id,
    )


def load_vault_apollo_ids_by_company(
    db: Session,
    *,
    company_search_id: int,
) -> dict[int, set[str]]:
    """Apollo person ids already saved on companies in a recordset."""
    rows = db.execute(
        select(ResearchCompanyContact.company_result_id, ResearchCompanyContact.apollo_id).where(
            ResearchCompanyContact.company_search_id == company_search_id,
            ResearchCompanyContact.apollo_id.isnot(None),
            ResearchCompanyContact.apollo_id != "",
        )
    ).all()
    out: dict[int, set[str]] = {}
    for company_result_id, apollo_id in rows:
        aid = str(apollo_id).strip()
        if aid:
            out.setdefault(int(company_result_id), set()).add(aid)
    return out


def person_already_in_company_vault(
    db: Session,
    *,
    parent_search: ResearchSearch,
    person_raw: dict[str, Any],
    vault_apollo_ids_by_company: dict[int, set[str]],
    company_result: ResearchResult | None = None,
    people_criteria: dict[str, Any] | None = None,
) -> bool:
    """True when this Apollo person is already stored on a matching company row."""
    apollo_id = str(person_raw.get("id") or "").strip()
    if not apollo_id:
        return False

    if company_result is not None:
        return apollo_id in vault_apollo_ids_by_company.get(company_result.id, set())

    criteria = people_criteria or {}
    fake_search = _CriteriaSearch(criteria)
    targets = resolve_company_results_for_person(
        db,
        parent_search=parent_search,
        company_result=None,
        person_raw=person_raw,
        people_search=fake_search,  # type: ignore[arg-type]
    )
    for target in targets:
        if apollo_id in vault_apollo_ids_by_company.get(target.id, set()):
            return True
    return False
