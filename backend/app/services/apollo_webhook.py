"""Apollo waterfall enrichment webhook helpers."""

from __future__ import annotations

import hashlib
import secrets
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Contact
from app.services.apollo_mapper import _normalize_email


def get_webhook_secret() -> str:
    explicit = (settings.APOLLO_WEBHOOK_SECRET or "").strip()
    if explicit:
        return explicit
    digest = hashlib.sha256(f"apollo-webhook:{settings.JWT_SECRET}".encode()).hexdigest()
    return digest[:32]


def public_base_url_configured() -> bool:
    return bool((settings.PUBLIC_BASE_URL or "").strip())


def waterfall_enrichment_enabled() -> bool:
    """Whether Apollo waterfall email/phone enrichment is allowed."""
    return bool(settings.APOLLO_WATERFALL_ENABLED)


def build_contact_webhook_url(contact_id: int) -> str | None:
    """Public HTTPS URL Apollo POSTs waterfall results to."""
    base = (settings.PUBLIC_BASE_URL or "").strip().rstrip("/")
    if not base:
        return None
    secret = get_webhook_secret()
    return f"{base}/webhooks/apollo/{secret}/contacts/{contact_id}"


def redact_match_log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k not in {"email", "webhook_url"}}


def apply_waterfall_webhook(db: Session, contact: Contact, payload: dict[str, Any]) -> bool:
    """Merge asynchronous waterfall email/phone results into a contact."""
    person_data = _pick_person_payload(contact, payload)
    if not person_data:
        return False

    updated = False

    emails = person_data.get("emails") or []
    if emails and isinstance(emails[0], dict):
        email = _normalize_email(emails[0].get("email"))
        status = emails[0].get("email_status_cd") or emails[0].get("email_status")
        if email:
            if not contact.email or contact.email.lower() != email.lower():
                clash = db.execute(
                    select(Contact).where(func.lower(Contact.email) == email.lower())
                ).scalar_one_or_none()
                if not clash or clash.id == contact.id:
                    contact.email = email
                    updated = True
            if status:
                contact.email_status = status
                updated = True

    phones = person_data.get("phone_numbers") or []
    if phones and isinstance(phones[0], dict):
        phone = phones[0].get("sanitized_number") or phones[0].get("raw_number")
        if phone and phone != contact.phone:
            contact.phone = phone
            updated = True

    apollo_id = person_data.get("id")
    if apollo_id and not contact.apollo_id:
        clash = db.execute(
            select(Contact).where(Contact.apollo_id == str(apollo_id))
        ).scalar_one_or_none()
        if not clash or clash.id == contact.id:
            contact.apollo_id = str(apollo_id)
            updated = True

    merged = dict(contact.apollo_data or {})
    merged["waterfall_webhook"] = payload
    contact.apollo_data = merged
    contact.enrichment_status = "enriched"
    return updated


def _pick_person_payload(contact: Contact, payload: dict[str, Any]) -> dict[str, Any] | None:
    people = payload.get("people") or []
    if not people:
        return None

    contact_apollo_id = (contact.apollo_id or "").strip()
    if contact_apollo_id:
        for person in people:
            if person and str(person.get("id") or "") == contact_apollo_id:
                return person

    for person in people:
        if person:
            return person
    return None


def verify_webhook_secret(provided: str) -> bool:
    expected = get_webhook_secret()
    return secrets.compare_digest(provided, expected)
