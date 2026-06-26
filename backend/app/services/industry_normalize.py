"""Normalize industry labels to consistent title-style casing."""

from __future__ import annotations

import re

# Common Apollo / spreadsheet variants (lowercase key -> display form).
INDUSTRY_ALIASES: dict[str, str] = {
    "information technology & services": "Information Technology & Services",
    "information technology and services": "Information Technology & Services",
    "it services": "IT Services",
    "computer software": "Computer Software",
    "internet": "Internet",
    "financial services": "Financial Services",
    "management consulting": "Management Consulting",
    "marketing & advertising": "Marketing & Advertising",
    "marketing and advertising": "Marketing & Advertising",
    "telecommunications": "Telecommunications",
    "health, wellness & fitness": "Health, Wellness & Fitness",
    "health wellness and fitness": "Health, Wellness & Fitness",
    "hospital & health care": "Hospital & Health Care",
    "hospital and health care": "Hospital & Health Care",
    "real estate": "Real Estate",
    "construction": "Construction",
    "retail": "Retail",
    "food & beverages": "Food & Beverages",
    "food and beverages": "Food & Beverages",
    "oil & energy": "Oil & Energy",
    "oil and energy": "Oil & Energy",
    "legal services": "Legal Services",
    "accounting": "Accounting",
    "insurance": "Insurance",
    "banking": "Banking",
    "education management": "Education Management",
    "higher education": "Higher Education",
    "government administration": "Government Administration",
    "non-profit organization management": "Non-Profit Organization Management",
    "nonprofit organization management": "Non-Profit Organization Management",
    "staffing & recruiting": "Staffing & Recruiting",
    "staffing and recruiting": "Staffing & Recruiting",
    "human resources": "Human Resources",
    "logistics & supply chain": "Logistics & Supply Chain",
    "logistics and supply chain": "Logistics & Supply Chain",
    "automotive": "Automotive",
    "machinery": "Machinery",
    "electrical/electronic manufacturing": "Electrical/Electronic Manufacturing",
    "mechanical or industrial engineering": "Mechanical or Industrial Engineering",
    "biotechnology": "Biotechnology",
    "pharmaceuticals": "Pharmaceuticals",
    "media production": "Media Production",
    "online media": "Online Media",
    "design": "Design",
    "architecture & planning": "Architecture & Planning",
    "architecture and planning": "Architecture & Planning",
}

_SMALL_WORDS = frozenset({"and", "or", "of", "the", "in", "for", "a", "an", "to", "at", "by", "on"})
_ACRONYMS = frozenset(
    {
        "it",
        "ai",
        "saas",
        "b2b",
        "b2c",
        "hr",
        "ip",
        "vr",
        "ar",
        "iot",
        "uk",
        "us",
        "eu",
        "crm",
        "erp",
        "api",
        "seo",
        "sem",
    }
)


def _title_word(word: str, *, is_first: bool) -> str:
    lower = word.lower()
    if not is_first and lower in _SMALL_WORDS:
        return lower
    if lower in _ACRONYMS:
        return lower.upper()
    if "/" in lower:
        return "/".join(_title_word(part, is_first=True) for part in lower.split("/"))
    if lower.startswith("(") and lower.endswith(")"):
        return f"({_title_word(lower[1:-1], is_first=True)})"
    return lower.capitalize()


def normalize_industry(value: str | None) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    key = re.sub(r"\s+", " ", raw.lower())
    if key in INDUSTRY_ALIASES:
        return INDUSTRY_ALIASES[key]

    # Split on spaces while keeping & and /
    parts = re.split(r"(\s+|&)", raw)
    out: list[str] = []
    word_index = 0
    for part in parts:
        if not part:
            continue
        if part.isspace():
            out.append(" ")
            continue
        if part == "&":
            out.append(" & ")
            continue
        cleaned = part.strip(",.;")
        if cleaned:
            out.append(_title_word(cleaned, is_first=word_index == 0))
            word_index += 1
        trailing = part[len(cleaned) :] if cleaned else part
        if trailing:
            out.append(trailing)

    result = "".join(out)
    result = re.sub(r"\s+", " ", result).strip()
    return result or raw
