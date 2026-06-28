from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
import csv
import io

from app.api.deps import get_admin_user, get_current_user
from app.core.database import get_db
from app.models import Company, Contact, EnrichmentLog, User
from app.schemas.contact import (
    BulkDeleteRequest,
    BulkDeleteResult,
    BulkEnrichRequest,
    BulkEnrichResult,
    BulkEnrichFilteredResult,
    ContactCompanyOption,
    ContactCreate,
    ContactEnrichJobOut,
    ContactEnrichJobStart,
    ContactEnrichJobStartResult,
    ContactEnrichJobFilters,
    ContactTitleAiJobOut,
    ContactTitleAiJobStart,
    ContactTitleAiJobStartResult,
    ContactFilterOptions,
    ContactImportResult,
    ContactList,
    ContactOut,
    ContactUpdate,
    WaterfallStatusOut,
)
from app.services.apollo_webhook import public_base_url_configured, waterfall_enrichment_enabled
from app.services.contact_enrich import (
    enrich_contact_apollo,
    enrich_contact_auto,
    enrich_contact_prospeo,
    store_apollo_person_profile,
)
from app.services.apollo_mapper import map_person
from app.services.apollo_service import ApolloError
from app.services.company_domains import add_domain, email_domain
from app.services import contact_enrich_jobs, contact_title_jobs
from app.services.contact_title_ai import ensure_groq_title_ai_enabled, normalize_contact_title_ai
from app.services.import_service import (
    ImportParseError,
    contact_canonical_field,
    extract_contact_row,
    parse_contact_spreadsheet,
)
from app.services.settings_service import (
    build_client,
    build_prospeo_client,
    get_or_create_prospeo_settings,
    get_or_create_settings,
    is_configured,
    prospeo_is_configured,
)

MAX_IMPORT_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_EXPORT_ROWS = 10_000
MAX_BULK_ENRICH = 50
TITLE_FILTER_NONE = "__no_title__"
UNENRICHED_CONTACT_STATUSES = ("none", "failed")
WATERFALL_ENQUEUED_ENDPOINT = "/waterfall/enqueued"
WATERFALL_WEBHOOK_ENDPOINT = "/webhooks/apollo/waterfall"


def _contact_has_no_title():
    return or_(Contact.title.is_(None), func.trim(Contact.title) == "")


def _contact_has_title():
    return and_(Contact.title.isnot(None), func.trim(Contact.title) != "")


def _contact_missing_title_ai():
    return or_(Contact.title_ai.is_(None), func.trim(Contact.title_ai) == "")


router = APIRouter(prefix="/contacts", tags=["contacts"])


def _apply_contact_filters(
    stmt,
    *,
    search: str | None = None,
    company_id: int | None = None,
    source: str | None = None,
    enrichment_status: str | None = None,
    country: str | None = None,
    city: str | None = None,
    seniority: str | None = None,
    department: str | None = None,
    title: str | None = None,
    titles: list[str] | None = None,
    tier: str | None = None,
):
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Contact.full_name).like(like),
                func.lower(Contact.first_name).like(like),
                func.lower(Contact.last_name).like(like),
                func.lower(Contact.title).like(like),
                func.lower(Contact.title_ai).like(like),
                func.lower(Contact.email).like(like),
            )
        )
    if company_id:
        stmt = stmt.where(Contact.company_id == company_id)
    if source:
        stmt = stmt.where(Contact.source == source)
    if enrichment_status:
        stmt = stmt.where(Contact.enrichment_status == enrichment_status)
    if country:
        stmt = stmt.where(func.lower(Contact.country) == country.lower())
    if city:
        stmt = stmt.where(func.lower(Contact.city) == city.lower())
    if seniority:
        stmt = stmt.where(func.lower(Contact.seniority) == seniority.lower())
    if department:
        stmt = stmt.where(func.lower(Contact.department) == department.lower())
    title_values = [t.strip() for t in (titles or []) if t and t.strip()]
    if not title_values and title:
        title_values = [title.strip()]
    include_no_title = any(t.lower() == TITLE_FILTER_NONE.lower() for t in title_values)
    title_values = [t for t in title_values if t.lower() != TITLE_FILTER_NONE.lower()]
    title_clauses = []
    if title_values:
        lowered = [t.lower() for t in title_values]
        title_clauses.append(func.lower(Contact.title).in_(lowered))
    if include_no_title:
        title_clauses.append(_contact_has_no_title())
    if title_clauses:
        stmt = stmt.where(or_(*title_clauses))
    if tier:
        stmt = stmt.join(Company, Contact.company_id == Company.id).where(
            func.lower(Company.tier) == tier.lower()
        )
    return stmt


