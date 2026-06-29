"""Normalize Apollo search filter values before API calls."""

from __future__ import annotations

import re
from typing import Any

# Friendly CRM field names -> Apollo API parameter names.
FIELD_ALIASES: dict[str, str] = {
    "organization_domains": "q_organization_domains_list",
    "organization_industries": "q_organization_keyword_tags",
}

LIST_FIELDS = {
    "person_titles",
    "person_seniorities",
    "person_departments",
    "person_locations",
    "organization_locations",
    "organization_not_locations",
    "q_organization_domains_list",
    "contact_email_status",
    "organization_ids",
    "organization_num_employees_ranges",
    "currently_using_all_of_technology_uids",
    "currently_using_any_of_technology_uids",
    "currently_not_using_any_of_technology_uids",
    "q_organization_job_titles",
    "organization_job_locations",
    "q_organization_keyword_tags",
    "organization_latest_funding_stage_cd",
    "organization_industry_tag_ids",
}

RANGE_FIELDS = {
    "revenue_range",
    "organization_num_jobs_range",
    "organization_job_posted_at_range",
    "organization_founded_year_range",
}


def normalize_employee_ranges(value: list[str] | str | None) -> list[str] | None:
    """Parse employee ranges for Apollo's organization_num_employees_ranges.

    Apollo expects each range as a single string ``"min,max"`` (e.g. ``"1,10"``).
    Multiple ranges are separate list entries: ``["1,10", "11,50"]``.

    Commas inside a range must NOT be used as list separators. Use ``·``, ``|`` or ``;``
    between ranges instead (e.g. ``1,10 · 11,50``).
    """
    if value is None:
        return None

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        parts = re.split(r"[·|;|\n]+", text)
        items = [p.strip() for p in parts if p.strip()]
    else:
        items = [str(v).strip() for v in value if str(v).strip()]

    if not items:
        return None

    ranges: list[str] = []
    i = 0
    while i < len(items):
        part = items[i]
        if re.fullmatch(r"\d+", part) and i + 1 < len(items) and re.fullmatch(r"\d+", items[i + 1]):
            ranges.append(f"{part},{items[i + 1]}")
            i += 2
            continue
        ranges.append(part)
        i += 1

    return ranges or None


def _coerce_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes"):
            return True
        if lowered in ("false", "0", "no"):
            return False
    return None


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        return [part.strip() for part in re.split(r"[,;\n]+", text) if part.strip()]
    if isinstance(value, list):
        items = [str(v).strip() for v in value if str(v).strip()]
        return items or None
    return None


def _apply_range(payload: dict[str, Any], key: str, value: Any) -> None:
    if value is None or value == "":
        return
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for bound in ("min", "max"):
            coerced = _coerce_int(value.get(bound))
            if coerced is not None:
                out[bound] = coerced
        if out:
            payload[key] = out
        return

    if isinstance(value, str) and ":" in value:
        left, _, right = value.partition(":")
        out = {}
        min_val = _coerce_int(left.strip())
        max_val = _coerce_int(right.strip())
        if min_val is not None:
            out["min"] = min_val
        if max_val is not None:
            out["max"] = max_val
        if out:
            payload[key] = out
        return

    min_key = f"{key}_min"
    max_key = f"{key}_max"
    if min_key in payload or max_key in payload:
        out = {}
        min_val = _coerce_int(payload.pop(min_key, None))
        max_val = _coerce_int(payload.pop(max_key, None))
        if min_val is not None:
            out["min"] = min_val
        if max_val is not None:
            out["max"] = max_val
        if out:
            payload[key] = out


def normalize_search_payload(filters: dict[str, Any] | None) -> dict[str, Any]:
    """Map friendly filter keys to Apollo parameters and normalize values."""
    if not filters:
        return {}

    payload: dict[str, Any] = {}
    deferred_ranges: dict[str, Any] = {}

    for key, value in filters.items():
        if value is None or value == "" or value == []:
            continue

        target = FIELD_ALIASES.get(key, key)

        if key in RANGE_FIELDS or target in RANGE_FIELDS:
            deferred_ranges[target] = value
            continue

        if key.endswith("_min") or key.endswith("_max"):
            base = key.rsplit("_", 1)[0]
            if base in RANGE_FIELDS:
                deferred_ranges.setdefault(base, {})[
                    "min" if key.endswith("_min") else "max"
                ] = value
            continue

        if target == "organization_num_employees_ranges":
            normalized = normalize_employee_ranges(value)
            if normalized:
                payload[target] = normalized
            continue

        if target == "include_similar_titles":
            coerced = _coerce_bool(value)
            if coerced is not None:
                payload[target] = coerced
            continue

        if target in LIST_FIELDS:
            normalized = _normalize_list(value)
            if normalized:
                payload[target] = normalized
            continue

        if target in ("page", "per_page"):
            coerced = _coerce_int(value)
            if coerced is not None:
                payload[target] = coerced
            continue

        payload[target] = value

    for key, value in deferred_ranges.items():
        _apply_range(payload, key, value)

    return payload
