from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.models import User
from app.schemas.settings import (
    ApolloSettingsOut,
    ApolloSettingsUpdate,
    ApolloTestResult,
    GroqSettingsOut,
    GroqSettingsUpdate,
    GroqTestResult,
    LogokitSettingsOut,
    LogokitSettingsUpdate,
    LogokitTestResult,
)
from app.services.settings_service import (
    build_client,
    build_groq_client,
    build_logokit_client,
    get_decrypted_logokit_token,
    get_masked_api_key,
    get_masked_groq_key,
    get_or_create_groq_settings,
    get_or_create_logokit_settings,
    get_or_create_settings,
    groq_is_configured,
    is_configured,
    logokit_is_configured,
    set_api_key,
    set_groq_key,
    set_logokit_token,
)

router = APIRouter(prefix="/settings", tags=["settings"])


def _to_out(db: Session, row) -> ApolloSettingsOut:
    out = ApolloSettingsOut.model_validate(row)
    out.configured = is_configured(row)
    out.api_key_masked = get_masked_api_key(row)
    return out


@router.get("/apollo", response_model=ApolloSettingsOut)
def get_apollo_settings(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    row = get_or_create_settings(db)
    return _to_out(db, row)


@router.put("/apollo", response_model=ApolloSettingsOut)
def update_apollo_settings(
    payload: ApolloSettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    row = get_or_create_settings(db)
    if payload.clear_api_key:
        row.api_key_encrypted = None
    elif payload.api_key:
        set_api_key(row, payload.api_key.strip())
    if payload.base_url is not None and payload.base_url.strip():
        row.base_url = payload.base_url.strip().rstrip("/")
    if payload.enabled is not None:
        row.enabled = payload.enabled
    db.commit()
    db.refresh(row)
    return _to_out(db, row)


@router.post("/apollo/test", response_model=ApolloTestResult)
def test_apollo_settings(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    row = get_or_create_settings(db)
    if not is_configured(row):
        return ApolloTestResult(success=False, message="No Apollo API key configured.", status_code=400)
    client = build_client(db)
    ok, message, status_code = client.test_connection()
    return ApolloTestResult(success=ok, message=message, status_code=status_code)


# ---------------------------------------------------------------------------
# Groq
# ---------------------------------------------------------------------------
def _groq_to_out(row) -> GroqSettingsOut:
    out = GroqSettingsOut.model_validate(row)
    out.configured = groq_is_configured(row)
    out.api_key_masked = get_masked_groq_key(row)
    return out


@router.get("/groq", response_model=GroqSettingsOut)
def get_groq_settings(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    return _groq_to_out(get_or_create_groq_settings(db))


@router.put("/groq", response_model=GroqSettingsOut)
def update_groq_settings(
    payload: GroqSettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    row = get_or_create_groq_settings(db)
    if payload.clear_api_key:
        row.api_key_encrypted = None
    elif payload.api_key:
        set_groq_key(row, payload.api_key.strip())
    if payload.base_url is not None and payload.base_url.strip():
        row.base_url = payload.base_url.strip().rstrip("/")
    if payload.model is not None and payload.model.strip():
        row.model = payload.model.strip()
    if payload.enabled is not None:
        row.enabled = payload.enabled
    db.commit()
    db.refresh(row)
    return _groq_to_out(row)


@router.post("/groq/test", response_model=GroqTestResult)
def test_groq_settings(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    row = get_or_create_groq_settings(db)
    if not groq_is_configured(row):
        return GroqTestResult(success=False, message="No Groq API key configured.", status_code=400)
    client = build_groq_client(db)
    ok, message, status_code = client.test_connection()
    return GroqTestResult(success=ok, message=message, status_code=status_code)


# ---------------------------------------------------------------------------
# Logokit
# ---------------------------------------------------------------------------
def _logokit_to_out(row) -> LogokitSettingsOut:
    out = LogokitSettingsOut.model_validate(row)
    out.configured = logokit_is_configured(row)
    out.token = get_decrypted_logokit_token(row)
    return out


@router.get("/logokit", response_model=LogokitSettingsOut)
def get_logokit_settings(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    return _logokit_to_out(get_or_create_logokit_settings(db))


@router.put("/logokit", response_model=LogokitSettingsOut)
def update_logokit_settings(
    payload: LogokitSettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    row = get_or_create_logokit_settings(db)
    if payload.clear_token:
        row.api_key_encrypted = None
    elif payload.token:
        set_logokit_token(row, payload.token.strip())
    if payload.base_url is not None and payload.base_url.strip():
        row.base_url = payload.base_url.strip().rstrip("/")
    if payload.enabled is not None:
        row.enabled = payload.enabled
    db.commit()
    db.refresh(row)
    return _logokit_to_out(row)


@router.post("/logokit/test", response_model=LogokitTestResult)
def test_logokit_settings(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    row = get_or_create_logokit_settings(db)
    if not logokit_is_configured(row):
        return LogokitTestResult(success=False, message="No Logokit token configured.", status_code=400)
    client = build_logokit_client(db)
    ok, message, status_code = client.test_connection()
    return LogokitTestResult(success=ok, message=message, status_code=status_code)
