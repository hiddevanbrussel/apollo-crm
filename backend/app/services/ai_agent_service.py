"""A small read-only "ask your data" agent.

The agent turns a natural-language question into a single PostgreSQL SELECT over
the CRM tables, executes it against a strictly read-only transaction, and then
asks the LLM to summarise the result rows in plain language.

Safety model:
  - Only a single statement is allowed and it must be a SELECT / WITH query.
  - A denylist blocks any data-modifying or DDL keywords.
  - The query runs inside a READ ONLY transaction with a statement timeout and
    is always rolled back; results are capped to a fixed number of rows.
"""

from __future__ import annotations

import datetime
import decimal
import logging
import re
from typing import Any

from sqlalchemy import text

from app.core.database import engine
from app.services.groq_service import GroqError, GroqService, _extract_json

logger = logging.getLogger("ai.agent")

MAX_ROWS = 100
STATEMENT_TIMEOUT_MS = 8000

SCHEMA_DESCRIPTION = """
You can query a PostgreSQL database with two main tables.

Table "companies":
  - id (int, primary key)
  - name (text)
  - domain (text)            -- e.g. 'acme.com'
  - website (text)
  - linkedin_url (text)
  - industry (text)
  - employee_count (bigint)
  - revenue (bigint)         -- estimated annual revenue in USD
  - country (text)
  - city (text)
  - phone (text)
  - description (text)
  - source (text)            -- 'manual' | 'apollo' | 'import'
  - enrichment_status (text) -- 'none' | 'enriched' | 'failed'
  - extra_data (jsonb)       -- arbitrary imported columns, e.g. extra_data->>'Sector', extra_data->>'Tier'
  - created_at (timestamptz)
  - updated_at (timestamptz)

Table "contacts":
  - id (int, primary key)
  - company_id (int)         -- foreign key to companies.id (may be null)
  - first_name, last_name, full_name (text)
  - title (text)
  - headline (text)
  - email (text)
  - email_status (text)
  - phone (text)
  - linkedin_url (text)
  - city, country (text)
  - seniority (text)
  - department (text)
  - source (text)
  - enrichment_status (text)
  - apollo_data (jsonb)
  - created_at, updated_at (timestamptz)

Join contacts to companies with: contacts.company_id = companies.id
""".strip()

_PLANNER_SYSTEM = (
    "You are a precise data analyst for a self-hosted CRM. Translate the user's "
    "question into ONE PostgreSQL query over the schema below.\n\n"
    f"{SCHEMA_DESCRIPTION}\n\n"
    "Rules:\n"
    "- Produce a single read-only SELECT (a leading WITH/CTE is allowed).\n"
    "- Never write data: no INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/etc.\n"
    "- Use ILIKE for case-insensitive text matching (e.g. country ILIKE '%netherlands%').\n"
    "- For aggregate questions use COUNT/SUM/AVG and GROUP BY.\n"
    "- Always include a reasonable LIMIT (max 100) on row-returning queries.\n"
    "- If the question cannot be answered from this data, set needs_sql to false.\n\n"
    'Respond with ONLY a minified JSON object: '
    '{"needs_sql": boolean, "sql": string|null, "reason": string}'
)

_ANSWER_SYSTEM = (
    "You are a helpful CRM assistant. Answer the user's question using ONLY the "
    "query results provided. Be concise and specific: cite real numbers and names "
    "from the data. If the result set is empty, say that no matching records were "
    "found. Never invent data that is not in the results. Use markdown when it helps "
    "(short lists or a compact table)."
)

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|merge|"
    r"copy|call|do|vacuum|analyze|comment|reindex|lock|listen|notify|set|reset)\b",
    re.IGNORECASE,
)


class AgentError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _sanitize_sql(sql: str) -> str:
    """Validate that the SQL is a single, read-only SELECT/WITH statement."""
    if not sql or not sql.strip():
        raise AgentError("The assistant did not produce a query.")
    cleaned = re.sub(r"```(?:sql)?", "", sql).strip()
    # Drop a single trailing semicolon, then reject any remaining ';'.
    cleaned = cleaned.rstrip(";").strip()
    if ";" in cleaned:
        raise AgentError("Only a single statement is allowed.")
    # Strip SQL comments to prevent hiding keywords.
    no_comments = re.sub(r"--[^\n]*", "", cleaned)
    no_comments = re.sub(r"/\*.*?\*/", "", no_comments, flags=re.DOTALL)
    lowered = no_comments.lstrip().lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise AgentError("Only SELECT queries are allowed.")
    if _FORBIDDEN.search(no_comments):
        raise AgentError("The generated query contained a disallowed keyword.")
    return cleaned


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool, dict, list)):
        return value
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    return str(value)


