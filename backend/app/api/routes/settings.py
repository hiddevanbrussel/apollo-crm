from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_admin_user, get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.azure_auth import AzureAdSettingsOut, AzureAdSettingsUpdate
from app.schemas.settings import (
    ApolloSettingsOut,
    ApolloSettingsUpdate,
    ApolloTestResult,
    GroqSettingsOut,
    GroqSettingsUpdate,
    GroqTestResult,
    IntegrationServiceStatus,
    IntegrationsStatusOut,
    LogokitSettingsOut,
    LogokitSettingsUpdate,
    LogokitClientConfig,
    LogokitTestInput,
    LogokitTestResult,
    ProspeoSettingsOut,
    ProspeoSettingsUpdate,
    ProspeoTestResult,
    LushaSettingsOut,
    LushaSettingsUpdate,
    LushaTestResult,
)
from app.services.azure_auth_service import (
    get_masked_client_secret,
    get_or_create_azure_settings,
    is_azure_configured,
    normalize_domains,
    set_client_secret,
    suggest_redirect_uri,
)
from app.services.logokit_service import LogokitService, validate_publishable_token
from app.services.settings_service import (
    build_client,
    build_groq_client,
    build_logokit_client,
    build_lusha_client,
    build_prospeo_client,
    get_decrypted_logokit_token,
    get_masked_api_key,
    get_masked_groq_key,
    get_masked_prospeo_key,
    get_or_create_lusha_settings,
    get_or_create_groq_settings,
    get_or_create_logokit_settings,
    get_or_create_prospeo_settings,
    get_or_create_settings,
    groq_is_configured,
    is_configured,
    logokit_is_configured,
    lusha_is_configured,
    prospeo_is_configured,
    set_api_key,
    set_groq_key,
    set_logokit_token,
    set_lusha_key,
    set_prospeo_key,
    get_masked_lusha_key,
)

router = APIRouter(prefix="/settings", tags=["settings"])


def _to_out(db: Session, row) -> ApolloSettingsOut:
    out = ApolloSettingsOut.model_validate(row)
    out.configured = is_configured(row)
    out.api_key_masked = get_masked_api_key(row)
    return out


