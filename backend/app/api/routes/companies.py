from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import bindparam, func, or_, select, text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import Company, Contact, EnrichmentLog, User
from app.schemas.company import (
    BulkDomainItem,
    BulkDomainResult,
    BulkEnrichItem,
    BulkEnrichRequest,
    BulkEnrichResult,
    CompanyCreate,
    CompanyFilterOptions,
    CompanyList,
    CompanyOut,
    CompanyUpdate,
    DomainJobOut,
    DomainLookupResult,
    ImportResult,
)
from app.schemas.contact import ContactOut, FindPeopleResult
from app.services.apollo_mapper import map_organization, map_person
from app.services.apollo_service import ApolloError
from app.services import domain_jobs
from app.services.groq_service import GroqError
from app.services.import_service import ImportParseError, canonical_field, parse_spreadsheet
from app.services.settings_service import (
    build_client,
    build_groq_client,
    get_or_create_groq_settings,
    get_or_create_settings,
    groq_is_configured,
    is_configured,
)


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


def _ensure_groq_enabled(db: Session) -> None:
    row = get_or_create_groq_settings(db)
    if not row.enabled:
        raise HTTPException(
            status_code=400,
            detail="The Groq integration is off. Enable it in Settings to find domains.",
        )
    if not groq_is_configured(row):
        raise HTTPException(
            status_code=400, detail="No Groq API key configured. Add one in Settings."
        )


def _apply_found_domain(db: Session, company: Company, domain: str | None) -> bool:
    """Set a found domain on a company if it's free. Returns True if applied."""
    if not domain:
        return False
    if company.domain and company.domain.lower() == domain.lower():
        return False
    clash = db.execute(
        select(Company).where(func.lower(Company.domain) == domain.lower())
    ).scalar_one_or_none()
    if clash and clash.id != company.id:
        return False
    company.domain = domain
    return True

MAX_IMPORT_BYTES = 5 * 1024 * 1024  # 5 MB

# extra_data keys (case-insensitive) treated as "market segment".
SEGMENT_KEYS = (
    "market segment",
    "market_segment",
    "market segments",
    "market_segments",
    "segment",
    "segments",
    "sector",
)

router = APIRouter(prefix="/companies", tags=["companies"])


def _segment_exists_clause(value: str):
    return text(
        "EXISTS (SELECT 1 FROM jsonb_each_text(companies.extra_data) e "
        "WHERE lower(e.key) IN :seg_keys AND lower(e.value) = :seg_val)"
    ).bindparams(
        bindparam("seg_keys", value=list(SEGMENT_KEYS), expanding=True),
        bindparam("seg_val", value=value.lower()),
    )


def _with_contact_count(db: Session, company: Company) -> CompanyOut:
    count = db.scalar(
        select(func.count(Contact.id)).where(Contact.company_id == company.id)
    )
    data = CompanyOut.model_validate(company)
    data.contact_count = count or 0
    return data


