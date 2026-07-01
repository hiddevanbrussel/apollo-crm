import re

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import ResearchResult, ResearchSearch, User
from app.schemas.research import (
    ResearchCompanyAdd,
    ResearchCompanyContactsOut,
    ResearchCompanyOptionList,
    ResearchContactAdd,
    ResearchContactDatasetCreate,
    ResearchCreate,
    ResearchDatasetCreate,
    ResearchDatasetImportResult,
    ResearchDetail,
    ResearchEnrichRequest,
    ResearchEnrichResult,
    ResearchPeopleFromCompanies,
    ResearchRelatedCompaniesOut,
    ResearchResultDetail,
    ResearchResultsPage,
    ResearchSearchList,
    ResearchSearchOut,
)
from app.services import research_service
from app.services.apollo_service import ApolloError
from app.services.research_contact_dataset import (
    add_contact_to_contact_dataset,
    create_manual_contact_dataset,
    delete_contact_from_contact_dataset,
    is_manual_contact_dataset,
    update_contact_in_contact_dataset,
)
from app.services.research_dataset import (
    add_company_to_dataset,
    create_manual_dataset as create_manual_dataset_record,
    delete_dataset_result,
    import_companies_to_dataset,
    update_company_in_dataset,
)
from app.services.settings_service import build_client, get_or_create_settings, is_configured

router = APIRouter(prefix="/research", tags=["research"])


def _ensure_apollo_enabled(db: Session) -> None:
    row = get_or_create_settings(db)
    if not row.enabled:
        raise HTTPException(
            status_code=400,
            detail="The Apollo integration is off. Enable it in Settings to run research.",
        )
    if not is_configured(row):
        raise HTTPException(
            status_code=400, detail="No Apollo API key configured. Add one in Settings."
        )


def _get_results(db: Session, search_id: int) -> list[ResearchResult]:
    return (
        db.execute(
            select(ResearchResult)
            .where(ResearchResult.search_id == search_id)
            .order_by(ResearchResult.id)
        )
        .scalars()
        .all()
    )


def _detail(db: Session, search: ResearchSearch) -> ResearchDetail:
    results = _get_results(db, search.id)
    cols = research_service.columns_for(search.query_type)
    rows = [research_service.flatten(search.query_type, r.raw_data or {}) for r in results]
    base = ResearchSearchOut.model_validate(search)
    return ResearchDetail(**base.model_dump(), columns=cols, rows=rows)


@router.post("/searches", response_model=ResearchDetail)
def create_search(
    payload: ResearchCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.query_type not in ("people", "organizations"):
        raise HTTPException(status_code=400, detail="query_type must be 'people' or 'organizations'.")
    _ensure_apollo_enabled(db)
    client = build_client(db)
    try:
        search = research_service.run_and_store(
            db,
            client,
            name=payload.name.strip(),
            query_type=payload.query_type,
            criteria=payload.criteria,
            max_records=payload.max_records,
            created_by=user.id,
        )
    except ApolloError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message)
    return _detail(db, search)


