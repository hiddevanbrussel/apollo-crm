from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_admin_user, get_current_user
from app.core.database import get_db
from app.models import Company, Contact, EnrichmentLog, SearchHistory, User
from app.schemas.apollo import (
    ApolloStatus,
    BulkPersonEnrichInput,
    OrganizationEnrichInput,
    OrganizationSearchFilters,
    PeopleSearchFilters,
    PersonEnrichInput,
    SaveSelection,
)
from app.services.apollo_mapper import map_organization, map_person
from app.services.apollo_service import ApolloError
from app.services.settings_service import build_client, get_or_create_settings, is_configured

router = APIRouter(prefix="/apollo", tags=["apollo"])


def _log_search(db: Session, query_type: str, payload: dict, count: int, user_id: int) -> None:
    db.add(
        SearchHistory(
            query_type=query_type,
            query_payload=payload,
            result_count=count,
            created_by=user_id,
        )
    )


def _handle_apollo_error(exc: ApolloError):
    raise HTTPException(status_code=exc.status_code or 502, detail=exc.message)


@router.get("/status", response_model=ApolloStatus)
def apollo_status(
    check: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Report Apollo configuration status.

    By default this performs **no** Apollo API call (so it never consumes
    credits). Pass ``?check=true`` to actively ping Apollo and verify the key.
    """
    row = get_or_create_settings(db)
    configured = is_configured(row)
    reachable = None
    message = None

    if not configured:
        message = "No Apollo API key configured."
    elif not row.enabled:
        message = "Apollo integration is disabled."
    elif check:
        client = build_client(db)
        ok, msg, _code = client.test_connection()
        reachable = ok
        message = msg
    else:
        message = "Apollo is enabled. Searches and enrichment run only when you trigger them."

    return ApolloStatus(
        enabled=row.enabled,
        configured=configured,
        base_url=row.base_url,
        reachable=reachable,
        message=message,
    )


def _ensure_enabled(db: Session):
    row = get_or_create_settings(db)
    if not row.enabled:
        raise HTTPException(status_code=400, detail="Apollo integration is disabled. Enable it in Settings.")
    if not is_configured(row):
        raise HTTPException(status_code=400, detail="No Apollo API key configured. Add one in Settings.")


@router.post("/search/people")
def search_people(
    filters: PeopleSearchFilters,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_enabled(db)
    client = build_client(db)
    try:
        response = client.search_people(filters.model_dump(exclude_none=True))
    except ApolloError as exc:
        _handle_apollo_error(exc)

    people = response.get("people") or response.get("contacts") or []
    pagination = response.get("pagination")
    _log_search(db, "people", filters.model_dump(exclude_none=True), len(people), current_user.id)
    db.commit()
    return {"results": people, "pagination": pagination, "total": (pagination or {}).get("total_entries", len(people))}


@router.post("/search/organizations")
def search_organizations(
    filters: OrganizationSearchFilters,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_enabled(db)
    client = build_client(db)
    try:
        response = client.search_organizations(filters.model_dump(exclude_none=True))
    except ApolloError as exc:
        _handle_apollo_error(exc)

    orgs = response.get("organizations") or response.get("accounts") or []
    pagination = response.get("pagination")
    _log_search(db, "organizations", filters.model_dump(exclude_none=True), len(orgs), current_user.id)
    db.commit()
    return {"results": orgs, "pagination": pagination, "total": (pagination or {}).get("total_entries", len(orgs))}


@router.post("/enrich/person")
def enrich_person(
    payload: PersonEnrichInput,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    _ensure_enabled(db)
    data = payload.model_dump(exclude_none=True)
    if data.get("run_waterfall_email") and not data.get("webhook_url"):
        raise HTTPException(
            status_code=400,
            detail="webhook_url is required when run_waterfall_email is enabled.",
        )
    client = build_client(db)
    try:
        response = client.enrich_person(data)
    except ApolloError as exc:
        _handle_apollo_error(exc)
    db.add(
        EnrichmentLog(
            entity_type="person",
            endpoint="/api/v1/people/match",
            request_payload=payload.model_dump(exclude={"email"}, exclude_none=True),
            response_status=200,
        )
    )
    db.commit()
    return response


@router.post("/enrich/people/bulk")
def enrich_people_bulk(
    payload: BulkPersonEnrichInput,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    _ensure_enabled(db)
    client = build_client(db)
    try:
        response = client.enrich_people_bulk(payload.model_dump(exclude_none=True))
    except ApolloError as exc:
        _handle_apollo_error(exc)
    db.add(
        EnrichmentLog(
            entity_type="person_bulk",
            endpoint="/api/v1/people/bulk_match",
            request_payload={"count": len(payload.details)},
            response_status=200,
        )
    )
    db.commit()
    return response


@router.post("/enrich/organization")
def enrich_organization(
    payload: OrganizationEnrichInput,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    _ensure_enabled(db)
    client = build_client(db)
    try:
        response = client.enrich_organization(payload.model_dump(exclude_none=True))
    except ApolloError as exc:
        _handle_apollo_error(exc)
    db.add(
        EnrichmentLog(
            entity_type="organization",
            endpoint="/api/v1/organizations/enrich",
            request_payload=payload.model_dump(exclude_none=True),
            response_status=200,
        )
    )
    db.commit()
    return response


# ---------------------------------------------------------------------------
# Save selected Apollo results into the CRM
# ---------------------------------------------------------------------------
def _upsert_company_from_org(db: Session, org: dict) -> Company | None:
    fields = map_organization(org)
    if not fields.get("name"):
        return None
    apollo_id = fields.get("apollo_id")
    domain = fields.get("domain")

    company = None
    if apollo_id:
        company = db.execute(select(Company).where(Company.apollo_id == apollo_id)).scalar_one_or_none()
    if not company and domain:
        company = db.execute(
            select(Company).where(func.lower(Company.domain) == domain.lower())
        ).scalar_one_or_none()

    valid = {k: v for k, v in fields.items() if hasattr(Company, k) and v not in (None, "")}
    if company:
        for key, value in valid.items():
            if key == "domain" and value and value.lower() != (company.domain or "").lower():
                continue  # avoid unique clashes
            setattr(company, key, value)
    else:
        company = Company(**valid)
        company.enrichment_status = "enriched"
        db.add(company)
        db.flush()
    return company


def _upsert_contact_from_person(db: Session, person: dict) -> Contact | None:
    fields = map_person(person)
    org = fields.pop("_organization", None)
    if not (fields.get("full_name") or fields.get("first_name") or fields.get("email")):
        return None

    apollo_id = fields.get("apollo_id")
    email = fields.get("email")

    contact = None
    if apollo_id:
        contact = db.execute(select(Contact).where(Contact.apollo_id == apollo_id)).scalar_one_or_none()
    if not contact and email:
        contact = db.execute(
            select(Contact).where(func.lower(Contact.email) == email.lower())
        ).scalar_one_or_none()

    company = _upsert_company_from_org(db, org) if org else None

    valid = {k: v for k, v in fields.items() if hasattr(Contact, k) and v not in (None, "")}
    if contact:
        for key, value in valid.items():
            if key == "email" and value and contact.email and value.lower() != contact.email.lower():
                clash = db.execute(
                    select(Contact).where(func.lower(Contact.email) == value.lower())
                ).scalar_one_or_none()
                if clash and clash.id != contact.id:
                    continue
            setattr(contact, key, value)
    else:
        contact = Contact(**valid)
        contact.enrichment_status = "enriched"
        db.add(contact)
    if company:
        contact.company_id = company.id
    db.flush()
    return contact


@router.post("/save/organizations")
def save_organizations(
    payload: SaveSelection,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    saved = 0
    for org in payload.results:
        company = _upsert_company_from_org(db, org)
        if company:
            saved += 1
    db.commit()
    return {"saved": saved, "total": len(payload.results)}


@router.post("/save/people")
def save_people(
    payload: SaveSelection,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    saved = 0
    for person in payload.results:
        contact = _upsert_contact_from_person(db, person)
        if contact:
            saved += 1
    db.commit()
    return {"saved": saved, "total": len(payload.results)}
