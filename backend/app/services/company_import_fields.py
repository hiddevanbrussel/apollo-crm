"""Normalize import-specific company field values."""

from __future__ import annotations

import re

TIER_ALIASES = {
    "tier 1": "Tier 1",
    "tier1": "Tier 1",
    "t1": "Tier 1",
    "tier 2": "Tier 2",
    "tier2": "Tier 2",
    "t2": "Tier 2",
}

SECTOR_CONFIDENCE_ALIASES = {
    "assumed": "Assumed",
    "high": "High",
    "verify": "Verify",
    "verifiy": "Verify",
    "verified": "Verify",
}


def normalize_tier(value: str | None) -> str | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    return TIER_ALIASES.get(raw.lower(), raw)


def normalize_sector_confidence(value: str | None) -> str | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    return SECTOR_CONFIDENCE_ALIASES.get(raw.lower(), raw)


def normalize_partner_status(value: str | None) -> str | None:
    if not value:
        return None
    raw = str(value).strip()
    return raw or None


def parse_revenue_2025(value: str | None) -> int | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    digits = re.sub(r"[^\d]", "", raw)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None
