"""Apollo people/match enrichment for CRM contacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Company, Contact, EnrichmentLog
from app.services.apollo_mapper import (
    build_person_match_attempts,
    build_person_search_attempts,
    map_organization,
    map_person,
    person_match_is_empty,
    pick_best_person_search_match,
)
from app.services.apollo_service import ApolloError, ApolloService
from app.services.apollo_webhook import (
    build_contact_webhook_url,
    redact_match_log_payload,
    waterfall_enrichment_enabled,
)

PEOPLE_MATCH_ENDPOINT = "/api/v1/people/match"
PEOPLE_SEARCH_ENDPOINT = "/api/v1/mixed_people/api_search"


@dataclass
class EnrichContactResult:
    ok: bool
    status: str = "failed"
    error: str | None = None


def _apply_person_to_contact(db: Session, contact: Contact, person: dict[str, Any]) -> None:
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


def _match_strategy_label(payload: dict[str, Any]) -> str:
    if payload.get("email") and not payload.get("name") and not payload.get("first_name"):
        return "email_only"
    if payload.get("name") and payload.get("organization_name") and not payload.get("domain"):
        return "name_organization"
    return "full"


def _try_people_match(
    client: ApolloService,
    match_attempts: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], str, ApolloError | None]:
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
        strategy = _match_strategy_label(payload)
        return attempt_response, payload, strategy, None
    return {}, {}, "full", last_exc


def _try_search_then_match(
    client: ApolloService,
    contact: Contact,
    company: Company | None,
    *,
    webhook_url: str | None,
    reveal_personal_emails: bool = True,
    run_waterfall_email: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    """People API Search → people/match by Apollo id when direct match fails."""
    search_attempts = build_person_search_attempts(contact, company)
    if not search_attempts:
        return {}, {}, None

    last_search_payload: dict[str, Any] | None = None
    for search_payload in search_attempts:
        last_search_payload = search_payload
        try:
            search_response = client.search_people_api(search_payload)
        except ApolloError:
            continue

        people = search_response.get("people") or search_response.get("contacts") or []
        best = pick_best_person_search_match(contact, company, people)
        if not best or not best.get("id"):
            continue

        enrich_payload: dict[str, Any] = {
            "id": best["id"],
            "reveal_personal_emails": reveal_personal_emails,
            "run_waterfall_email": run_waterfall_email,
        }
        if webhook_url:
            enrich_payload["webhook_url"] = webhook_url

        try:
            match_response = client.enrich_person(enrich_payload)
        except ApolloError:
            continue

        person = match_response.get("person") or {}
        if person_match_is_empty(person):
            continue

        log_payload = {
            **redact_match_log_payload(enrich_payload),
            "match_strategy": "search_then_match",
            "search_filters": redact_match_log_payload(search_payload),
            "search_person_id": best.get("id"),
        }
        return match_response, log_payload, search_payload

    return {}, {}, last_search_payload


def enrich_contact_apollo(
    db: Session,
    client: ApolloService,
    contact: Contact,
    *,
    company: Company | None = None,
) -> EnrichContactResult:
    """Match one contact via Apollo people/match, with people search as fallback."""
    if company is None and contact.company_id:
        company = db.get(Company, contact.company_id)

    match_attempts = build_person_match_attempts(
        contact,
        company,
        run_waterfall_email=waterfall_enrichment_enabled(),
    )
    if not match_attempts:
        contact.enrichment_status = "failed"
        return EnrichContactResult(
            ok=False,
            status="failed",
            error="Not enough data to match (need email, name, or LinkedIn).",
        )

    reveal_personal_emails = bool(match_attempts[0].get("reveal_personal_emails", True))
    run_waterfall_email = bool(match_attempts[0].get("run_waterfall_email", False))

    webhook_url: str | None = None
    if run_waterfall_email:
        webhook_url = build_contact_webhook_url(contact.id)
        if not webhook_url:
            return EnrichContactResult(
                ok=False,
                status="failed",
                error="PUBLIC_BASE_URL is not configured for waterfall enrichment.",
            )
        for payload in match_attempts:
            payload["webhook_url"] = webhook_url

    response, request_payload, match_strategy, last_exc = _try_people_match(client, match_attempts)
    search_payload_used: dict[str, Any] | None = None

    if not response:
        response, request_payload, search_payload_used = _try_search_then_match(
            client,
            contact,
            company,
            webhook_url=webhook_url,
            reveal_personal_emails=reveal_personal_emails,
            run_waterfall_email=run_waterfall_email,
        )
        if response:
            match_strategy = "search_then_match"

    log_payload: dict[str, Any] = {
        **redact_match_log_payload(request_payload),
        "match_strategy": match_strategy,
    }

    if not response:
        contact.enrichment_status = "failed"
        db.add(
            EnrichmentLog(
                entity_type="contact",
                entity_id=contact.id,
                endpoint=PEOPLE_MATCH_ENDPOINT,
                request_payload=redact_match_log_payload(match_attempts[-1]),
                response_status=last_exc.status_code if last_exc else 404,
            )
        )
        if search_payload_used:
            db.add(
                EnrichmentLog(
                    entity_type="contact",
                    entity_id=contact.id,
                    endpoint=PEOPLE_SEARCH_ENDPOINT,
                    request_payload=redact_match_log_payload(search_payload_used),
                    response_status=404,
                )
            )
        if last_exc:
            return EnrichContactResult(ok=False, status="failed", error=last_exc.message)
        return EnrichContactResult(ok=False, status="failed", error="Apollo found no matching person.")

    person = response.get("person") or {}
    _apply_person_to_contact(db, contact, person)

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
            endpoint=PEOPLE_MATCH_ENDPOINT,
            request_payload=log_payload,
            response_status=200,
        )
    )
    if search_payload_used and match_strategy == "search_then_match":
        db.add(
            EnrichmentLog(
                entity_type="contact",
                entity_id=contact.id,
                endpoint=PEOPLE_SEARCH_ENDPOINT,
                request_payload=redact_match_log_payload(search_payload_used),
                response_status=200,
            )
        )
    return EnrichContactResult(ok=True, status=final_status)
