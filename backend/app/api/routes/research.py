import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.models import ResearchResult, ResearchSearch, User
from app.schemas.research import (
    ResearchCreate,
    ResearchDetail,
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
    user: User = Depends(get_current_admin),
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
def list_searches(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    rows = (
        db.execute(select(ResearchSearch).order_by(ResearchSearch.created_at.desc()))
        .scalars()
        .all()
    )
    return ResearchSearchList(items=[ResearchSearchOut.model_validate(r) for r in rows])


@router.get("/searches/{search_id}", response_model=ResearchDetail)
def get_search(search_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    search = db.get(ResearchSearch, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Research search not found.")
    return _detail(db, search)


@router.delete("/searches/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_search(search_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
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
    _: User = Depends(get_current_admin),
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
