"""Generate normalized job titles (title_ai) via Groq."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Contact
from app.services.groq_service import GroqError, GroqService
from app.services.settings_service import build_groq_client, get_or_create_groq_settings, groq_is_configured


@dataclass
class TitleAiResult:
    ok: bool
    title_ai: str | None = None
    error: str | None = None
    skipped: bool = False
    reason: str | None = None


def ensure_groq_title_ai_enabled(db: Session) -> None:
    row = get_or_create_groq_settings(db)
    if not row.enabled:
        raise GroqError("The Groq integration is off. Enable it in Settings.", status_code=400)
    if not groq_is_configured(row):
        raise GroqError("No Groq API key configured. Add one in Settings.", status_code=400)


def normalize_contact_title_ai(
    db: Session,
    contact: Contact,
    *,
    client: GroqService | None = None,
    force: bool = False,
) -> TitleAiResult:
    raw_title = (contact.title or "").strip()
    if not raw_title:
        return TitleAiResult(ok=False, skipped=True, error="Contact has no title.")

    existing_ai = (contact.title_ai or "").strip()
    if existing_ai and not force:
        return TitleAiResult(ok=True, title_ai=existing_ai, skipped=True, reason="Already has title AI.")

    if client is None:
        ensure_groq_title_ai_enabled(db)
        client = build_groq_client(db)

    company_name = contact.company.name if contact.company else None
    try:
        parsed = client.normalize_job_title(
            title=raw_title,
            seniority=contact.seniority,
            department=contact.department,
            company_name=company_name,
        )
    except GroqError as exc:
        return TitleAiResult(ok=False, error=exc.message)

    title_ai = parsed.get("title_ai")
    if not title_ai:
        return TitleAiResult(
            ok=False,
            error=parsed.get("reason") or "Groq could not normalize this title.",
        )

    contact.title_ai = title_ai[:255]
    return TitleAiResult(
        ok=True,
        title_ai=contact.title_ai,
        reason=parsed.get("reason"),
    )
