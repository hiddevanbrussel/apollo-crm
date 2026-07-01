"""Apply Apollo organization enrichment payloads onto CRM companies."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company
from app.services.apollo_mapper import map_organization
from app.services.apollo_service import ApolloError
from app.services.import_service import normalize_domain


def organization_from_response(response: dict[str, Any]) -> dict[str, Any]:
    return response.get("organization") or response.get("account") or {}


def apply_apollo_organization_to_company(
    db: Session,
    company: Company,
    org: dict[str, Any],
    *,
    update_name: bool = False,
) -> None:
    """Merge Apollo organization fields onto a company record."""
    if not org:
        raise ApolloError("Apollo returned no organization data for this domain.", status_code=502)

    mapped = map_organization(org)

    apollo_id = mapped.get("apollo_id")
    if apollo_id:
        apollo_id = str(apollo_id).strip()
        if apollo_id:
            owner = db.execute(
                select(Company).where(Company.apollo_id == apollo_id, Company.id != company.id)
            ).scalar_one_or_none()
            if owner:
                mapped.pop("apollo_id", None)
            else:
                mapped["apollo_id"] = apollo_id

    skip_keys = {"source"}
    if not update_name:
        skip_keys.add("name")

    for key, value in mapped.items():
        if key in skip_keys:
            continue
        if value in (None, ""):
            continue
        if key == "name" and value == "Unknown company":
            continue
        if key == "domain":
            value = normalize_domain(str(value))
            if not value:
                continue
        if key == "phone" and isinstance(value, str):
            value = value[:60]
        if key == "linkedin_url" and isinstance(value, str):
            value = value[:255]
        if hasattr(company, key):
            setattr(company, key, value)