@router.get("/status", response_model=IntegrationsStatusOut)
def integrations_status(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Read-only integration flags for UI (no secrets). Available to all signed-in users."""
    apollo = get_or_create_settings(db)
    groq = get_or_create_groq_settings(db)
    logokit = get_or_create_logokit_settings(db)
    prospeo = get_or_create_prospeo_settings(db)
    lusha = get_or_create_lusha_settings(db)
    azure = get_or_create_azure_settings(db)
    return IntegrationsStatusOut(
        apollo=IntegrationServiceStatus(enabled=apollo.enabled, configured=is_configured(apollo)),
        groq=IntegrationServiceStatus(enabled=groq.enabled, configured=groq_is_configured(groq)),
        logokit=IntegrationServiceStatus(
            enabled=logokit.enabled, configured=logokit_is_configured(logokit)
        ),
        prospeo=IntegrationServiceStatus(
            enabled=prospeo.enabled, configured=prospeo_is_configured(prospeo)
        ),
        lusha=IntegrationServiceStatus(
            enabled=lusha.enabled, configured=lusha_is_configured(lusha)
        ),
        azure_ad=IntegrationServiceStatus(
            enabled=azure.enabled, configured=is_azure_configured(azure)
        ),
    )


@router.get("/apollo", response_model=ApolloSettingsOut)
def get_apollo_settings(db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
    row = get_or_create_settings(db)
    return _to_out(db, row)


@router.put("/apollo", response_model=ApolloSettingsOut)
def update_apollo_settings(
    payload: ApolloSettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
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
def test_apollo_settings(db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
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
def get_groq_settings(db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
    return _groq_to_out(get_or_create_groq_settings(db))


@router.put("/groq", response_model=GroqSettingsOut)
def update_groq_settings(
    payload: GroqSettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
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
    if payload.assistant_enabled is not None:
        row.assistant_enabled = payload.assistant_enabled
    db.commit()
    db.refresh(row)
    return _groq_to_out(row)


@router.post("/groq/test", response_model=GroqTestResult)
def test_groq_settings(db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
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
def get_logokit_settings(db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
    return _logokit_to_out(get_or_create_logokit_settings(db))


@router.get("/logokit/client-config", response_model=LogokitClientConfig)
def get_logokit_client_config(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Publishable Logo API config for rendering logos in the UI (all signed-in users)."""
    row = get_or_create_logokit_settings(db)
    token = get_decrypted_logokit_token(row)
    configured = logokit_is_configured(row) and bool(token)
    return LogokitClientConfig(
        enabled=row.enabled and configured,
        configured=configured,
        token=token if row.enabled and configured else None,
        base_url=row.base_url,
    )


@router.put("/logokit", response_model=LogokitSettingsOut)
def update_logokit_settings(
    payload: LogokitSettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    row = get_or_create_logokit_settings(db)
    if payload.clear_token:
        row.api_key_encrypted = None
    elif payload.token:
        token = payload.token.strip()
        token_error = validate_publishable_token(token)
        if token_error:
            raise HTTPException(status_code=400, detail=token_error)
        set_logokit_token(row, token)
    if payload.base_url is not None and payload.base_url.strip():
        row.base_url = payload.base_url.strip().rstrip("/")
    if payload.enabled is not None:
        row.enabled = payload.enabled
    db.commit()
    db.refresh(row)
    return _logokit_to_out(row)


@router.post("/logokit/test", response_model=LogokitTestResult)
def test_logokit_settings(
    payload: LogokitTestInput | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    row = get_or_create_logokit_settings(db)
    stored_token = get_decrypted_logokit_token(row)
    token = (payload.token.strip() if payload and payload.token else None) or stored_token
    if not token:
        if row.api_key_encrypted and not stored_token:
            return LogokitTestResult(
                success=False,
                message=(
                    "Token is stored but could not be decrypted. "
                    "Re-enter your pk_ token and save, or check ENCRYPTION_KEY."
                ),
                status_code=400,
            )
        return LogokitTestResult(success=False, message="No Logokit token configured.", status_code=400)

    client = LogokitService(token=token, base_url=row.base_url)
    ok, message, status_code = client.test_connection()
    return LogokitTestResult(success=ok, message=message, status_code=status_code)


# ---------------------------------------------------------------------------
# Prospeo
# ---------------------------------------------------------------------------
def _prospeo_to_out(row) -> ProspeoSettingsOut:
    out = ProspeoSettingsOut.model_validate(row)
    out.configured = prospeo_is_configured(row)
    out.api_key_masked = get_masked_prospeo_key(row)
    return out


@router.get("/prospeo", response_model=ProspeoSettingsOut)
def get_prospeo_settings(db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
    return _prospeo_to_out(get_or_create_prospeo_settings(db))


@router.put("/prospeo", response_model=ProspeoSettingsOut)
def update_prospeo_settings(
    payload: ProspeoSettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    row = get_or_create_prospeo_settings(db)
    if payload.clear_api_key:
        row.api_key_encrypted = None
    elif payload.api_key:
        set_prospeo_key(row, payload.api_key.strip())
    if payload.base_url is not None and payload.base_url.strip():
        row.base_url = payload.base_url.strip().rstrip("/")
    if payload.enabled is not None:
        row.enabled = payload.enabled
    db.commit()
    db.refresh(row)
    return _prospeo_to_out(row)


@router.post("/prospeo/test", response_model=ProspeoTestResult)
def test_prospeo_settings(db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
    row = get_or_create_prospeo_settings(db)
    if not prospeo_is_configured(row):
        return ProspeoTestResult(success=False, message="No Prospeo API key configured.", status_code=400)
    client = build_prospeo_client(db)
    ok, message, status_code = client.test_connection()
    return ProspeoTestResult(success=ok, message=message, status_code=status_code)


# ---------------------------------------------------------------------------
# Lusha
# ---------------------------------------------------------------------------
def _lusha_to_out(row) -> LushaSettingsOut:
    out = LushaSettingsOut.model_validate(row)
    out.configured = lusha_is_configured(row)
    out.api_key_masked = get_masked_lusha_key(row)
    return out


@router.get("/lusha", response_model=LushaSettingsOut)
def get_lusha_settings(db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
    return _lusha_to_out(get_or_create_lusha_settings(db))


@router.put("/lusha", response_model=LushaSettingsOut)
def update_lusha_settings(
    payload: LushaSettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    row = get_or_create_lusha_settings(db)
    if payload.clear_api_key:
        row.api_key_encrypted = None
    elif payload.api_key:
        set_lusha_key(row, payload.api_key.strip())
    if payload.base_url is not None and payload.base_url.strip():
        row.base_url = payload.base_url.strip().rstrip("/")
    if payload.enabled is not None:
        row.enabled = payload.enabled
    db.commit()
    db.refresh(row)
    return _lusha_to_out(row)


@router.post("/lusha/test", response_model=LushaTestResult)
def test_lusha_settings(db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
    row = get_or_create_lusha_settings(db)
    if not lusha_is_configured(row):
        return LushaTestResult(success=False, message="No Lusha API key configured.", status_code=400)
    client = build_lusha_client(db)
    ok, message, status_code = client.test_connection()
    return LushaTestResult(success=ok, message=message, status_code=status_code)


def _azure_to_out(row) -> AzureAdSettingsOut:
    configured = is_azure_configured(row)
    return AzureAdSettingsOut(
        enabled=row.enabled,
        configured=configured,
        client_id=row.client_id,
        client_secret_masked=get_masked_client_secret(row),
        authority=row.authority,
        redirect_uri=row.redirect_uri,
        suggested_redirect_uri=suggest_redirect_uri(),
        allowed_domains=list(row.allowed_domains or []),
    )


@router.get("/azure-ad", response_model=AzureAdSettingsOut)
def get_azure_ad_settings(db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
    return _azure_to_out(get_or_create_azure_settings(db))


@router.put("/azure-ad", response_model=AzureAdSettingsOut)
def update_azure_ad_settings(
    payload: AzureAdSettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    row = get_or_create_azure_settings(db)
    if payload.enabled is not None:
        if payload.enabled and not is_azure_configured(row):
            raise HTTPException(
                status_code=400,
                detail="Configure client ID and client secret before enabling Microsoft sign-in.",
            )
        row.enabled = payload.enabled
    if payload.clear_client_secret:
        row.client_secret_encrypted = None
    elif payload.client_secret:
        set_client_secret(row, payload.client_secret.strip())
    if payload.client_id is not None:
        row.client_id = payload.client_id.strip() or None
    if payload.authority is not None and payload.authority.strip():
        row.authority = payload.authority.strip().rstrip("/")
    if payload.redirect_uri is not None:
        value = payload.redirect_uri.strip()
        row.redirect_uri = value.rstrip("/") if value else None
    if payload.allowed_domains is not None:
        row.allowed_domains = normalize_domains(payload.allowed_domains)
    db.commit()
    db.refresh(row)
    return _azure_to_out(row)
