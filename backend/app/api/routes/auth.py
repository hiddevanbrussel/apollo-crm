from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.models import User
from app.schemas.auth import Token, UserLogin, UserOut
from app.schemas.azure_auth import AzureAuthPublicConfig
from app.services.azure_auth_service import (
    AzureAuthError,
    azure_is_active,
    build_authorization_url,
    build_frontend_callback_url,
    create_oauth_state,
    exchange_code_for_tokens,
    get_or_create_azure_settings,
    is_azure_configured,
    upsert_user_from_claims,
    validate_id_token,
    verify_oauth_state,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_token(user: User) -> Token:
    access_token = create_access_token(subject=user.id, extra={"role": user.role})
    return Token(access_token=access_token, user=UserOut.model_validate(user))


@router.get("/azure/config", response_model=AzureAuthPublicConfig)
def azure_config(db: Session = Depends(get_db)):
    row = get_or_create_azure_settings(db)
    return AzureAuthPublicConfig(
        enabled=azure_is_active(db),
        configured=is_azure_configured(row),
    )


@router.get("/azure/login")
def azure_login(db: Session = Depends(get_db)):
    if not azure_is_active(db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Microsoft sign-in is not enabled.",
        )
    state = create_oauth_state()
    url = build_authorization_url(db, state)
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.get("/azure/callback")
def azure_callback(request: Request, db: Session = Depends(get_db)):
    if not azure_is_active(db):
        return RedirectResponse(
            url=build_frontend_callback_url(db, "", error="Microsoft sign-in is not enabled."),
            status_code=status.HTTP_302_FOUND,
        )

    params = dict(request.query_params)
    if params.get("error"):
        message = params.get("error_description") or params.get("error") or "Sign-in cancelled."
        return RedirectResponse(
            url=build_frontend_callback_url(db, "", error=message),
            status_code=status.HTTP_302_FOUND,
        )

    state = params.get("state")
    if not state or not verify_oauth_state(state):
        return RedirectResponse(
            url=build_frontend_callback_url(db, "", error="Invalid or expired sign-in session."),
            status_code=status.HTTP_302_FOUND,
        )

    try:
        tokens = exchange_code_for_tokens(db, str(request.url))
        id_token = tokens.get("id_token")
        if not id_token:
            raise AzureAuthError("No id_token received from Microsoft.", status_code=401)
        claims = validate_id_token(db, id_token)
        user = upsert_user_from_claims(db, claims)
        token = _build_token(user)
        return RedirectResponse(
            url=build_frontend_callback_url(db, token.access_token),
            status_code=status.HTTP_302_FOUND,
        )
    except AzureAuthError as exc:
        return RedirectResponse(
            url=build_frontend_callback_url(db, "", error=exc.message),
            status_code=status.HTTP_302_FOUND,
        )
    except Exception:
        return RedirectResponse(
            url=build_frontend_callback_url(db, "", error="Microsoft sign-in failed."),
            status_code=status.HTTP_302_FOUND,
        )


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password."
        )
    return _build_token(user)


@router.post("/login/token", response_model=Token, include_in_schema=False)
def login_oauth(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 password-flow compatible login (used by Swagger UI)."""
    user = db.execute(select(User).where(User.email == form_data.username)).scalar_one_or_none()
    if not user or not user.password_hash or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password."
        )
    return _build_token(user)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