def _unenriched_contacts_stmt(
    *,
    search: str | None = None,
    company_id: int | None = None,
    source: str | None = None,
    enrichment_status: str | None = None,
    country: str | None = None,
    city: str | None = None,
    seniority: str | None = None,
    department: str | None = None,
    title: str | None = None,
    titles: list[str] | None = None,
    tier: str | None = None,
):
    stmt = _apply_contact_filters(
        select(Contact),
        search=search,
        company_id=company_id,
        source=source,
        enrichment_status=enrichment_status,
        country=country,
        city=city,
        seniority=seniority,
        department=department,
        title=title,
        titles=titles,
        tier=tier,
    )
    if enrichment_status:
        if enrichment_status in {"enriched", "pending"}:
            return stmt.where(Contact.id == -1)
        return stmt
    return stmt.where(Contact.enrichment_status.in_(UNENRICHED_CONTACT_STATUSES))


def _run_bulk_enrich(db: Session, contacts: list[Contact]) -> BulkEnrichResult:
    result = BulkEnrichResult()
    for contact in contacts:
        enrich_result = enrich_contact_auto(db, contact)
        if enrich_result.ok:
            if enrich_result.status == "pending":
                result.pending += 1
            else:
                result.enriched += 1
        else:
            result.failed += 1
            label = contact.full_name or contact.email or f"#{contact.id}"
            result.errors.append(f"{label}: {enrich_result.error or 'match failed'}")
    return result


def _resolve_enrich_job_contact_ids(
    db: Session,
    payload: ContactEnrichJobStart,
) -> tuple[list[int], str, dict | None]:
    if payload.ids:
        return list(dict.fromkeys(payload.ids)), "selected", None

    filters = payload.filters or ContactEnrichJobFilters()
    stmt = _unenriched_contacts_stmt(
        search=filters.search,
        company_id=filters.company_id,
        source=filters.source,
        enrichment_status=filters.enrichment_status,
        country=filters.country,
        city=filters.city,
        seniority=filters.seniority,
        department=filters.department,
        title=filters.title,
        titles=filters.titles or None,
        tier=filters.tier,
    )
    contacts = db.scalars(stmt.order_by(Contact.updated_at.asc(), Contact.id.asc())).all()
    contact_ids = [c.id for c in contacts]
    filters_dict = filters.model_dump(exclude_none=True)
    if filters.titles:
        filters_dict["titles"] = filters.titles
    return contact_ids, "unenriched", filters_dict or None


def _job_out(job: contact_enrich_jobs.ContactEnrichJob) -> ContactEnrichJobOut:
    return ContactEnrichJobOut(**job.to_dict())


def _title_job_out(job: contact_title_jobs.ContactTitleAiJob) -> ContactTitleAiJobOut:
    return ContactTitleAiJobOut(**job.to_dict())


def _ensure_groq_title_ai(db: Session) -> None:
    try:
        ensure_groq_title_ai_enabled(db)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _resolve_title_job_contact_ids(
    db: Session,
    payload: ContactTitleAiJobStart,
) -> tuple[list[int], str, dict | None]:
    if payload.ids:
        return list(dict.fromkeys(payload.ids)), "selected", None

    filters = payload.filters or ContactEnrichJobFilters()
    stmt = _apply_contact_filters(
        select(Contact),
        search=filters.search,
        company_id=filters.company_id,
        source=filters.source,
        enrichment_status=filters.enrichment_status,
        country=filters.country,
        city=filters.city,
        seniority=filters.seniority,
        department=filters.department,
        title=filters.title,
        titles=filters.titles or None,
        tier=filters.tier,
    )
    stmt = stmt.where(_contact_has_title())
    if payload.only_missing and not payload.force:
        stmt = stmt.where(_contact_missing_title_ai())
    contacts = db.scalars(stmt.order_by(Contact.updated_at.asc(), Contact.id.asc())).all()
    contact_ids = [c.id for c in contacts]
    filters_dict = filters.model_dump(exclude_none=True)
    if filters.titles:
        filters_dict["titles"] = filters.titles
    return contact_ids, "filtered", filters_dict or None


