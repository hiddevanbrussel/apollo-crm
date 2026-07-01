"""Microsoft Entra ID (Azure AD) OAuth2 / OIDC helpers."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from authlib.integrations.httpx_client import OAuth2Client
from jose import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import decrypt_value, encrypt_value, mask_api_key
from app.models import AzureAdSettings, User
from app.models.azure_ad_settings import DEFAULT_AZURE_AUTHORITY

MICROSOFT_JWKS_URI = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
MICROSOFT_ISSUER_PREFIX = "https://login.microsoftonline.com/"
OAUTH_STATE_MINUTES = 10


class AzureAuthError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_decrypted_client_secret(row: AzureAdSettings) -> str | None:
    if not row.client_secret_encrypted:
        return None
    try:
        return decrypt_value(row.client_secret_encrypted)
    except ValueError:
        return None


def get_masked_client_secret(row: AzureAdSettings) -> str | None:
    secret = get_decrypted_client_secret(row)
    return mask_api_key(secret)


def set_client_secret(row: AzureAdSettings, secret: str) -> None:
    row.client_secret_encrypted = encrypt_value(secret)


def is_azure_configured(row: AzureAdSettings) -> bool:
    return bool(row.client_id and row.client_secret_encrypted)


def suggest_redirect_uri() -> str:
    if settings.PUBLIC_BASE_URL:
        return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/api/auth/azure/callback"
    if settings.cors_origins:
        return f"{settings.cors_origins[0].rstrip('/')}/api/auth/azure/callback"
    return "http://localhost:8080/api/auth/azure/callback"


def get_redirect_uri(row: AzureAdSettings) -> str:
    if row.redirect_uri and row.redirect_uri.strip():
        return row.redirect_uri.strip().rstrip("/")
    return suggest_redirect_uri()


def get_frontend_base(row: AzureAdSettings) -> str:
    redirect = get_redirect_uri(row)
    suffix = "/api/auth/azure/callback"
    if redirect.endswith(suffix):
        return redirect[: -len(suffix)]
    if settings.PUBLIC_BASE_URL:
        return settings.PUBLIC_BASE_URL.rstrip("/")
    if settings.cors_origins:
        return settings.cors_origins[0].rstrip("/")
    return "http://localhost:8080"


def get_or_create_azure_settings(db: Session) -> AzureAdSettings:
    row = db.execute(select(AzureAdSettings).limit(1)).scalar_one_or_none()
    if row is None:
        row = AzureAdSettings(
            authority=DEFAULT_AZURE_AUTHORITY,
            allowed_domains=[],
            enabled=False,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def azure_is_active(db: Session) -> bool:
    row = get_or_create_azure_settings(db)
    return row.enabled and is_azure_configured(row)


def normalize_domain(domain: str) -> str:
    return domain.strip().lower().lstrip("@")


def normalize_domains(domains: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for domain in domains:
        normalized = normalize_domain(domain)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return sorted(result)


def get_allowed_domains(db: Session) -> list[str]:
    row = get_or_create_azure_settings(db)
    return normalize_domains(list(row.allowed_domains or []))


def is_email_domain_allowed(email: str, allowed_domains: list[str]) -> bool:
    if not allowed_domains:
        return False
    if "@" not in email:
        return False
    domain = email.rsplit("@", 1)[-1].lower()
    return domain in {normalize_domain(d) for d in allowed_domains}


def create_oauth_state() -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=OAUTH_STATE_MINUTES)
    payload = {
        "purpose": "azure_oauth",
        "nonce": secrets.token_urlsafe(16),
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_oauth_state(state: str) -> bool:
    try:
        payload = jwt.decode(
            state,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except Exception:
        return False
    return payload.get("purpose") == "azure_oauth"


def _get_active_row(db: Session) -> AzureAdSettings:
    row = get_or_create_azure_settings(db)
    if not is_azure_configured(row):
        raise AzureAuthError("Azure AD is not configured.", status_code=503)
    return row


def _oauth_client(db: Session) -> tuple[OAuth2Client, AzureAdSettings]:
    row = _get_active_row(db)
    secret = get_decrypted_client_secret(row)
    if not secret or not row.client_id:
        raise AzureAuthError("Azure AD is not configured.", status_code=503)
    client = OAuth2Client(
        client_id=row.client_id,
        client_secret=secret,
        scope="openid profile email",
        redirect_uri=get_redirect_uri(row),
    )
    return client, row


def build_authorization_url(db: Session, state: str) -> str:
    client, row = _oauth_client(db)
    authorize_endpoint = f"{row.authority.rstrip('/')}/oauth2/v2.0/authorize"
    uri, _ = client.create_authorization_url(
        authorize_endpoint,
        state=state,
        response_mode="query",
    )
    return uri


def exchange_code_for_tokens(db: Session, authorization_response: str) -> dict:
    client, row = _oauth_client(db)
    token_endpoint = f"{row.authority.rstrip('/')}/oauth2/v2.0/token"
    return client.fetch_token(token_endpoint, authorization_response=authorization_response)


def validate_id_token(db: Session, id_token: str) -> dict:
    row = _get_active_row(db)
    response = httpx.get(MICROSOFT_JWKS_URI, timeout=10)
    response.raise_for_status()
    jwks = response.json()
    header = jwt.get_unverified_header(id_token)
    kid = header.get("kid")
    key = next((entry for entry in jwks.get("keys", []) if entry.get("kid") == kid), None)
    if key is None:
        raise AzureAuthError("Unable to validate Microsoft sign-in token.", status_code=401)
    claims = jwt.decode(
        id_token,
        key,
        algorithms=["RS256"],
        audience=row.client_id,
        options={"verify_at_hash": False},
    )
    issuer = claims.get("iss", "")
    if not issuer.startswith(MICROSOFT_ISSUER_PREFIX):
        raise AzureAuthError("Invalid token issuer.", status_code=401)
    return claims


def extract_email(claims: dict) -> str | None:
    for key in ("email", "preferred_username", "upn"):
        value = claims.get(key)
        if isinstance(value, str) and "@" in value:
            return value.strip().lower()
    return None


def extract_name(claims: dict, email: str) -> str:
    name = claims.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    given = claims.get("given_name") or ""
    family = claims.get("family_name") or ""
    combined = f"{given} {family}".strip()
    if combined:
        return combined
    return email.split("@")[0]


def upsert_user_from_claims(db: Session, claims: dict) -> User:
    azure_oid = claims.get("oid")
    if not azure_oid:
        raise AzureAuthError("Azure account id (oid) missing from token.", status_code=401)

    email = extract_email(claims)
    if not email:
        raise AzureAuthError("No email address found in Azure profile.", status_code=401)

    allowed = get_allowed_domains(db)
    if not is_email_domain_allowed(email, allowed):
        raise AzureAuthError(
            f"Sign-in is not allowed for the email domain @{email.rsplit('@', 1)[-1]}.",
            status_code=403,
        )

    tenant_id = claims.get("tid")
    name = extract_name(claims, email)

    user = db.execute(select(User).where(User.azure_oid == azure_oid)).scalar_one_or_none()
    if user is None:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()

    if user is None:
        user = User(
            name=name,
            email=email,
            password_hash=None,
            auth_provider="azure",
            azure_oid=azure_oid,
            azure_tenant_id=tenant_id,
            role="user",
        )
        db.add(user)
    else:
        user.name = name
        user.email = email
        user.azure_oid = azure_oid
        user.azure_tenant_id = tenant_id
        if not user.auth_provider or user.auth_provider == "local":
            user.auth_provider = "azure"

    db.commit()
    db.refresh(user)
    return user


def build_frontend_callback_url(db: Session, access_token: str, error: str | None = None) -> str:
    row = get_or_create_azure_settings(db)
    base = f"{get_frontend_base(row)}/login/azure-callback"
    if error:
        return f"{base}?{urlencode({'error': error})}"
    return f"{base}?{urlencode({'token': access_token})}"