@router.get("", response_model=CompanyList)
def list_companies(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    search: str | None = Query(default=None, description="Search name/domain/industry/country"),
    industry: str | None = None,
    country: str | None = None,
    city: str | None = None,
    market_segment: str | None = None,
    min_employees: int | None = Query(default=None, ge=0),
    max_employees: int | None = Query(default=None, ge=0),
    enrichment_status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    stmt = select(Company)
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Company.name).like(like),
                func.lower(Company.domain).like(like),
                func.lower(Company.industry).like(like),
                func.lower(Company.country).like(like),
            )
        )
    if industry:
        stmt = stmt.where(func.lower(Company.industry) == industry.lower())
    if country:
        stmt = stmt.where(func.lower(Company.country) == country.lower())
    if city:
        stmt = stmt.where(func.lower(Company.city) == city.lower())
    if min_employees is not None:
        stmt = stmt.where(Company.employee_count >= min_employees)
    if max_employees is not None:
        stmt = stmt.where(Company.employee_count <= max_employees)
    if market_segment:
        stmt = stmt.where(_segment_exists_clause(market_segment))
    if enrichment_status:
        stmt = stmt.where(Company.enrichment_status == enrichment_status)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(Company.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    companies = db.execute(stmt).scalars().all()

    items = [_with_contact_count(db, c) for c in companies]
    return CompanyList(items=items, total=total, page=page, page_size=page_size)


@router.get("/filter-options", response_model=CompanyFilterOptions)
def company_filter_options(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Distinct values to populate the Companies page filters."""

    def _distinct(column):
        rows = db.execute(
            select(column)
            .where(column.is_not(None), func.trim(column) != "")
            .distinct()
            .order_by(column)
        ).all()
        return [r[0] for r in rows]

    segment_rows = db.execute(
        text(
            "SELECT DISTINCT e.value AS v FROM companies c, jsonb_each_text(c.extra_data) e "
            "WHERE lower(e.key) IN :seg_keys AND trim(e.value) <> '' ORDER BY v"
        ).bindparams(bindparam("seg_keys", value=list(SEGMENT_KEYS), expanding=True))
    ).all()

    return CompanyFilterOptions(
        industries=_distinct(Company.industry),
        countries=_distinct(Company.country),
        cities=_distinct(Company.city),
        segments=[r.v for r in segment_rows],
    )


@router.post("", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
def create_company(payload: CompanyCreate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    if payload.domain:
        existing = db.execute(
            select(Company).where(func.lower(Company.domain) == payload.domain.lower())
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A company with domain '{payload.domain}' already exists.",
            )
    company = Company(**payload.model_dump())
    db.add(company)
    db.commit()
    db.refresh(company)
    return _with_contact_count(db, company)


def _extract_row(row: dict[str, str]) -> tuple[str | None, str | None, str | None, dict]:
    """Split a raw spreadsheet row into (name, country, domain, extra_data)."""
    name = country = domain = None
    extra: dict[str, str] = {}
    for header, value in row.items():
        field = canonical_field(header)
        if field == "customer_name":
            name = (value or "").strip() or name
        elif field == "country":
            country = (value or "").strip() or country
        elif field == "domain":
            domain = (value or "").strip().lower() or domain
        elif value not in (None, ""):
            extra[header] = value
    return (name, country, domain, extra)


def _enrich_company_inline(db: Session, client, company: Company) -> bool:
    """Enrich one company via Apollo (organization enrich). Returns True on success."""
    if not company.domain:
        return False
    payload = {"domain": company.domain}
    try:
        response = client.enrich_organization(payload)
    except ApolloError:
        company.enrichment_status = "failed"
        db.add(
            EnrichmentLog(
                entity_type="company",
                entity_id=company.id,
                endpoint="/api/v1/organizations/enrich",
                request_payload=payload,
                response_status=None,
            )
        )
        return False
    org = response.get("organization") or {}
    mapped = map_organization(org)
    for key, value in mapped.items():
        if key in {"source", "name"} or value in (None, ""):
            continue
        if key == "domain" and value.lower() != (company.domain or "").lower():
            clash = db.execute(
                select(Company).where(func.lower(Company.domain) == value.lower())
            ).scalar_one_or_none()
            if clash and clash.id != company.id:
                continue
        if hasattr(company, key):
            setattr(company, key, value)
    company.enrichment_status = "enriched"
    db.add(
        EnrichmentLog(
            entity_type="company",
            entity_id=company.id,
            endpoint="/api/v1/organizations/enrich",
            request_payload=payload,
            response_status=200,
        )
    )
    return True


@router.post("/import", response_model=ImportResult)
async def import_companies(
    file: UploadFile = File(...),
    enrich: bool = Form(False),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Import companies from an Excel (.xlsx) or CSV file.

    Recognized columns: ``customer_name`` (required), ``country`` and ``domain``.
    Every other column is preserved in ``extra_data``. Existing companies (matched
    by name or domain) are updated rather than duplicated. When ``enrich`` is true
    and Apollo is enabled, each company with a domain is enriched via Apollo
    (filling industry, employee_count and revenue) — this consumes credits.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 5 MB).")

    try:
        rows = parse_spreadsheet(file.filename or "", content)
    except ImportParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Optionally prepare an Apollo client up front.
    client = None
    if enrich:
        settings_row = get_or_create_settings(db)
        if not settings_row.enabled or not is_configured(settings_row):
            raise HTTPException(
                status_code=400,
                detail="Enrichment requested, but Apollo is off or not configured.",
            )
        client = build_client(db)

    created = 0
    updated = 0
    skipped = 0
    enriched = 0
    errors: list[str] = []
    created_names: list[str] = []
    recognized: set[str] = set()
    extra_cols: set[str] = set()
    seen_in_file: set[str] = set()

    for index, row in enumerate(rows, start=2):  # row 1 is the header
        for header in row:
            field = canonical_field(header)
            (recognized if field else extra_cols).add(header)

        name, country, domain, extra = _extract_row(row)
        if not name:
            errors.append(f"Rij {index}: 'customer_name' is leeg, overgeslagen.")
            continue

        dedup_key = f"{name.lower()}|{domain or ''}"
        if dedup_key in seen_in_file:
            skipped += 1
            continue
        seen_in_file.add(dedup_key)

        # Match an existing company by name first, then by domain.
        existing = db.execute(
            select(Company).where(func.lower(Company.name) == name.lower())
        ).scalar_one_or_none()
        if not existing and domain:
            existing = db.execute(
                select(Company).where(func.lower(Company.domain) == domain)
            ).scalar_one_or_none()

        if existing:
            changed = False
            if domain and not existing.domain:
                clash = db.execute(
                    select(Company).where(func.lower(Company.domain) == domain)
                ).scalar_one_or_none()
                if not clash or clash.id == existing.id:
                    existing.domain = domain
                    changed = True
            if country and not existing.country:
                existing.country = country
                changed = True
            if extra:
                merged = {**(existing.extra_data or {}), **extra}
                if merged != (existing.extra_data or {}):
                    existing.extra_data = merged
                    changed = True
            company = existing
            if changed:
                updated += 1
            else:
                skipped += 1
        else:
            company = Company(
                name=name,
                country=country,
                domain=domain,
                extra_data=extra,
                source="import",
                enrichment_status="none",
            )
            db.add(company)
            created += 1
            created_names.append(name)

        if enrich and company.domain:
            db.flush()  # ensure company.id for logging
            if _enrich_company_inline(db, client, company):
                enriched += 1
            else:
                errors.append(f"Rij {index}: verrijken via Apollo mislukt voor '{name}'.")

    db.commit()
    return ImportResult(
        total_rows=len(rows),
        created=created,
        updated=updated,
        skipped_duplicates=skipped,
        enriched=enriched,
        errors=errors,
        created_names=created_names,
        recognized_columns=sorted(recognized),
        extra_columns=sorted(extra_cols),
    )


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(company_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")
    return _with_contact_count(db, company)


@router.put("/{company_id}", response_model=CompanyOut)
def update_company(
    company_id: int,
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")

    data = payload.model_dump(exclude_unset=True)
    if "domain" in data and data["domain"] and data["domain"].lower() != (company.domain or "").lower():
        clash = db.execute(
            select(Company).where(func.lower(Company.domain) == data["domain"].lower())
        ).scalar_one_or_none()
        if clash and clash.id != company.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Another company already uses domain '{data['domain']}'.",
            )
    for key, value in data.items():
        setattr(company, key, value)
    db.commit()
    db.refresh(company)
    return _with_contact_count(db, company)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")
    db.delete(company)
    db.commit()
    return None


@router.post("/enrich", response_model=BulkEnrichResult)
def bulk_enrich_companies(
    payload: BulkEnrichRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Enrich multiple selected companies via Apollo (organization enrich).

    Companies without a domain are skipped. Consumes Apollo credits per company.
    """
    _ensure_apollo_enabled(db)
    client = build_client(db)

    companies = db.execute(
        select(Company).where(Company.id.in_(payload.company_ids))
    ).scalars().all()

    items: list[BulkEnrichItem] = []
    enriched = failed = skipped = 0
    for company in companies:
        if not company.domain:
            skipped += 1
            items.append(
                BulkEnrichItem(
                    company_id=company.id,
                    name=company.name,
                    status="skipped",
                    reason="No domain to enrich.",
                )
            )
            continue
        if _enrich_company_inline(db, client, company):
            enriched += 1
            items.append(BulkEnrichItem(company_id=company.id, name=company.name, status="enriched"))
        else:
            failed += 1
            items.append(
                BulkEnrichItem(
                    company_id=company.id,
                    name=company.name,
                    status="failed",
                    reason="Apollo enrichment failed.",
                )
            )

    db.commit()
    return BulkEnrichResult(
        requested=len(payload.company_ids),
        enriched=enriched,
        failed=failed,
        skipped=skipped,
        items=items,
    )


@router.post("/{company_id}/enrich", response_model=CompanyOut)
def enrich_company(company_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")
    if not company.domain:
        raise HTTPException(
            status_code=400,
            detail="This company needs a domain to be enriched via Apollo.",
        )

    _ensure_apollo_enabled(db)
    client = build_client(db)
    request_payload = {"domain": company.domain}
    try:
        response = client.enrich_organization(request_payload)
    except ApolloError as exc:
        company.enrichment_status = "failed"
        db.add(
            EnrichmentLog(
                entity_type="company",
                entity_id=company.id,
                endpoint="/api/v1/organizations/enrich",
                request_payload=request_payload,
                response_status=exc.status_code,
            )
        )
        db.commit()
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message)

    org = response.get("organization") or {}
    mapped = map_organization(org)
    for key, value in mapped.items():
        if key in {"source"}:
            continue
        if value not in (None, "") and hasattr(company, key):
            # Don't overwrite domain uniqueness with a clashing value.
            if key == "domain" and value and value.lower() != (company.domain or "").lower():
                clash = db.execute(
                    select(Company).where(func.lower(Company.domain) == value.lower())
                ).scalar_one_or_none()
                if clash and clash.id != company.id:
                    continue
            setattr(company, key, value)
    company.enrichment_status = "enriched"
    db.add(
        EnrichmentLog(
            entity_type="company",
            entity_id=company.id,
            endpoint="/api/v1/organizations/enrich",
            request_payload=request_payload,
            response_status=200,
        )
    )
    db.commit()
    db.refresh(company)
    return _with_contact_count(db, company)


_PERSON_LIGHT_FIELDS = (
    "first_name",
    "title",
    "headline",
    "photo_url",
    "city",
    "country",
    "seniority",
    "department",
)


@router.post("/{company_id}/find-people", response_model=FindPeopleResult)
def find_company_people(
    company_id: int,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Find people working at this company via Apollo (mixed_people/api_search).

    Matches on the company's domain. Discovered people are stored as contacts
    linked to this company, keeping the full Apollo payload in ``apollo_data``.
    Use ``POST /contacts/{id}/complete`` afterwards to fetch a person's full
    profile (email, phone, etc.) one at a time.
    """
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")
    if not company.domain:
        raise HTTPException(
            status_code=400,
            detail="This company needs a domain to find people via Apollo.",
        )

    _ensure_apollo_enabled(db)
    client = build_client(db)
    request_payload = {"domain": company.domain, "page": page, "per_page": per_page}
    try:
        response = client.search_people_by_domains([company.domain], page=page, per_page=per_page)
    except ApolloError as exc:
        db.add(
            EnrichmentLog(
                entity_type="company",
                entity_id=company.id,
                endpoint="/api/v1/mixed_people/api_search",
                request_payload=request_payload,
                response_status=exc.status_code,
            )
        )
        db.commit()
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message)

    people = response.get("people") or response.get("contacts") or []
    created = 0
    updated = 0
    saved: list[Contact] = []
    for person in people:
        apollo_id = person.get("id")
        mapped = map_person(person)
        mapped.pop("_organization", None)

        contact = None
        if apollo_id:
            contact = db.execute(
                select(Contact).where(Contact.apollo_id == apollo_id)
            ).scalar_one_or_none()

        if contact:
            for key in _PERSON_LIGHT_FIELDS:
                value = mapped.get(key)
                if value:
                    setattr(contact, key, value)
            if not contact.full_name and mapped.get("full_name"):
                contact.full_name = mapped["full_name"]
            if contact.company_id is None:
                contact.company_id = company.id
            contact.apollo_data = person
            updated += 1
        else:
            contact = Contact(
                company_id=company.id,
                first_name=mapped.get("first_name"),
                last_name=mapped.get("last_name"),
                full_name=mapped.get("full_name"),
                title=mapped.get("title"),
                headline=mapped.get("headline"),
                photo_url=mapped.get("photo_url"),
                city=mapped.get("city"),
                country=mapped.get("country"),
                seniority=mapped.get("seniority"),
                department=mapped.get("department"),
                apollo_id=apollo_id,
                source="apollo",
                enrichment_status="none",
                apollo_data=person,
            )
            db.add(contact)
            created += 1
        db.flush()
        saved.append(contact)

    db.add(
        EnrichmentLog(
            entity_type="company",
            entity_id=company.id,
            endpoint="/api/v1/mixed_people/api_search",
            request_payload=request_payload,
            response_status=200,
        )
    )
    db.commit()

    pagination = response.get("pagination") or {}
    total = pagination.get("total_entries", len(people))
    items = [ContactOut.model_validate(c) for c in saved]
    return FindPeopleResult(created=created, updated=updated, total=total, contacts=items)


@router.post("/{company_id}/find-domain", response_model=DomainLookupResult)
def find_company_domain(
    company_id: int,
    overwrite: bool = Query(default=False, description="Overwrite an existing domain"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Use Groq (AI web search) to find this company's official website domain."""
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")
    _ensure_groq_enabled(db)

    client = build_groq_client(db)
    try:
        result = client.find_domain(company.name, company.country)
    except GroqError as exc:
        db.add(
            EnrichmentLog(
                entity_type="company",
                entity_id=company.id,
                endpoint="groq/find-domain",
                request_payload={"name": company.name, "country": company.country},
                response_status=exc.status_code,
            )
        )
        db.commit()
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message)

    applied = False
    message = None
    domain = result.get("domain")
    if result.get("found") and domain:
        if company.domain and not overwrite:
            message = "Domain found, but the company already has a domain (not overwritten)."
        else:
            applied = _apply_found_domain(db, company, domain)
            message = "Domain applied." if applied else "Domain already in use by another company."
    else:
        message = result.get("reason") or "No domain found."

    db.add(
        EnrichmentLog(
            entity_type="company",
            entity_id=company.id,
            endpoint="groq/find-domain",
            request_payload={"name": company.name, "country": company.country},
            response_status=200,
        )
    )
    db.commit()
    db.refresh(company)
    return DomainLookupResult(
        found=bool(result.get("found")),
        domain=domain,
        confidence=result.get("confidence"),
        reason=result.get("reason"),
        applied=applied,
        message=message,
        company=_with_contact_count(db, company),
    )


@router.post("/find-domains", response_model=BulkDomainResult)
def bulk_find_domains(
    limit: int | None = Query(
        default=None, ge=1, description="Max companies to process. Omit to process all."
    ),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Find domains via Groq for companies without one. Processes all when no limit."""
    _ensure_groq_enabled(db)
    client = build_groq_client(db)

    query = (
        select(Company)
        .where((Company.domain.is_(None)) | (Company.domain == ""))
        .order_by(Company.updated_at.desc())
    )
    if limit:
        query = query.limit(limit)
    companies = db.execute(query).scalars().all()

    items: list[BulkDomainItem] = []
    found_count = 0
    applied_count = 0
    for company in companies:
        try:
            result = client.find_domain(company.name, company.country)
        except GroqError as exc:
            items.append(
                BulkDomainItem(
                    company_id=company.id,
                    name=company.name,
                    found=False,
                    reason=exc.message,
                )
            )
            continue

        domain = result.get("domain")
        applied = False
        if result.get("found") and domain:
            found_count += 1
            applied = _apply_found_domain(db, company, domain)
            if applied:
                applied_count += 1
        db.add(
            EnrichmentLog(
                entity_type="company",
                entity_id=company.id,
                endpoint="groq/find-domain",
                request_payload={"name": company.name, "country": company.country},
                response_status=200,
            )
        )
        items.append(
            BulkDomainItem(
                company_id=company.id,
                name=company.name,
                found=bool(result.get("found")),
                domain=domain,
                applied=applied,
                reason=result.get("reason"),
            )
        )

    db.commit()
    return BulkDomainResult(
        processed=len(companies),
        found=found_count,
        applied=applied_count,
        items=items,
    )


@router.post("/find-domains/jobs", response_model=DomainJobOut)
def start_find_domains_job(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Start a background job that finds domains for all companies without one."""
    _ensure_groq_enabled(db)
    job, _started = domain_jobs.start_job()
    return DomainJobOut(**job.to_dict())


@router.get("/find-domains/jobs/active", response_model=DomainJobOut | None)
def get_active_find_domains_job(_: User = Depends(get_current_user)):
    job = domain_jobs.get_active_job()
    return DomainJobOut(**job.to_dict()) if job else None


@router.get("/find-domains/jobs/{job_id}", response_model=DomainJobOut)
def get_find_domains_job(job_id: str, _: User = Depends(get_current_user)):
    job = domain_jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return DomainJobOut(**job.to_dict())
