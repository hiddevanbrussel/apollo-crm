from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.ai import (
    AiStatus,
    AskRequest,
    AskResponse,
    ResearchCreateFromPlan,
    ResearchPlanOut,
    ResearchPlanRequest,
)
from app.schemas.research import ResearchSearchOut
from app.services import ai_agent_service
from app.services.ai_agent_service import AgentError
from app.services.research_nl_service import ResearchNlError, create_research_from_plan, plan_research
from app.services.settings_service import (
    build_client,
    build_groq_client,
    get_or_create_groq_settings,
    get_or_create_settings,
    groq_is_configured,
    is_configured,
)

router = APIRouter(prefix="/ai", tags=["ai"])


def _ensure_apollo_enabled(db: Session) -> None:
    row = get_or_create_settings(db)
    if not row.enabled:
        raise HTTPException(
            status_code=400,
            detail="The Apollo integration is off. Enable it in Settings to run research.",
        )
    if not is_configured(row):
        raise HTTPException(
            status_code=400,
            detail="No Apollo API key configured. Add one in Settings.",
        )


def _groq_ready(db: Session) -> None:
    row = get_or_create_groq_settings(db)
    if not row.enabled:
        raise HTTPException(
            status_code=400,
            detail="The Groq integration is off. Enable it in Settings to use the assistant.",
        )
    if not groq_is_configured(row):
        raise HTTPException(
            status_code=400, detail="No Groq API key configured. Add one in Settings."
        )


@router.get("/status", response_model=AiStatus)
def ai_status(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    row = get_or_create_groq_settings(db)
    configured = groq_is_configured(row)
    if not configured:
        message = "No Groq API key configured. Add one in Settings → Integrations."
    elif not row.enabled:
        message = "Groq is disabled. Enable it in Settings to use the assistant."
    else:
        message = "Ready."
    return AiStatus(enabled=row.enabled, configured=configured, model=row.model, message=message)


@router.post("/ask", response_model=AskResponse)
def ai_ask(
    payload: AskRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _groq_ready(db)
    client = build_groq_client(db)
    try:
        result = ai_agent_service.ask(client, payload.question)
    except AgentError as exc:
        raise HTTPException(status_code=exc.status_code or 400, detail=exc.message)
    return AskResponse(**result)


@router.post("/research/plan", response_model=ResearchPlanOut)
def ai_research_plan(
    payload: ResearchPlanRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _groq_ready(db)
    client = build_groq_client(db)
    try:
        plan = plan_research(client, payload.prompt, company_source=payload.company_source)
    except ResearchNlError as exc:
        raise HTTPException(status_code=exc.status_code or 400, detail=exc.message)
    return ResearchPlanOut(**plan)


@router.post("/research/create", response_model=ResearchSearchOut)
def ai_research_create(
    payload: ResearchCreateFromPlan,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _groq_ready(db)
    apollo = None
    if payload.query_type == "people" or payload.source == "apollo":
        _ensure_apollo_enabled(db)
        apollo = build_client(db)
    try:
        search = create_research_from_plan(
            db,
            apollo,
            name=payload.name,
            query_type=payload.query_type,
            source=payload.source,
            criteria=payload.criteria,
            companies=[c.model_dump() for c in payload.companies],
            max_records=payload.max_records,
            sort_by=payload.sort_by,
            created_by=user.id,
            summary=payload.summary,
        )
    except ResearchNlError as exc:
        raise HTTPException(status_code=exc.status_code or 400, detail=exc.message)
    return ResearchSearchOut.model_validate(search)
