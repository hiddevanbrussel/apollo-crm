from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_admin_user, get_current_user
from app.core.database import get_db
from app.models import Company, Contact, EnrichmentLog, User
from app.schemas.contact import ContactCreate, ContactList, ContactOut, ContactUpdate
from app.services.apollo_mapper import map_person
from app.services.apollo_service import ApolloError
from app.services.settings_service import build_client, get_or_create_settings, is_configured

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _ensure_apollo_enabled(db: Session) -> None:
    row = get_or_create_settings(db)
    if not row.enabled:
        raise HTTPException(
            status_code=400,
            detail="The Apollo integration is off. Enable it in Settings to enrich.",
        )
    if not is_configured(row):
        raise HTTPException(
            status_code=400, detail="No Apollo API key configured. Add one in Settings."
        )


@router.get("", response_model=ContactList)
def list_contacts(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    search: str | None = Query(default=None, description="Search name/title/email"),
    company_id: int | None = None,
    enrichment_status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    stmt = select(Contact)
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Contact.full_name).like(like),
                func.lower(Contact.first_name).like(like),
                func.lower(Contact.last_name).like(like),
                func.lower(Contact.title).like(like),
                func.lower(Contact.email).like(like),
            )
        )
    if company_id:
        stmt = stmt.where(Contact.company_id == company_id)
    if enrichment_status:
        stmt = stmt.where(Contact.enrichment_status == enrichment_status)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(Contact.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    contacts = db.execute(stmt).scalars().all()
    items = [ContactOut.model_validate(c) for c in contacts]
    return ContactList(items=items, total=total, page=page, page_size=page_size)


def _check_duplicate(db: Session, email: str | None, apollo_id: str | None, exclude_id: int | None = None):
    if email:
        existing = db.execute(
            select(Contact).where(func.lower(Contact.email) == email.lower())
        ).scalar_one_or_none()
        if existing and existing.id != exclude_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A contact with email '{email}' already exists.",
            )
    if apollo_id:
        existing = db.execute(
            select(Contact).where(Contact.apollo_id == apollo_id)
        ).scalar_one_or_none()
        if existing and existing.id != exclude_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A contact with this Apollo ID already exists.",
            )


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
def create_contact(payload: ContactCreate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    email = str(payload.email) if payload.email else None
    _check_duplicate(db, email, payload.apollo_id)
    if payload.company_id and not db.get(Company, payload.company_id):
        raise HTTPException(status_code=400, detail="Linked company does not exist.")

    data = payload.model_dump()
    data["email"] = email
    if not data.get("full_name"):
        parts = [data.get("first_name"), data.get("last_name")]
        data["full_name"] = " ".join(p for p in parts if p) or None
    contact = Contact(**data)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return ContactOut.model_validate(contact)


@router.get("/{contact_id}", response_model=ContactOut)
def get_contact(contact_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found.")
    return ContactOut.model_validate(contact)


@router.put("/{contact_id}", response_model=ContactOut)
def update_contact(
    contact_id: int,
    payload: ContactUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found.")
    data = payload.model_dump(exclude_unset=True)
    if "email" in data and data["email"]:
        data["email"] = str(data["email"])
        _check_duplicate(db, data["email"], None, exclude_id=contact.id)
    if data.get("company_id") and not db.get(Company, data["company_id"]):
        raise HTTPException(status_code=400, detail="Linked company does not exist.")
    for key, value in data.items():
        setattr(contact, key, value)
    if not contact.full_name:
        contact.full_name = " ".join(p for p in [contact.first_name, contact.last_name] if p) or None
    db.commit()
    db.refresh(contact)
    return ContactOut.model_validate(contact)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(contact_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found.")
    db.delete(contact)
    db.commit()
    return None


@router.post("/{contact_id}/complete", response_model=ContactOut)
def fetch_complete_person(contact_id: int, db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
    """Fetch a person's complete profile via Apollo GET /api/v1/people/{id}.

    Requires the contact to carry an Apollo person id (set by "Find people").
    Fills email, phone, full name, location, etc. and stores the full payload.
    """
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found.")
    if not contact.apollo_id:
        raise HTTPException(
            status_code=400,
            detail="This contact has no Apollo person id. Use 'Find people' on its company first.",
        )

    _ensure_apollo_enabled(db)
    client = build_client(db)
    try:
        response = client.get_person(contact.apollo_id)
    except ApolloError as exc:
        contact.enrichment_status = "failed"
        db.add(
            EnrichmentLog(
                entity_type="contact",
                entity_id=contact.id,
                endpoint=f"/api/v1/people/{contact.apollo_id}",
                request_payload={"id": contact.apollo_id},
                response_status=exc.status_code,
            )
        )
        db.commit()
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message)

    person = response.get("person") or {}
    if not person:
        raise HTTPException(status_code=502, detail="Apollo returned no person details.")

    mapped = map_person(person)
    mapped.pop("_organization", None)
    for key, value in mapped.items():
        if key in {"source", "apollo_id"}:
            continue
        if value in (None, "") or not hasattr(contact, key):
            continue
        if key == "email" and value:
            if contact.email and value.lower() == contact.email.lower():
                continue
            clash = db.execute(
                select(Contact).where(func.lower(Contact.email) == value.lower())
            ).scalar_one_or_none()
            if clash and clash.id != contact.id:
                continue
        setattr(contact, key, value)

    merged = dict(contact.apollo_data or {})
    merged.update(person)
    contact.apollo_data = merged
    contact.enrichment_status = "enriched"
    db.add(
        EnrichmentLog(
            entity_type="contact",
            entity_id=contact.id,
            endpoint=f"/api/v1/people/{contact.apollo_id}",
            request_payload={"id": contact.apollo_id},
            response_status=200,
        )
    )
    db.commit()
    db.refresh(contact)
    return ContactOut.model_validate(contact)


@router.post("/{contact_id}/enrich", response_model=ContactOut)
def enrich_contact(contact_id: int, db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found.")

    company = db.get(Company, contact.company_id) if contact.company_id else None
    request_payload = {
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "name": contact.full_name,
        "email": contact.email,
        "linkedin_url": contact.linkedin_url,
        "organization_name": company.name if company else None,
        "domain": company.domain if company else None,
        "reveal_personal_emails": True,
    }
    _ensure_apollo_enabled(db)
    client = build_client(db)
    try:
        response = client.enrich_person(request_payload)
    except ApolloError as exc:
        contact.enrichment_status = "failed"
        db.add(
            EnrichmentLog(
                entity_type="contact",
                entity_id=contact.id,
                endpoint="/api/v1/people/match",
                request_payload={k: v for k, v in request_payload.items() if k != "email"},
                response_status=exc.status_code,
            )
        )
        db.commit()
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message)

    person = response.get("person") or {}
    mapped = map_person(person)
    org = mapped.pop("_organization", None)
    for key, value in mapped.items():
        if key == "source":
            continue
        if value not in (None, "") and hasattr(contact, key):
            if key == "email" and value and contact.email and value.lower() == contact.email.lower():
                continue
            if key == "apollo_id" and value:
                clash = db.execute(
                    select(Contact).where(Contact.apollo_id == value)
                ).scalar_one_or_none()
                if clash and clash.id != contact.id:
                    continue
            setattr(contact, key, value)

    # Optionally upsert the discovered company and link it.
    if org and not contact.company_id:
        from app.services.apollo_mapper import map_organization

        org_fields = map_organization(org)
        domain = org_fields.get("domain")
        existing_company = None
        if domain:
            existing_company = db.execute(
                select(Company).where(func.lower(Company.domain) == domain.lower())
            ).scalar_one_or_none()
        if not existing_company and org_fields.get("name"):
            existing_company = Company(
                **{k: v for k, v in org_fields.items() if hasattr(Company, k)}
            )
            existing_company.enrichment_status = "enriched"
            db.add(existing_company)
            db.flush()
        if existing_company:
            contact.company_id = existing_company.id

    contact.enrichment_status = "enriched"
    db.add(
        EnrichmentLog(
            entity_type="contact",
            entity_id=contact.id,
            endpoint="/api/v1/people/match",
            request_payload={k: v for k, v in request_payload.items() if k != "email"},
            response_status=200,
        )
    )
    db.commit()
    db.refresh(contact)
    return ContactOut.model_validate(contact)
