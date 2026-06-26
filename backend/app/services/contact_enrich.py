"""Contact enrichment via Apollo and Prospeo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

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
from app.services.prospeo_mapper import (
    build_prospeo_enrich_data,
    has_prospeo_match_criteria,
    map_prospeo_organization,
    map_prospeo_person,
)
from app.services.prospeo_service import ProspeoError, ProspeoService
from app.services.settings_service import (
    build_client,
    build_prospeo_client,
    get_or_create_prospeo_settings,
    get_or_create_settings,
    is_configured,
    prospeo_is_configured,
)

PEOPLE_MATCH_ENDPOINT = "/api/v1/people/match"
PEOPLE_SEARCH_ENDPOINT = "/api/v1/mixed_people/api_search"
PROSPEO_ENRICH_ENDPOINT = "/enrich-person"


@dataclass
class EnrichContactResult:
    ok: bool
    status: str = "failed"
    error: str | None = None
    provider: str | None = None


def _apply_mapped_to_contact(
    db: Session,
    contact: Contact,
    mapped: dict[str, Any],
    *,
    external_id_field: str | None,
    map_org: Callable[[dict[str, Any]], dict[str, Any]],
) -> None:
    org = mapped.pop("_organization", None)
    for key, value in mapped.items():
        if key == "source":
            continue
        if value not in (None, "") and hasattr(contact, key):
            if key == "email" and value and contact.email and value.lower() == contact.email.lower():
                continue
            if external_id_field and key == external_id_field and value:
                clash = db.execute(
                    select(Contact).where(getattr(Contact, external_id_field) == value)
                ).scalar_one_or_none()
                if clash and clash.id != contact.id:
                    continue
            setattr(contact, key, value)

    if org and not contact.company_id:
        org_fields = map_org(org)
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


def _apply_person_to_contact(db: Session, contact: Contact, person: dict[str, Any]) -> None:
    _apply_mapped_to_contact(
        db,
        contact,
        map_person(person),
        external_id_field="apollo_id",
        map_org=map_organization,
    )


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
            return EnrichContactResult(ok=False, status="failed", error=last_exc.message, provider="apollo")
        return EnrichContactResult(
            ok=False,
            status="failed",
            error="Apollo found no matching person.",
            provider="apollo",
        )

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

    contact.source = "apollo"

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
    return EnrichContactResult(ok=True, status=final_status, provider="apollo")


def enrich_contact_prospeo(
    db: Session,
    client: ProspeoService,
    contact: Contact,
    *,
    company: Company | None = None,
) -> EnrichContactResult:
    """Enrich one contact via Prospeo POST /enrich-person."""
    if company is None and contact.company_id:
        company = db.get(Company, contact.company_id)

    data = build_prospeo_enrich_data(contact, company)
    if not has_prospeo_match_criteria(data):
        contact.enrichment_status = "failed"
        return EnrichContactResult(
            ok=False,
            status="failed",
            error="Not enough data for Prospeo (need email, LinkedIn, or name + company).",
            provider="prospeo",
        )

    log_data = {k: v for k, v in data.items() if k != "email"}
    try:
        response = client.enrich_person(data)
    except ProspeoError as exc:
        contact.enrichment_status = "failed"
        db.add(
            EnrichmentLog(
                entity_type="contact",
                entity_id=contact.id,
                endpoint=PROSPEO_ENRICH_ENDPOINT,
                request_payload=log_data,
                response_status=exc.status_code or 400,
            )
        )
        if exc.error_code == "NO_MATCH":
            return EnrichContactResult(
                ok=False,
                status="failed",
                error="Prospeo found no matching person.",
                provider="prospeo",
            )
        return EnrichContactResult(ok=False, status="failed", error=exc.message, provider="prospeo")

    mapped = map_prospeo_person(response)
    if not mapped:
        contact.enrichment_status = "failed"
        return EnrichContactResult(
            ok=False,
            status="failed",
            error="Prospeo returned an empty person record.",
            provider="prospeo",
        )

    _apply_mapped_to_contact(
        db,
        contact,
        mapped,
        external_id_field="prospeo_id",
        map_org=map_prospeo_organization,
    )
    contact.prospeo_data = response
    contact.enrichment_status = "enriched"
    contact.source = "prospeo"

    db.add(
        EnrichmentLog(
            entity_type="contact",
            entity_id=contact.id,
            endpoint=PROSPEO_ENRICH_ENDPOINT,
            request_payload=log_data,
            response_status=200,
        )
    )
    return EnrichContactResult(ok=True, status="enriched", provider="prospeo")


def enrich_contact_auto(
    db: Session,
    contact: Contact,
    *,
    company: Company | None = None,
) -> EnrichContactResult:
    """Try Apollo first, then Prospeo when Apollo does not match."""
    apollo_row = get_or_create_settings(db)
    prospeo_row = get_or_create_prospeo_settings(db)
    apollo_on = apollo_row.enabled and is_configured(apollo_row)
    prospeo_on = prospeo_row.enabled and prospeo_is_configured(prospeo_row)

    if not apollo_on and not prospeo_on:
        return EnrichContactResult(
            ok=False,
            status="failed",
            error="No enrichment provider enabled. Configure Apollo or Prospeo in Settings.",
        )

    apollo_result: EnrichContactResult | None = None
    if apollo_on:
        apollo_result = enrich_contact_apollo(db, build_client(db), contact, company=company)
        if apollo_result.ok:
            return apollo_result

    if prospeo_on:
        prospeo_result = enrich_contact_prospeo(
            db, build_prospeo_client(db), contact, company=company
        )
        if prospeo_result.ok:
            return prospeo_result
        if apollo_result and not apollo_result.ok:
            return EnrichContactResult(
                ok=False,
                status="failed",
                error=f"Apollo: {apollo_result.error}. Prospeo: {prospeo_result.error}",
                provider="prospeo",
            )
        return prospeo_result

    return apollo_result or EnrichContactResult(
        ok=False, status="failed", error="Enrichment failed."
    )