def _waterfall_contacts_filter():
    return or_(
        Contact.enrichment_status == "pending",
        Contact.apollo_data["waterfall_request"].isnot(None),
        Contact.apollo_data["waterfall_webhook"].isnot(None),
    )


def _waterfall_state(contact: Contact) -> str:
    apollo = contact.apollo_data or {}
    if apollo.get("waterfall_webhook"):
        return "completed"
    if contact.enrichment_status == "pending" or apollo.get("waterfall_request"):
        return "pending"
    return "unknown"


def _waterfall_log_times(db: Session, contact_ids: list[int]) -> dict[int, dict]:
    if not contact_ids:
        return {}
    logs = db.scalars(
        select(EnrichmentLog)
        .where(
            EnrichmentLog.entity_type == "contact",
            EnrichmentLog.entity_id.in_(contact_ids),
            EnrichmentLog.endpoint.in_((WATERFALL_ENQUEUED_ENDPOINT, WATERFALL_WEBHOOK_ENDPOINT)),
        )
        .order_by(EnrichmentLog.created_at.asc())
    ).all()
    times: dict[int, dict] = {}
    for log in logs:
        if log.entity_id is None:
            continue
        entry = times.setdefault(log.entity_id, {"requested_at": None, "completed_at": None, "webhook_updated": None})
        if log.endpoint == WATERFALL_ENQUEUED_ENDPOINT:
            entry["requested_at"] = log.created_at
        elif log.endpoint == WATERFALL_WEBHOOK_ENDPOINT:
            entry["completed_at"] = log.created_at
            payload = log.request_payload or {}
            if "updated" in payload:
                entry["webhook_updated"] = bool(payload.get("updated"))
    return times


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


def _ensure_prospeo_enabled(db: Session) -> None:
    row = get_or_create_prospeo_settings(db)
    if not row.enabled:
        raise HTTPException(
            status_code=400,
            detail="The Prospeo integration is off. Enable it in Settings to enrich.",
        )
    if not prospeo_is_configured(row):
        raise HTTPException(
            status_code=400, detail="No Prospeo API key configured. Add one in Settings."
        )


def _ensure_enrichment_enabled(db: Session) -> None:
    apollo = get_or_create_settings(db)
    prospeo = get_or_create_prospeo_settings(db)
    apollo_on = apollo.enabled and is_configured(apollo)
    prospeo_on = prospeo.enabled and prospeo_is_configured(prospeo)
    if not apollo_on and not prospeo_on:
        raise HTTPException(
            status_code=400,
            detail="No enrichment provider enabled. Configure Apollo or Prospeo in Settings.",
        )