@router.post("/datasets", response_model=ResearchDetail)
def create_manual_dataset(
    payload: ResearchDatasetCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create an empty company dataset to fill manually or via import."""
    search = create_manual_dataset_record(
        db,
        name=payload.name.strip(),
        created_by=user.id,
    )
    return _detail(db, search)


@router.post("/searches/{search_id}/contact-datasets", response_model=ResearchDetail)
def create_contact_dataset(
    search_id: int,
    payload: ResearchContactDatasetCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create an empty manual contact recordset linked to a company recordset."""
    parent = db.get(ResearchSearch, search_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Research search not found.")
    try:
        search = create_manual_contact_dataset(
            db,
            parent_search=parent,
            name=payload.name.strip(),
            created_by=user.id,
        )
    except ApolloError as exc:
        raise HTTPException(status_code=exc.status_code or 400, detail=exc.message)
    return _detail(db, search)


@router.get("/searches/{search_id}/company-options", response_model=ResearchCompanyOptionList)
def list_company_options(
    search_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    search = db.get(ResearchSearch, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Research search not found.")
    if search.query_type != "organizations":
        raise HTTPException(status_code=400, detail="Company options are only available for company recordsets.")

    rows = (
        db.execute(
            select(ResearchResult)
            .where(
                ResearchResult.search_id == search_id,
                ResearchResult.entity_type == "company",
            )
            .order_by(ResearchResult.name, ResearchResult.id)
        )
        .scalars()
        .all()
    )
    items = []
    for row in rows:
        fields = research_service.flatten("organizations", row.raw_data or {})
        items.append(
            {
                "id": row.id,
                "name": fields.get("name") or row.name,
                "domain": fields.get("domain"),
            }
        )
    return ResearchCompanyOptionList(items=items)


@router.post("/searches/{search_id}/contacts", response_model=ResearchResultDetail)
def add_contact_to_contact_search(
    search_id: int,
    payload: ResearchContactAdd,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    search = db.get(ResearchSearch, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Research search not found.")
    try:
        result = add_contact_to_contact_dataset(
            db,
            search,
            name=payload.name,
            company_result_id=payload.company_result_id,
            title=payload.title,
            email=payload.email,
            phone=payload.phone,
            seniority=payload.seniority,
            linkedin_url=payload.linkedin_url,
        )
    except ApolloError as exc:
        raise HTTPException(status_code=exc.status_code or 400, detail=exc.message)
    return ResearchResultDetail(**research_service.result_detail(result, search))


@router.post("/searches/{search_id}/results", response_model=ResearchResultDetail)
def add_company_to_search(
    search_id: int,
    payload: ResearchCompanyAdd,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    search = db.get(ResearchSearch, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Research search not found.")
    try:
        result = add_company_to_dataset(
            db,
            search,
            name=payload.name,
            domain=payload.domain,
            website=payload.website,
            industry=payload.industry,
            country=payload.country,
            city=payload.city,
            phone=payload.phone,
            linkedin_url=payload.linkedin_url,
            employee_count=payload.employee_count,
            revenue=payload.revenue,
        )
    except ApolloError as exc:
        raise HTTPException(status_code=exc.status_code or 400, detail=exc.message)
    return ResearchResultDetail(**research_service.result_detail(result, search))


@router.patch("/searches/{search_id}/results/{result_id}", response_model=ResearchResultDetail)
def update_company_in_search(
    search_id: int,
    result_id: int,
    payload: ResearchCompanyAdd,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    search = db.get(ResearchSearch, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Research search not found.")
    result = db.get(ResearchResult, result_id)
    if not result or result.search_id != search_id:
        raise HTTPException(status_code=404, detail="Research result not found.")
    try:
        result = update_company_in_dataset(
            db,
            search,
            result,
            name=payload.name,
            domain=payload.domain,
            website=payload.website,
            industry=payload.industry,
            country=payload.country,
            city=payload.city,
            phone=payload.phone,
            linkedin_url=payload.linkedin_url,
            employee_count=payload.employee_count,
            revenue=payload.revenue,
        )
    except ApolloError as exc:
        raise HTTPException(status_code=exc.status_code or 400, detail=exc.message)
    return ResearchResultDetail(**research_service.result_detail(result, search))


@router.patch("/searches/{search_id}/contacts/{result_id}", response_model=ResearchResultDetail)
def update_contact_in_contact_search(
    search_id: int,
    result_id: int,
    payload: ResearchContactAdd,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    search = db.get(ResearchSearch, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Research search not found.")
    result = db.get(ResearchResult, result_id)
    if not result or result.search_id != search_id:
        raise HTTPException(status_code=404, detail="Research result not found.")
    try:
        result = update_contact_in_contact_dataset(
            db,
            search,
            result,
            name=payload.name,
            company_result_id=payload.company_result_id,
            title=payload.title,
            email=payload.email,
            phone=payload.phone,
            seniority=payload.seniority,
            linkedin_url=payload.linkedin_url,
        )
    except ApolloError as exc:
        raise HTTPException(status_code=exc.status_code or 400, detail=exc.message)
    return ResearchResultDetail(**research_service.result_detail(result, search))


@router.post("/searches/{search_id}/import", response_model=ResearchDatasetImportResult)
async def import_companies_to_search(
    search_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Import companies from CSV/Excel into a manual research dataset."""
    search = db.get(ResearchSearch, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Research search not found.")
    content = await file.read()
    try:
        result = import_companies_to_dataset(
            db,
            search,
            filename=file.filename or "import.csv",
            content=content,
        )
    except ApolloError as exc:
        raise HTTPException(status_code=exc.status_code or 400, detail=exc.message)
    return ResearchDatasetImportResult(**result)


@router.delete("/searches/{search_id}/results/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_search_result(
    search_id: int,
    result_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    search = db.get(ResearchSearch, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Research search not found.")
    result = db.get(ResearchResult, result_id)
    if not result or result.search_id != search_id:
        raise HTTPException(status_code=404, detail="Research result not found.")
    try:
        if is_manual_contact_dataset(search):
            delete_contact_from_contact_dataset(db, search, result)
        else:
            delete_dataset_result(db, search, result)
    except ApolloError as exc:
        raise HTTPException(status_code=exc.status_code or 400, detail=exc.message)
    return None


@router.get("/searches", response_model=ResearchSearchList)
def list_searches(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = (
        db.execute(select(ResearchSearch).order_by(ResearchSearch.created_at.desc()))
        .scalars()
        .all()
    )
    return ResearchSearchList(items=[ResearchSearchOut.model_validate(r) for r in rows])


@router.get("/searches/{search_id}/children", response_model=ResearchSearchList)
def list_search_children(
    search_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Contact recordsets initiated from a company recordset."""
    search = db.get(ResearchSearch, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Research search not found.")
    rows = research_service.list_child_searches(db, search)
    return ResearchSearchList(items=[ResearchSearchOut.model_validate(r) for r in rows])


@router.get("/searches/{search_id}/domains")
def list_search_domains(
    search_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    search = db.get(ResearchSearch, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Research search not found.")
    if search.query_type != "organizations":
        raise HTTPException(status_code=400, detail="Domains are only available for company research.")

    results = _get_results(db, search.id)
    domains: list[str] = []
    seen: set[str] = set()
    for result in results:
        row = research_service.flatten("organizations", result.raw_data or {})
        domain = (row.get("domain") or "").strip().lower()
        if domain and domain not in seen:
            seen.add(domain)
            domains.append(domain)
    return {"domains": domains}


@router.post("/searches/{search_id}/people", response_model=ResearchDetail)
def create_people_from_company_search(
    search_id: int,
    payload: ResearchPeopleFromCompanies,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    parent = db.get(ResearchSearch, search_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Research search not found.")
    if parent.query_type != "organizations":
        raise HTTPException(
            status_code=400,
            detail="Contact search can only be started from a company research dataset.",
        )
    _ensure_apollo_enabled(db)
    client = build_client(db)
    try:
        search = research_service.run_people_for_company_search(
            db,
            client,
            parent_search=parent,
            name=payload.name.strip(),
            criteria=payload.criteria,
            max_records=payload.max_records,
            created_by=user.id,
        )
    except ApolloError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message)
    return _detail(db, search)


def _get_result_or_404(db: Session, search_id: int, result_id: int) -> tuple[ResearchSearch, ResearchResult]:
    search = db.get(ResearchSearch, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Research search not found.")
    result = db.get(ResearchResult, result_id)
    if not result or result.search_id != search_id:
        raise HTTPException(status_code=404, detail="Research result not found.")
    return search, result


@router.get(
    "/searches/{search_id}/results/{result_id}/related",
    response_model=ResearchRelatedCompaniesOut,
)
def list_company_result_related(
    search_id: int,
    result_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    search, result = _get_result_or_404(db, search_id, result_id)
    try:
        payload = research_service.list_related_companies_for_result(
            db, parent_search=search, company_result=result
        )
    except ApolloError as exc:
        raise HTTPException(status_code=exc.status_code or 400, detail=exc.message)
    return ResearchRelatedCompaniesOut(**payload)


@router.get(
    "/searches/{search_id}/results/{result_id}/contacts",
    response_model=ResearchCompanyContactsOut,
)
def list_company_result_contacts(
    search_id: int,
    result_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    search, result = _get_result_or_404(db, search_id, result_id)
    try:
        payload = research_service.list_contacts_for_company_result(
            db, parent_search=search, company_result=result
        )
    except ApolloError as exc:
        raise HTTPException(status_code=exc.status_code or 400, detail=exc.message)
    return ResearchCompanyContactsOut(**payload)


@router.get("/searches/{search_id}/results/{result_id}", response_model=ResearchResultDetail)
def get_search_result(
    search_id: int,
    result_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    search, result = _get_result_or_404(db, search_id, result_id)
    if search.query_type != "organizations":
        raise HTTPException(status_code=400, detail="Company detail is only available for company research.")
    return ResearchResultDetail(**research_service.result_detail(result, search))


@router.post("/searches/{search_id}/results/{result_id}/people", response_model=ResearchDetail)
def create_people_from_company_result(
    search_id: int,
    result_id: int,
    payload: ResearchPeopleFromCompanies,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    search, result = _get_result_or_404(db, search_id, result_id)
    _ensure_apollo_enabled(db)
    client = build_client(db)
    try:
        people_search = research_service.run_people_for_company_result(
            db,
            client,
            parent_search=search,
            company_result=result,
            name=payload.name.strip(),
            criteria=payload.criteria,
            max_records=payload.max_records,
            created_by=user.id,
        )
    except ApolloError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message)
    return _detail(db, people_search)


@router.post("/searches/{search_id}/results/{result_id}/enrich")
def enrich_search_result(
    search_id: int,
    result_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    search = db.get(ResearchSearch, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Research search not found.")
    result = db.get(ResearchResult, result_id)
    if not result or result.search_id != search_id:
        raise HTTPException(status_code=404, detail="Research result not found.")

    _ensure_apollo_enabled(db)
    client = build_client(db)
    try:
        payload = research_service.enrich_result_record(
            client, result, query_type=search.query_type
        )
    except ApolloError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message)

    result.raw_data = payload
    result.apollo_id = payload.get("id") or result.apollo_id
    result.name = research_service.display_name(search.query_type, payload) or result.name
    db.commit()
    db.refresh(result)
    return research_service.result_item(result, search.query_type)


@router.post("/searches/{search_id}/enrich", response_model=ResearchEnrichResult)
def enrich_search_results(
    search_id: int,
    payload: ResearchEnrichRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    search = db.get(ResearchSearch, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Research search not found.")
    if not payload.result_ids and not payload.all_unenriched:
        raise HTTPException(
            status_code=400,
            detail="Provide result_ids or set all_unenriched to true.",
        )

    _ensure_apollo_enabled(db)
    client = build_client(db)
    try:
        return research_service.enrich_results(
            db,
            client,
            search,
            result_ids=payload.result_ids or None,
            all_unenriched=payload.all_unenriched,
        )
    except ApolloError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message)


@router.get("/searches/{search_id}/results", response_model=ResearchResultsPage)
def list_search_results(
    search_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    search = db.get(ResearchSearch, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Research search not found.")

    total = (
        db.execute(
            select(func.count())
            .select_from(ResearchResult)
            .where(ResearchResult.search_id == search_id)
        ).scalar_one()
        or 0
    )
    offset = (page - 1) * page_size
    results = (
        db.execute(
            select(ResearchResult)
            .where(ResearchResult.search_id == search_id)
            .order_by(ResearchResult.id)
            .offset(offset)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    cols = research_service.columns_for(search.query_type)
    items = [research_service.result_item(r, search.query_type) for r in results]
    return ResearchResultsPage(
        search=ResearchSearchOut.model_validate(search),
        columns=cols,
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/searches/{search_id}", response_model=ResearchDetail)
def get_search(search_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    search = db.get(ResearchSearch, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Research search not found.")
    return _detail(db, search)


@router.delete("/searches/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_search(search_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    search = db.get(ResearchSearch, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Research search not found.")
    db.delete(search)
    db.commit()
    return None


@router.get("/searches/{search_id}/export")
def export_search(
    search_id: int,
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    search = db.get(ResearchSearch, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Research search not found.")
    results = _get_results(db, search.id)
    slug = re.sub(r"[^a-z0-9]+", "-", search.name.lower()).strip("-") or "research"

    if format == "xlsx":
        content = research_service.export_xlsx(search, results)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"{slug}.xlsx"
    else:
        content = research_service.export_csv(search, results)
        media = "text/csv"
        filename = f"{slug}.csv"

    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
