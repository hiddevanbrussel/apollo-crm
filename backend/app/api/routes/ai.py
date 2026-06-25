from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.models import User
from app.schemas.ai import AiStatus, AskRequest, AskResponse
from app.services import ai_agent_service
from app.services.ai_agent_service import AgentError
from app.services.settings_service import (
    build_groq_client,
    get_or_create_groq_settings,
    groq_is_configured,
)

router = APIRouter(prefix="/ai", tags=["ai"])


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
    _: User = Depends(get_current_admin),
):
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

    client = build_groq_client(db)
    try:
        result = ai_agent_service.ask(client, payload.question)
    except AgentError as exc:
        raise HTTPException(status_code=exc.status_code or 400, detail=exc.message)
    return AskResponse(**result)
