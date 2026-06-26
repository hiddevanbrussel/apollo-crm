from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_admin_user, get_current_user
from app.core.database import get_db
from app.models import Company, Contact, EnrichmentLog, User
from app.schemas.contact import (
    BulkDeleteRequest,
    BulkDeleteResult,
    ContactCreate,
    ContactImportResult,
    ContactList,
    ContactOut,
    ContactUpdate,
)
from app.services.apollo_mapper import map_person
from app.services.apollo_service import ApolloError
from app.services.company_domains import add_domain, email_domain
from app.services.import_service import (
    ImportParseError,
    contact_canonical_field,
    extract_contact_row,
    parse_contact_spreadsheet,
)
from app.services.settings_service import build_client, get_or_create_settings, is_configured

MAX_IMPORT_BYTES = 5 * 1024 * 1024  # 5 MB

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
    source: str | None = None,
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
    if source:
        stmt = stmt.where(Contact.source == source)
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


def _build_full_name(fields: dict[str, str | None]) -> str | None:
    full = (fields.get("full_name") or "").strip() or None
    if full:
        return full
    parts = [fields.get("first_name"), fields.get("last_name")]
    joined = " ".join(p.strip() for p in parts if p and str(p).strip())
    return joined or None


def _find_company_by_name(db: Session, name: str) -> Company | None:
    return db.execute(
        select(Company).where(func.lower(Company.name) == name.strip().lower())
    ).scalar_one_or_none()


@router.post("/import", response_model=ContactImportResult)
async def import_contacts(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Import contacts from Excel (.xlsx) or CSV and link them to existing companies.

    Required: ``customer_name`` (must match a company imported earlier) plus at least
    one of ``first_name``, ``last_name``, ``full_name`` or ``email``.
    Imported contacts are stored with ``source=import`` so they are distinguishable
    from Apollo-discovered people.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 5 MB).")

    try:
        rows = parse_contact_spreadsheet(file.filename or "", content)
    except ImportParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    created = 0
    updated = 0
    skipped = 0
    skipped_apollo = 0
    domains_added = 0
    errors: list[str] = []
    recognized: set[str] = set()
    extra_cols: set[str] = set()
    seen_in_file: set[str] = set()

    for index, row in enumerate(rows, start=2):
        for header in row:
            field = contact_canonical_field(header)
            (recognized if field else extra_cols).add(header)

        fields, extra = extract_contact_row(row)
        company_name = (fields.get("customer_name") or "").strip()
        email = (fields.get("email") or "").strip() or None
        full_name = _build_full_name(fields)

        if not company_name:
            errors.append(f"Row {index}: customer_name is empty, skipped.")
            continue
        if not full_name and not email:
            errors.append(f"Row {index}: no name or email, skipped.")
            continue

        company = _find_company_by_name(db, company_name)
        if not company:
            errors.append(
                f"Row {index}: company '{company_name}' not found. Import companies first."
            )
            continue

        if email:
            mail_domain = email_domain(email)
            if mail_domain:
                added, clash_msg = add_domain(db, company, mail_domain)
                if added:
                    domains_added += 1
                elif clash_msg:
                    errors.append(f"Row {index}: {clash_msg} (contact imported without adding domain)")

        dedup_key = f"{company.id}|{(email or '').lower()}|{(full_name or '').lower()}"
        if dedup_key in seen_in_file:
            skipped += 1
            continue
        seen_in_file.add(dedup_key)

        existing = None
        if email:
            existing = db.execute(
                select(Contact).where(func.lower(Contact.email) == email.lower())
            ).scalar_one_or_none()
        if not existing and full_name:
            existing = db.execute(
                select(Contact).where(
                    Contact.company_id == company.id,
                    func.lower(Contact.full_name) == full_name.lower(),
                )
            ).scalar_one_or_none()

        contact_fields = {
            k: v for k, v in fields.items() if k != "customer_name" and v not in (None, "")
        }
        if full_name:
            contact_fields["full_name"] = full_name

        if existing:
            if existing.source == "apollo":
                skipped_apollo += 1
                continue
            changed = False
            for key, value in contact_fields.items():
                if key in {"full_name", "first_name", "last_name", "email"} and value:
                    if getattr(existing, key) != value:
                        setattr(existing, key, value)
                        changed = True
                elif value and not getattr(existing, key):
                    setattr(existing, key, value)
                    changed = True
            if existing.company_id != company.id:
                existing.company_id = company.id
                changed = True
            if extra:
                merged = dict(existing.apollo_data or {})
                merged_extra = dict(merged.get("import_extra") or {})
                merged_extra.update(extra)
                if merged_extra != merged.get("import_extra"):
                    merged["import_extra"] = merged_extra
                    existing.apollo_data = merged
                    changed = True
            if existing.source != "import":
                existing.source = "import"
                changed = True
            if changed:
                updated += 1
            else:
                skipped += 1
            continue

        apollo_data: dict = {}
        if extra:
            apollo_data["import_extra"] = extra

        contact = Contact(
            company_id=company.id,
            first_name=contact_fields.get("first_name"),
            last_name=contact_fields.get("last_name"),
            full_name=contact_fields.get("full_name"),
            title=contact_fields.get("title"),
            email=email,
            phone=contact_fields.get("phone"),
            linkedin_url=contact_fields.get("linkedin_url"),
            city=contact_fields.get("city"),
            country=contact_fields.get("country"),
            seniority=contact_fields.get("seniority"),
            department=contact_fields.get("department"),
            source="import",
            enrichment_status="none",
            apollo_data=apollo_data,
        )
        db.add(contact)
        created += 1

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        detail = str(getattr(exc, "orig", exc))
        raise HTTPException(
            status_code=400,
            detail=f"Import failed: duplicate or invalid value in the data ({detail}).",
        ) from exc

    return ContactImportResult(
        total_rows=len(rows),
        created=created,
        updated=updated,
        skipped_duplicates=skipped,
        skipped_apollo=skipped_apollo,
        domains_added=domains_added,
        errors=errors,
        recognized_columns=sorted(recognized),
        extra_columns=sorted(extra_cols),
    )


@router.post("/bulk-delete", response_model=BulkDeleteResult)
def bulk_delete_contacts(
    payload: BulkDeleteRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if not payload.ids:
        return BulkDeleteResult(deleted=0)
    ids = list(dict.fromkeys(payload.ids))
    result = db.execute(delete(Contact).where(Contact.id.in_(ids)))
    db.commit()
    return BulkDeleteResult(deleted=result.rowcount or 0)


@router.delete("/all", response_model=BulkDeleteResult)
def delete_all_contacts(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    result = db.execute(delete(Contact))
    db.commit()
    return BulkDeleteResult(deleted=result.rowcount or 0)


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
