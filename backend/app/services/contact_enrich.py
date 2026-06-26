"""Apollo people/match enrichment for CRM contacts."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Company, Contact, EnrichmentLog
from app.services.apollo_mapper import (
    build_person_match_attempts,
    map_organization,
    map_person,
    person_match_is_empty,
)
from app.services.apollo_service import ApolloError, ApolloService
from app.services.apollo_webhook import build_contact_webhook_url, redact_match_log_payload


@dataclass
class EnrichContactResult:
    ok: bool
    status: str = "failed"
    error: str | None = None


def enrich_contact_apollo(
    db: Session,
    client: ApolloService,
    contact: Contact,
    *,
    company: Company | None = None,
) -> EnrichContactResult:
    """Match one contact via Apollo people/match and merge results into the row."""
    if company is None and contact.company_id:
        company = db.get(Company, contact.company_id)

    match_attempts = build_person_match_attempts(contact, company)
    if not match_attempts:
        contact.enrichment_status = "failed"
        return EnrichContactResult(
            ok=False,
            status="failed",
            error="Not enough data to match (need email, name, or LinkedIn).",
        )

    needs_webhook = any(p.get("run_waterfall_email") for p in match_attempts)
    if needs_webhook:
        webhook_url = build_contact_webhook_url(contact.id)
        if not webhook_url:
            return EnrichContactResult(
                ok=False,
                status="failed",
                error="PUBLIC_BASE_URL is not configured for waterfall enrichment.",
            )
        for payload in match_attempts:
            payload["webhook_url"] = webhook_url

    response: dict = {}
    request_payload: dict = {}
    match_strategy = "full"
    last_exc: ApolloError | None = None
    for idx, payload in enumerate(match_attempts):
        try:
            attempt_response = client.enrich_person(payload)
        except ApolloError as exc:
            last_exc = exc
            continue
        person = attempt_response.get("person") or {}
        if person_match_is_empty(person):
            continue
        response = attempt_response
        request_payload = payload
        match_strategy = "email_only" if idx == 0 and payload.get("email") else "full"
        break

    log_payload = {**redact_match_log_payload(request_payload), "match_strategy": match_strategy}

    if not response:
        contact.enrichment_status = "failed"
        db.add(
            EnrichmentLog(
                entity_type="contact",
                entity_id=contact.id,
                endpoint="/api/v1/people/match",
                request_payload=redact_match_log_payload(match_attempts[-1]),
                response_status=last_exc.status_code if last_exc else 404,
            )
        )
        if last_exc:
            return EnrichContactResult(ok=False, status="failed", error=last_exc.message)
        return EnrichContactResult(ok=False, status="failed", error="Apollo found no matching person.")

    person = response.get("person") or {}
    mapped = map_person(person)
    org = mapped.pop("_organization", None)
    for key, value in mapped.items():
        if key == "source":
            continue
        if value not in (None, "") and hasattr(contact, key):
            if key == "email" and value and contact.email and value.lower() == contact.email.lower():
                continue
            if key == "apollo_id" and value:
                clash = db.execute(
                    select(Contact).where(Contact.apollo_id == value)
                ).scalar_one_or_none()
                if clash and clash.id != contact.id:
                    continue
            setattr(contact, key, value)

    if org and not contact.company_id:
        org_fields = map_organization(org)
        domain = org_fields.get("domain")
        existing_company = None
        if domain:
            existing_company = db.execute(
                select(Company).where(func.lower(Company.domain) == domain.lower())
            ).scalar_one_or_none()
        if not existing_company and org_fields.get("name"):
            existing_company = Company(
                **{k: v for k, v in org_fields.items() if hasattr(Company, k)}
            )
            existing_company.enrichment_status = "enriched"
            db.add(existing_company)
            db.flush()
        if existing_company:
            contact.company_id = existing_company.id

    waterfall = response.get("waterfall") or {}
    wf_status = (waterfall.get("status") or "").lower()
    merged_apollo = dict(contact.apollo_data or {})
    if response.get("request_id") or waterfall:
        merged_apollo["waterfall_request"] = {
            "request_id": response.get("request_id"),
            "status": waterfall.get("status"),
            "message": waterfall.get("message"),
        }
        contact.apollo_data = merged_apollo

    if wf_status == "accepted":
        contact.enrichment_status = "pending"
        final_status = "pending"
    else:
        contact.enrichment_status = "enriched"
        final_status = "enriched"

    db.add(
        EnrichmentLog(
            entity_type="contact",
            entity_id=contact.id,
            endpoint="/api/v1/people/match",
            request_payload=log_payload,
            response_status=200,
        )
    )
    return EnrichContactResult(ok=True, status=final_status)