def run_query(sql: str) -> tuple[list[str], list[list[Any]]]:
    """Execute a validated SELECT in a read-only, auto-rolled-back transaction."""
    safe_sql = _sanitize_sql(sql)
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            conn.execute(text(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}"))
            result = conn.execute(text(safe_sql))
            columns = list(result.keys())
            rows = [[_jsonable(c) for c in row] for row in result.fetchmany(MAX_ROWS)]
            return columns, rows
        except AgentError:
            raise
        except Exception as exc:  # noqa: BLE001 - surface a clean message
            raise AgentError(f"Could not run the generated query: {exc}", status_code=400) from exc
        finally:
            trans.rollback()


def _plan_sql(client: GroqService, question: str) -> dict[str, Any]:
    content = client.chat(
        [
            {"role": "system", "content": _PLANNER_SYSTEM},
            {"role": "user", "content": question},
        ],
        temperature=0.0,
    )
    parsed = _extract_json(content) or {}
    return parsed


def ask(client: GroqService, question: str) -> dict[str, Any]:
    """Full agent loop: CRM Q&A or Market Research planning."""
    question = (question or "").strip()
    if not question:
        raise AgentError("Please ask a question.")

    from app.services.research_nl_service import ResearchNlError, classify_intent, plan_research

    try:
        intent = classify_intent(client, question)
    except GroqError as exc:
        raise AgentError(exc.message, status_code=exc.status_code or 502) from exc

    if intent == "research":
        try:
            plan = plan_research(client, question)
        except ResearchNlError as exc:
            raise AgentError(exc.message, status_code=exc.status_code or 400) from exc
        except GroqError as exc:
            raise AgentError(exc.message, status_code=exc.status_code or 502) from exc

        sort_note = ""
        if plan.get("sort_by") == "employee_count_desc":
            sort_note = " Results worden gesorteerd op aantal medewerkers (grootste eerst)."
        elif plan.get("sort_by") == "revenue_desc":
            sort_note = " Results worden gesorteerd op omzet (hoogste eerst)."

        if plan.get("source") == "groq" and plan.get("query_type") == "organizations":
            credit_note = " Deze lijst komt van Groq (geen Apollo credits). Je kunt bedrijven later verrijken via Apollo."
        elif plan.get("uses_apollo_credits"):
            credit_note = " Deze zoekactie verbruikt Apollo credits."
        else:
            credit_note = " People search verbruikt geen Apollo credits."

        return {
            "answer": f"{plan['summary']}{sort_note}{credit_note}\n\nBevestig hieronder om de recordset aan te maken.",
            "sql": None,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "used_data": False,
            "intent": "research",
            "research_plan": plan,
        }

    try:
        plan = _plan_sql(client, question)
    except GroqError as exc:
        raise AgentError(exc.message, status_code=exc.status_code or 502) from exc

    sql = plan.get("sql") if plan.get("needs_sql", True) else None
    columns: list[str] = []
    rows: list[list[Any]] = []

    if sql:
        columns, rows = run_query(sql)
        results_block = {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": len(rows) >= MAX_ROWS,
        }
        user_msg = (
            f"Question: {question}\n\n"
            f"SQL used:\n{sql}\n\n"
            f"Query results (JSON):\n{results_block}"
        )
    else:
        reason = plan.get("reason") or "No database query was needed."
        user_msg = (
            f"Question: {question}\n\n"
            f"There are no query results because: {reason}\n"
            "Answer helpfully based on what a CRM assistant can say, and suggest a "
            "more specific question about companies or contacts if appropriate."
        )

    try:
        answer = client.chat(
            [
                {"role": "system", "content": _ANSWER_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
        )
    except GroqError as exc:
        raise AgentError(exc.message, status_code=exc.status_code or 502) from exc

    return {
        "answer": (answer or "").strip() or "I couldn't produce an answer.",
        "sql": sql,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "used_data": bool(sql),
        "intent": "crm",
        "research_plan": None,
    }
