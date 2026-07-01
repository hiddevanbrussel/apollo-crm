"""Manual contact recordsets linked to a company recordset."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ResearchResult, ResearchSearch
from app.services.apollo_service import ApolloError
from app.services.research_company_contacts import (
    require_company_result,
    sync_person_result_to_vault,
)
from app.services.research_service import display_name

DATASET_SOURCE_MANUAL = "manual"


def is_manual_contact_dataset(search: ResearchSearch) -> bool:
    criteria = search.criteria or {}
    return (
        search.query_type == "people"
        and criteria.get("_dataset_source") == DATASET_SOURCE_MANUAL
        and criteria.get("_source_search_id") is not None
    )


def _require_org_parent(search: ResearchSearch) -> ResearchSearch:
    if search.query_type != "organizations":
        raise ApolloError("Contact recordsets can only be created from company recordsets.", status_code=400)
    return search


def _require_manual_contact_dataset(search: ResearchSearch) -> ResearchSearch:
    if not is_manual_contact_dataset(search):
        raise ApolloError("This action is only available on manual contact recordsets.", status_code=400)
    return search


def _parent_search(db: Session, search: ResearchSearch) -> ResearchSearch:
    parent_id = (search.criteria or {}).get("_source_search_id")
    if parent_id is None:
        raise ApolloError("Parent company recordset not found.", status_code=400)
    parent = db.get(ResearchSearch, int(parent_id))
    if not parent or parent.query_type != "organizations":
        raise ApolloError("Parent company recordset not found.", status_code=404)
    return parent


def sync_result_count(db: Session, search: ResearchSearch) -> None:
    search.result_count = (
        db.scalar(
            select(func.count())
            .select_from(ResearchResult)
            .where(ResearchResult.search_id == search.id)
        )
        or 0
    )


def manual_person_raw_data(
    *,
    name: str,
    title: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    seniority: str | None = None,
    linkedin_url: str | None = None,
    company_result_id: int | None = None,
    company_name: str | None = None,
    company_domain: str | None = None,
) -> dict:
    raw = {
        "name": name.strip(),
        "first_name": name.strip().split(" ", 1)[0] if name.strip() else None,
        "title": title,
        "email": email,
        "phone": phone,
        "seniority": seniority,
        "linkedin_url": linkedin_url,
        "_research_source": "manual",
        "_source_company_result_id": company_result_id,
        "_research_employer_domain": company_domain,
    }
    if company_name or company_domain:
        raw["organization"] = {
            "name": company_name,
            "primary_domain": company_domain,
            "domain": company_domain,
        }
    return {k: v for k, v in raw.items() if v not in (None, "")}


def create_manual_contact_dataset(
    db: Session,
    *,
    parent_search: ResearchSearch,
    name: str,
    created_by: int | None,
) -> ResearchSearch:
    _require_org_parent(parent_search)
    search = ResearchSearch(
        name=name.strip(),
        query_type="people",
        criteria={
            "_dataset_source": DATASET_SOURCE_MANUAL,
            "_source_search_id": parent_search.id,
            "_source_search_name": parent_search.name,
        },
        result_count=0,
        total_available=None,
        created_by=created_by,
    )
    db.add(search)
    db.commit()
    db.refresh(search)
    return search


def add_contact_to_contact_dataset(
    db: Session,
    contact_search: ResearchSearch,
    *,
    name: str,
    company_result_id: int,
    title: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    seniority: str | None = None,
    linkedin_url: str | None = None,
) -> ResearchResult:
    _require_manual_contact_dataset(contact_search)
    parent = _parent_search(db, contact_search)
    company = require_company_result(db, parent_search=parent, company_result_id=company_result_id)
    name = name.strip()
    if not name:
        raise ApolloError("Contact name is required.", status_code=400)

    from app.services.research_service import domain_from_result

    company_domain = domain_from_result(company)
    raw = manual_person_raw_data(
        name=name,
        title=title,
        email=email,
        phone=phone,
        seniority=seniority,
        linkedin_url=linkedin_url,
        company_result_id=company.id,
        company_name=company.name,
        company_domain=company_domain,
    )
    result = ResearchResult(
        search_id=contact_search.id,
        entity_type="person",
        apollo_id=None,
        name=display_name("people", raw),
        raw_data=raw,
    )
    db.add(result)
    sync_result_count(db, contact_search)
    db.flush()
    sync_person_result_to_vault(
        db,
        parent_search=parent,
        people_search=contact_search,
        person_result=result,
        company_result=company,
    )
    db.commit()
    db.refresh(result)
    return result


def update_contact_in_contact_dataset(
    db: Session,
    contact_search: ResearchSearch,
    result: ResearchResult,
    *,
    name: str,
    company_result_id: int,
    title: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    seniority: str | None = None,
    linkedin_url: str | None = None,
) -> ResearchResult:
    _require_manual_contact_dataset(contact_search)
    if result.search_id != contact_search.id or result.entity_type != "person":
        raise ApolloError("Contact not found in this recordset.", status_code=404)
    parent = _parent_search(db, contact_search)
    company = require_company_result(db, parent_search=parent, company_result_id=company_result_id)
    name = name.strip()
    if not name:
        raise ApolloError("Contact name is required.", status_code=400)

    from app.services.research_service import domain_from_result

    company_domain = domain_from_result(company)
    raw = manual_person_raw_data(
        name=name,
        title=title,
        email=email,
        phone=phone,
        seniority=seniority,
        linkedin_url=linkedin_url,
        company_result_id=company.id,
        company_name=company.name,
        company_domain=company_domain,
    )
    result.raw_data = raw
    result.name = display_name("people", raw) or name
    result.apollo_id = None
    sync_person_result_to_vault(
        db,
        parent_search=parent,
        people_search=contact_search,
        person_result=result,
        company_result=company,
    )
    db.commit()
    db.refresh(result)
    return result


def delete_contact_from_contact_dataset(
    db: Session,
    contact_search: ResearchSearch,
    result: ResearchResult,
) -> None:
    _require_manual_contact_dataset(contact_search)
    if result.search_id != contact_search.id:
        raise ApolloError("Contact not found in this recordset.", status_code=404)
    db.delete(result)
    sync_result_count(db, contact_search)
    db.commit()
