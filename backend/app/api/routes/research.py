import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import ResearchResult, ResearchSearch, User
from app.schemas.research import (
    ResearchCreate,
    ResearchDetail,
    ResearchEnrichRequest,
    ResearchEnrichResult,
    ResearchPeopleFromCompanies,
    ResearchResultsPage,
    ResearchSearchList,
    ResearchSearchOut,
)
from app.services import research_service
from app.services.apollo_service import ApolloError
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


@router.get("/searches", response_model=ResearchSearchList)
def list_searches(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = (
        db.execute(select(ResearchSearch).order_by(ResearchSearch.created_at.desc()))
        .scalars()
        .all()
    )
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