@router.get("", response_model=ContactList)
def list_contacts(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    search: str | None = Query(default=None, description="Search name/title/email"),
    company_id: int | None = None,
    source: str | None = None,
    enrichment_status: str | None = None,
    country: str | None = None,
    city: str | None = None,
    seniority: str | None = None,
    department: str | None = None,
    title: str | None = None,
    titles: list[str] | None = Query(default=None),
    tier: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    stmt = _apply_contact_filters(
        select(Contact),
        search=search,
        company_id=company_id,
        source=source,
        enrichment_status=enrichment_status,
        country=country,
        city=city,
        seniority=seniority,
        department=department,
        title=title,
        titles=titles,
        tier=tier,
    )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(Contact.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    contacts = db.execute(stmt).scalars().all()
    items = [ContactOut.model_validate(c) for c in contacts]
    return ContactList(items=items, total=total, page=page, page_size=page_size)


@router.get("/filter-options", response_model=ContactFilterOptions)
def contact_filter_options(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    def _distinct(column):
        rows = db.execute(
            select(column)
            .where(column.is_not(None), func.trim(column) != "")
            .distinct()
            .order_by(column)
        ).all()
        return [r[0] for r in rows]

    company_rows = db.execute(
        select(Company.id, Company.name)
        .join(Contact, Contact.company_id == Company.id)
        .distinct()
        .order_by(Company.name)
    ).all()

    tier_rows = db.execute(
        select(Company.tier)
        .join(Contact, Contact.company_id == Company.id)
        .where(Company.tier.is_not(None), func.trim(Company.tier) != "")
        .distinct()
        .order_by(Company.tier)
    ).all()

    return ContactFilterOptions(
        countries=_distinct(Contact.country),
        cities=_distinct(Contact.city),
        seniorities=_distinct(Contact.seniority),
        departments=_distinct(Contact.department),
        titles=_distinct(Contact.title),
        tiers=[r[0] for r in tier_rows],
        companies=[ContactCompanyOption(id=r.id, name=r.name) for r in company_rows],
    )


@router.get("/export")
def export_contacts(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    search: str | None = None,
    company_id: int | None = None,
    source: str | None = None,
    enrichment_status: str | None = None,
    country: str | None = None,
    city: str | None = None,
    seniority: str | None = None,
    department: str | None = None,
    title: str | None = None,
    titles: list[str] | None = Query(default=None),
    tier: str | None = None,
):
    """Export filtered contacts as CSV (max 10,000 rows)."""
    stmt = _apply_contact_filters(
        select(Contact),
        search=search,
        company_id=company_id,
        source=source,
        enrichment_status=enrichment_status,
        country=country,
        city=city,
        seniority=seniority,
        department=department,
        title=title,
        titles=titles,
        tier=tier,
    )
    stmt = stmt.order_by(Contact.updated_at.desc()).limit(MAX_EXPORT_ROWS)
    contacts = db.execute(stmt).scalars().all()

    company_ids = {c.company_id for c in contacts if c.company_id}
    companies: dict[int, Company] = {}
    if company_ids:
        rows = db.execute(select(Company).where(Company.id.in_(company_ids))).scalars().all()
        companies = {c.id: c for c in rows}

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(
        [
            "full_name",
            "first_name",
            "last_name",
            "email",
            "title",
            "title_ai",
            "company",
            "phone",
            "linkedin_url",
            "city",
            "country",
            "seniority",
            "department",
            "source",
            "enrichment_status",
        ]
    )
    for c in contacts:
        comp = companies.get(c.company_id) if c.company_id else None
        writer.writerow(
            [
                c.full_name or "",
                c.first_name or "",
                c.last_name or "",
                c.email or "",
                c.title or "",
                c.title_ai or "",
                comp.name if comp else "",
                c.phone or "",
                c.linkedin_url or "",
                c.city or "",
                c.country or "",
                c.seniority or "",
                c.department or "",
                c.source or "",
                c.enrichment_status or "",
            ]
        )

    content = buffer.getvalue()
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="contacts-export.csv"'},
    )


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
    from Apollo-discovered people. Existing contacts (matched by email or name + company)
    are skipped and never overwritten.
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


@router.post("/bulk-enrich", response_model=BulkEnrichResult)
def bulk_enrich_contacts(
    payload: BulkEnrichRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    """Match selected contacts via Apollo/Prospeo (sequential, max 50)."""
    ids = list(dict.fromkeys(payload.ids))
    if not ids:
        return BulkEnrichResult()
    if len(ids) > MAX_BULK_ENRICH:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_BULK_ENRICH} contacts per bulk enrich request.",
        )

    _ensure_enrichment_enabled(db)

    contacts = [db.get(Contact, contact_id) for contact_id in ids]
    result = BulkEnrichResult()
    to_enrich: list[Contact] = []
    for contact_id, contact in zip(ids, contacts):
        if not contact:
            result.skipped += 1
            result.errors.append(f"Contact {contact_id}: not found.")
            continue
        to_enrich.append(contact)

    batch_result = _run_bulk_enrich(db, to_enrich)
    db.commit()
    return batch_result


@router.post("/bulk-enrich-unenriched", response_model=BulkEnrichFilteredResult)
def bulk_enrich_unenriched_contacts(
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
    search: str | None = Query(default=None, description="Search name/title/email"),
    company_id: int | None = None,
    source: str | None = None,
    enrichment_status: str | None = None,
    country: str | None = None,
    city: str | None = None,
    seniority: str | None = None,
    department: str | None = None,
    title: str | None = None,
    titles: list[str] | None = Query(default=None),
    tier: str | None = None,
    limit: int = Query(default=MAX_BULK_ENRICH, ge=0, le=MAX_BULK_ENRICH),
):
    """Match not-yet-enriched contacts matching filters (batch of up to 50).

    Without an enrichment_status filter, targets contacts with status ``none`` or ``failed``.
    Pass ``limit=0`` to return only how many contacts would match.
    """
    _ensure_enrichment_enabled(db)

    base_stmt = _unenriched_contacts_stmt(
        search=search,
        company_id=company_id,
        source=source,
        enrichment_status=enrichment_status,
        country=country,
        city=city,
        seniority=seniority,
        department=department,
        title=title,
        titles=titles,
        tier=tier,
    )
    total_matched = db.scalar(select(func.count()).select_from(base_stmt.subquery())) or 0
    if limit == 0 or total_matched == 0:
        return BulkEnrichFilteredResult(total_matched=total_matched, remaining=total_matched)

    contacts = db.scalars(
        base_stmt.order_by(Contact.updated_at.asc(), Contact.id.asc()).limit(limit)
    ).all()
    batch_result = _run_bulk_enrich(db, contacts)
    db.commit()

    remaining = db.scalar(select(func.count()).select_from(base_stmt.subquery())) or 0
    return BulkEnrichFilteredResult(
        enriched=batch_result.enriched,
        pending=batch_result.pending,
        failed=batch_result.failed,
        skipped=batch_result.skipped,
        errors=batch_result.errors,
        total_matched=total_matched,
        processed=len(contacts),
        remaining=remaining,
    )


@router.post("/enrich/jobs", response_model=ContactEnrichJobStartResult)
def start_contact_enrich_job(
    payload: ContactEnrichJobStart,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    """Plan batches and start background enrichment for selected or filtered contacts."""
    _ensure_enrichment_enabled(db)

    contact_ids, source, filters = _resolve_enrich_job_contact_ids(db, payload)
    if not contact_ids:
        raise HTTPException(status_code=400, detail="No contacts matched for this job.")

    job, started = contact_enrich_jobs.start_job(
        contact_ids,
        source=source,
        filters=filters,
        db=db,
    )
    return ContactEnrichJobStartResult(job=_job_out(job), started=started)


@router.get("/enrich/jobs", response_model=list[ContactEnrichJobOut])
def list_contact_enrich_jobs(_: User = Depends(get_current_user)):
    return [_job_out(job) for job in contact_enrich_jobs.list_jobs()]


@router.get("/enrich/jobs/active", response_model=ContactEnrichJobOut | None)
def get_active_contact_enrich_job(_: User = Depends(get_current_user)):
    job = contact_enrich_jobs.get_active_job()
    return _job_out(job) if job else None


@router.get("/enrich/jobs/{job_id}", response_model=ContactEnrichJobOut)
def get_contact_enrich_job(job_id: str, _: User = Depends(get_current_user)):
    job = contact_enrich_jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return _job_out(job)


@router.get("/waterfall-status", response_model=WaterfallStatusOut)
def get_waterfall_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    limit: int = Query(default=100, ge=1, le=500),
):
    """Overview of Apollo waterfall enrichment: pending vs completed contacts."""
    wf_filter = _waterfall_contacts_filter()
    pending = db.scalar(select(func.count(Contact.id)).where(Contact.enrichment_status == "pending")) or 0
    completed = (
        db.scalar(
            select(func.count(Contact.id)).where(Contact.apollo_data["waterfall_webhook"].isnot(None))
        )
        or 0
    )
    total_triggered = (
        db.scalar(
            select(func.count(Contact.id)).where(Contact.apollo_data["waterfall_request"].isnot(None))
        )
        or 0
    )

    contacts = db.scalars(
        select(Contact)
        .where(wf_filter)
        .options(joinedload(Contact.company))
        .order_by(Contact.updated_at.desc())
        .limit(limit)
    ).unique().all()

    log_times = _waterfall_log_times(db, [c.id for c in contacts])
    items = []
    for contact in contacts:
        apollo = contact.apollo_data or {}
        wf_req = apollo.get("waterfall_request") or {}
        wf_hook = apollo.get("waterfall_webhook") or {}
        times = log_times.get(contact.id, {})
        webhook_updated = times.get("webhook_updated")
        if webhook_updated is None and wf_hook:
            webhook_updated = bool(wf_hook.get("people"))
        requested_at = times.get("requested_at")
        if requested_at is None and wf_req:
            requested_at = contact.updated_at
        items.append(
            {
                "id": contact.id,
                "full_name": contact.full_name,
                "email": contact.email,
                "company_name": contact.company.name if contact.company else None,
                "enrichment_status": contact.enrichment_status,
                "waterfall_status": _waterfall_state(contact),
                "request_id": wf_req.get("request_id") or wf_hook.get("request_id"),
                "requested_at": requested_at,
                "completed_at": times.get("completed_at"),
                "webhook_updated": webhook_updated,
            }
        )

    return WaterfallStatusOut(
        waterfall_enabled=waterfall_enrichment_enabled(),
        webhook_configured=public_base_url_configured(),
        pending=pending,
        completed=completed,
        total_triggered=total_triggered,
        items=items,
    )


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
            detail="This contact has no Apollo person id. Use 'Match via Apollo' on this page, or find people on its company first.",
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

    merged = store_apollo_person_profile(contact, person)
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

    _ensure_enrichment_enabled(db)
    enrich_result = enrich_contact_auto(db, contact)
    if not enrich_result.ok:
        db.commit()
        status = 404 if enrich_result.error and "no matching" in enrich_result.error.lower() else 400
        if enrich_result.error and "PUBLIC_BASE_URL" in enrich_result.error:
            status = 400
        raise HTTPException(status_code=status, detail=enrich_result.error or "Enrichment failed.")

    db.commit()
    db.refresh(contact)
    return ContactOut.model_validate(contact)


@router.post("/{contact_id}/enrich-prospeo", response_model=ContactOut)
def enrich_contact_prospeo_only(
    contact_id: int, db: Session = Depends(get_db), _: User = Depends(get_admin_user)
):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found.")

    _ensure_prospeo_enabled(db)
    enrich_result = enrich_contact_prospeo(db, build_prospeo_client(db), contact)
    if not enrich_result.ok:
        db.commit()
        status = 404 if enrich_result.error and "no matching" in enrich_result.error.lower() else 400
        raise HTTPException(status_code=status, detail=enrich_result.error or "Prospeo enrich failed.")

    db.commit()
    db.refresh(contact)
    return ContactOut.model_validate(contact)


@router.post("/{contact_id}/normalize-title", response_model=ContactOut)
def normalize_contact_title(
    contact_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    contact = db.execute(
        select(Contact).options(joinedload(Contact.company)).where(Contact.id == contact_id)
    ).scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found.")

    _ensure_groq_title_ai(db)
    result = normalize_contact_title_ai(db, contact, force=True)
    if result.skipped and not result.ok:
        raise HTTPException(status_code=400, detail=result.error or "Nothing to normalize.")
    if not result.ok:
        db.commit()
        raise HTTPException(status_code=400, detail=result.error or "Title normalization failed.")

    db.commit()
    db.refresh(contact)
    return ContactOut.model_validate(contact)


@router.post("/title-ai/jobs", response_model=ContactTitleAiJobStartResult)
def start_contact_title_ai_job(
    payload: ContactTitleAiJobStart,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    _ensure_groq_title_ai(db)
    contact_ids, source, filters = _resolve_title_job_contact_ids(db, payload)
    if not contact_ids:
        raise HTTPException(status_code=400, detail="No contacts matched for this job.")

    job, started = contact_title_jobs.start_job(
        contact_ids,
        source=source,
        filters=filters,
        only_missing=payload.only_missing,
        force=payload.force,
        db=db,
    )
    return ContactTitleAiJobStartResult(job=_title_job_out(job), started=started)


@router.get("/title-ai/jobs", response_model=list[ContactTitleAiJobOut])
def list_contact_title_ai_jobs(_: User = Depends(get_current_user)):
    return [_title_job_out(job) for job in contact_title_jobs.list_jobs()]


@router.get("/title-ai/jobs/active", response_model=ContactTitleAiJobOut | None)
def get_active_contact_title_ai_job(_: User = Depends(get_current_user)):
    job = contact_title_jobs.get_active_job()
    return _title_job_out(job) if job else None


@router.get("/title-ai/jobs/{job_id}", response_model=ContactTitleAiJobOut)
def get_contact_title_ai_job(job_id: str, _: User = Depends(get_current_user)):
    job = contact_title_jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return _title_job_out(job)
