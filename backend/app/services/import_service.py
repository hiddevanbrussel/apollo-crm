"""Parse uploaded spreadsheets (xlsx / csv) into normalized row dicts.

Rows are returned keyed by their *original* (whitespace-trimmed) header so the
caller can preserve every column. Use :func:`canonical_field` to map a header
onto one of the known CRM fields (customer_name, country, domain).
"""

from __future__ import annotations

import csv
import io

from openpyxl import load_workbook

# Header aliases -> canonical CRM field. Matching is case-insensitive and
# ignores surrounding whitespace.
HEADER_ALIASES: dict[str, str] = {
    "customer_name": "customer_name",
    "customer name": "customer_name",
    "company": "customer_name",
    "company_name": "customer_name",
    "name": "customer_name",
    "bedrijf": "customer_name",
    "bedrijfsnaam": "customer_name",
    "country": "country",
    "land": "country",
    "domain": "domain",
    "website": "domain",
    "website_url": "domain",
}


class ImportParseError(Exception):
    pass


def canonical_field(header: object) -> str | None:
    """Return the canonical CRM field for a header, or None if it is custom."""
    if header is None:
        return None
    return HEADER_ALIASES.get(str(header).strip().lower())


def _has_name_column(headers) -> bool:
    return any(canonical_field(h) == "customer_name" for h in headers)


def _parse_xlsx(content: bytes) -> list[dict[str, str]]:
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise ImportParseError(f"Could not read Excel file: {exc}") from exc
    sheet = workbook.active
    rows_iter = sheet.iter_rows(values_only=True)
    try:
        header_row = next(rows_iter)
    except StopIteration:
        return []

    headers = [str(h).strip() if h not in (None, "") else None for h in header_row]
    if not _has_name_column(headers):
        raise ImportParseError(
            "Required column 'customer_name' not found. Expected at least: customer_name."
        )

    rows: list[dict[str, str]] = []
    for raw in rows_iter:
        record: dict[str, str] = {}
        for idx, header in enumerate(headers):
            if header is None or idx >= len(raw):
                continue
            value = raw[idx]
            record[header] = str(value).strip() if value not in (None, "") else ""
        if any(v for v in record.values()):
            rows.append(record)
    return rows


def _parse_csv(content: bytes) -> list[dict[str, str]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    sample = text[:2048]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows_list = list(reader)
    if not rows_list:
        return []

    headers = [h.strip() if h and h.strip() else None for h in rows_list[0]]
    if not _has_name_column(headers):
        raise ImportParseError(
            "Required column 'customer_name' not found. Expected at least: customer_name."
        )

    rows: list[dict[str, str]] = []
    for raw in rows_list[1:]:
        record: dict[str, str] = {}
        for idx, header in enumerate(headers):
            if header is None or idx >= len(raw):
                continue
            value = raw[idx]
            record[header] = value.strip() if value else ""
        if any(v for v in record.values()):
            rows.append(record)
    return rows


def parse_spreadsheet(filename: str, content: bytes) -> list[dict[str, str]]:
    """Return rows as {original_header: value} dicts from an xlsx or csv file."""
    lower = (filename or "").lower()
    if lower.endswith(".csv"):
        return _parse_csv(content)
    if lower.endswith(".xlsx") or lower.endswith(".xlsm"):
        return _parse_xlsx(content)
    try:
        return _parse_xlsx(content)
    except ImportParseError:
        return _parse_csv(content)
