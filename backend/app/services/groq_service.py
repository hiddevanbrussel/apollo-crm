"""Service layer for the Groq API.

Groq is used as an AI research assistant. With one of Groq's agentic "compound"
models (which have built-in web search) we look up the official website domain of
a company based on its name and country.

Endpoint (OpenAI-compatible): POST {base_url}/openai/v1/chat/completions
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.core.crypto import mask_api_key

logger = logging.getLogger("groq.service")

DEFAULT_TIMEOUT = 60.0  # web search can take a while
CHAT_PATH = "/openai/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are a meticulous B2B data researcher. Your single task is to determine the "
    "official primary website domain of a company. ALWAYS use web search to verify "
    "before answering.\n\n"
    "Rules for the domain you return:\n"
    "- Return only the registrable apex domain, e.g. 'acme.com' or 'acme.co.uk'.\n"
    "- Lowercase, no 'http://' or 'https://', no 'www.', no trailing path or slash.\n"
    "- Prefer the company's own corporate website over social media, app stores, or "
    "directories such as linkedin.com, crunchbase.com, facebook.com, bloomberg.com.\n"
    "- Use the provided country to disambiguate between similarly named companies.\n"
    "- If you cannot identify the company with high confidence, set found to false "
    "and domain to null. Do not guess.\n\n"
    "Respond with ONLY a single minified JSON object and no other text, markdown or "
    "code fences."
)


class GroqError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class GroqService:
    def __init__(
        self,
        api_key: str | None,
        base_url: str = "https://api.groq.com",
        model: str = "groq/compound",
    ):
        self.api_key = api_key
        self.base_url = (base_url or "https://api.groq.com").rstrip("/")
        self.model = model or "groq/compound"

    # -- internal helpers ----------------------------------------------------
    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key or ''}",
        }

    def _require_key(self) -> None:
        if not self.api_key:
            raise GroqError("Groq API key is not configured.", status_code=400)

    def _chat(self, messages: list[dict[str, str]], temperature: float = 0.0) -> str:
        self._require_key()
        url = f"{self.base_url}{CHAT_PATH}"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        logger.info("Groq chat model=%s (key=%s)", self.model, mask_api_key(self.api_key))
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
                response = client.post(url, json=payload, headers=self._headers())
        except httpx.HTTPError as exc:
            raise GroqError(f"Could not reach Groq API: {exc}", status_code=502) from exc

        if response.status_code == 401:
            raise GroqError("Groq rejected the API key (401 Unauthorized).", status_code=401)
        if response.status_code >= 400:
            raise GroqError(
                f"Groq API error {response.status_code}: {response.text[:300]}",
                status_code=response.status_code,
            )
        try:
            data = response.json()
            return data["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError) as exc:
            raise GroqError("Groq returned an unexpected response.", status_code=502) from exc

    # -- public API ----------------------------------------------------------
    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        """Run a chat completion and return the raw assistant message content."""
        return self._chat(messages, temperature=temperature)

    def find_domain(self, company_name: str, country: str | None) -> dict[str, Any]:
        """Ask Groq to find a company's official website domain via web search."""
        user_prompt = (
            f"Company name: {company_name}\n"
            f"Country: {country or 'unknown'}\n\n"
            'Respond with JSON exactly in this shape: '
            '{"found": boolean, "domain": string|null, '
            '"confidence": "high"|"medium"|"low", "reason": string}'
        )
        content = self._chat(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
        )
        return self._parse_domain_response(content)

    @staticmethod
    def _parse_domain_response(content: str) -> dict[str, Any]:
        result = {"found": False, "domain": None, "confidence": None, "reason": None, "raw": content}
        parsed = _extract_json(content)
        if parsed:
            result["found"] = bool(parsed.get("found"))
            result["confidence"] = parsed.get("confidence")
            result["reason"] = parsed.get("reason")
            domain = _normalize_domain(parsed.get("domain"))
            result["domain"] = domain
            if domain and result["found"] is False:
                # Trust a concrete domain even if the model forgot the flag.
                result["found"] = True
        else:
            # Fallback: try to find a domain-like token in free text.
            domain = _find_domain_token(content)
            if domain:
                result.update(found=True, domain=domain, confidence="low",
                              reason="Parsed from non-JSON response.")
        return result

    def test_connection(self) -> tuple[bool, str, int | None]:
        try:
            self._chat(
                [{"role": "user", "content": "Reply with the single word: ok"}],
            )
            return True, "Connection successful. Groq API key is valid.", 200
        except GroqError as exc:
            return False, exc.message, exc.status_code


def _extract_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    # Strip code fences if present.
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return None
    try:
        value = json.loads(match.group(0))
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return None


def _normalize_domain(domain: Any) -> str | None:
    if not domain or not isinstance(domain, str):
        return None
    d = domain.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    d = d.split("/")[0].split("?")[0].strip()
    if "." not in d or " " in d:
        return None
    return d or None


def _find_domain_token(text: str) -> str | None:
    if not text:
        return None
    match = re.search(r"\b([a-z0-9-]+(?:\.[a-z0-9-]+)+)\b", text.lower())
    if match:
        return _normalize_domain(match.group(1))
    return None
