"""Helpers to read/write Apollo settings and build a configured client."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.core.crypto import decrypt_value, encrypt_value, mask_api_key
from app.models import ApolloSettings, GroqSettings, LogokitSettings, LushaSettings, ProspeoSettings
from app.services.prospeo_service import ProspeoService
from app.services.apollo_service import ApolloService
from app.services.groq_service import GroqService
from app.services.logokit_service import LogokitService
from app.services.lusha_service import LushaService


def get_or_create_settings(db: Session) -> ApolloSettings:
    row = db.execute(select(ApolloSettings).limit(1)).scalar_one_or_none()
    if row is None:
        row = ApolloSettings(
            base_url=app_settings.APOLLO_BASE_URL,
            enabled=False,
            api_key_encrypted=None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def get_decrypted_api_key(row: ApolloSettings) -> str | None:
    if not row.api_key_encrypted:
        return None
    try:
        return decrypt_value(row.api_key_encrypted)
    except ValueError:
        return None


def get_masked_api_key(row: ApolloSettings) -> str | None:
    key = get_decrypted_api_key(row)
    return mask_api_key(key)


def set_api_key(row: ApolloSettings, api_key: str) -> None:
    row.api_key_encrypted = encrypt_value(api_key)


def build_client(db: Session) -> ApolloService:
    row = get_or_create_settings(db)
    api_key = get_decrypted_api_key(row)
    return ApolloService(api_key=api_key, base_url=row.base_url)


def is_configured(row: ApolloSettings) -> bool:
    return bool(row.api_key_encrypted)


# ---------------------------------------------------------------------------
# Groq
# ---------------------------------------------------------------------------
def get_or_create_groq_settings(db: Session) -> GroqSettings:
    row = db.execute(select(GroqSettings).limit(1)).scalar_one_or_none()
    if row is None:
        row = GroqSettings(
            base_url="https://api.groq.com",
            model="groq/compound",
            enabled=False,
            assistant_enabled=True,
            api_key_encrypted=None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def get_decrypted_groq_key(row: GroqSettings) -> str | None:
    if not row.api_key_encrypted:
        return None
    try:
        return decrypt_value(row.api_key_encrypted)
    except ValueError:
        return None


def get_masked_groq_key(row: GroqSettings) -> str | None:
    return mask_api_key(get_decrypted_groq_key(row))


def set_groq_key(row: GroqSettings, api_key: str) -> None:
    row.api_key_encrypted = encrypt_value(api_key)


def groq_is_configured(row: GroqSettings) -> bool:
    return bool(row.api_key_encrypted)


def build_groq_client(db: Session) -> GroqService:
    row = get_or_create_groq_settings(db)
    api_key = get_decrypted_groq_key(row)
    return GroqService(api_key=api_key, base_url=row.base_url, model=row.model)


# ---------------------------------------------------------------------------
# Logokit
# ---------------------------------------------------------------------------
def get_or_create_logokit_settings(db: Session) -> LogokitSettings:
    row = db.execute(select(LogokitSettings).limit(1)).scalar_one_or_none()
    if row is None:
        row = LogokitSettings(
            base_url="https://img.logokit.com",
            enabled=False,
            api_key_encrypted=None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def get_decrypted_logokit_token(row: LogokitSettings) -> str | None:
    if not row.api_key_encrypted:
        return None
    try:
        return decrypt_value(row.api_key_encrypted)
    except ValueError:
        return None


def set_logokit_token(row: LogokitSettings, token: str) -> None:
    row.api_key_encrypted = encrypt_value(token)


def logokit_is_configured(row: LogokitSettings) -> bool:
    return bool(row.api_key_encrypted)


def build_logokit_client(db: Session) -> LogokitService:
    row = get_or_create_logokit_settings(db)
    token = get_decrypted_logokit_token(row)
    return LogokitService(token=token, base_url=row.base_url)


# ---------------------------------------------------------------------------
# Prospeo
# ---------------------------------------------------------------------------
def get_or_create_prospeo_settings(db: Session) -> ProspeoSettings:
    row = db.execute(select(ProspeoSettings).limit(1)).scalar_one_or_none()
    if row is None:
        row = ProspeoSettings(
            base_url=app_settings.PROSPEO_BASE_URL,
            enabled=False,
            api_key_encrypted=None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def get_decrypted_prospeo_key(row: ProspeoSettings) -> str | None:
    if not row.api_key_encrypted:
        return None
    try:
        return decrypt_value(row.api_key_encrypted)
    except ValueError:
        return None


def get_masked_prospeo_key(row: ProspeoSettings) -> str | None:
    return mask_api_key(get_decrypted_prospeo_key(row))


def set_prospeo_key(row: ProspeoSettings, api_key: str) -> None:
    row.api_key_encrypted = encrypt_value(api_key)


def prospeo_is_configured(row: ProspeoSettings) -> bool:
    return bool(row.api_key_encrypted)


def build_prospeo_client(db: Session) -> ProspeoService:
    row = get_or_create_prospeo_settings(db)
    api_key = get_decrypted_prospeo_key(row)
    return ProspeoService(api_key=api_key, base_url=row.base_url)


# ---------------------------------------------------------------------------
# Lusha
# ---------------------------------------------------------------------------
def get_or_create_lusha_settings(db: Session) -> LushaSettings:
    row = db.execute(select(LushaSettings).limit(1)).scalar_one_or_none()
    if row is None:
        row = LushaSettings(
            base_url=app_settings.LUSHA_BASE_URL,
            enabled=False,
            api_key_encrypted=None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def get_decrypted_lusha_key(row: LushaSettings) -> str | None:
    if not row.api_key_encrypted:
        return None
    try:
        return decrypt_value(row.api_key_encrypted)
    except ValueError:
        return None


def get_masked_lusha_key(row: LushaSettings) -> str | None:
    return mask_api_key(get_decrypted_lusha_key(row))


def set_lusha_key(row: LushaSettings, api_key: str) -> None:
    row.api_key_encrypted = encrypt_value(api_key)


def lusha_is_configured(row: LushaSettings) -> bool:
    return bool(row.api_key_encrypted)


def build_lusha_client(db: Session) -> LushaService:
    row = get_or_create_lusha_settings(db)
    api_key = get_decrypted_lusha_key(row)
    return LushaService(api_key=api_key, base_url=row.base_url)
