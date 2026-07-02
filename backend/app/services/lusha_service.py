"""Thin client for the Lusha REST API v3 (https://docs.lusha.com/apis/openapi)."""

from __future__ import annotations

import logging
from typing import Any, Literal

import httpx

from app.core.crypto import mask_api_key

logger = logging.getLogger("lusha.service")

DEFAULT_TIMEOUT = 45.0
RevealField = Literal["emails", "phones"]


class LushaError(Exception):
    def __init__(self, message: str, status_code: int | None = None, error_code: str | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class LushaService:
    def __init__(self, api_key: str | None, base_url: str = "https://api.lusha.com"):
        self.api_key = api_key
        self.base_url = (base_url or "https://api.lusha.com").rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "api_key": self.api_key or "",
        }

    def _require_key(self) -> None:
        if not self.api_key:
            raise LushaError("Lusha API key is not configured.", status_code=400)

    @staticmethod
    def _parse_body(response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise LushaError("Lusha returned an invalid JSON response.", status_code=502) from exc
        if not isinstance(body, dict):
            raise LushaError("Lusha returned an unexpected response.", status_code=502)
        return body

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        body = self._parse_body(response)
        if response.status_code == 401:
            raise LushaError("Invalid Lusha API key.", status_code=401, error_code="UNAUTHORIZED")
        if response.status_code == 403:
            raise LushaError("Lusha API access denied.", status_code=403, error_code="FORBIDDEN")
        if response.status_code >= 400:
            message = body.get("message") or response.text[:300]
            raise LushaError(
                f"Lusha API error {response.status_code}: {message}",
                status_code=response.status_code,
            )
        return body

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_key()
        url = f"{self.base_url}{path}"
        logger.info("Lusha POST %s (key=%s)", path, mask_api_key(self.api_key))
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
                response = client.post(url, json=payload, headers=self._headers())
        except httpx.HTTPError as exc:
            raise LushaError(f"Could not reach Lusha API: {exc}", status_code=502) from exc
        return self._handle_response(response)

    def search_and_enrich_contacts(
        self,
        contacts: list[dict[str, Any]],
        *,
        reveal: list[RevealField] | None = None,
        include_partial_profiles: bool = True,
    ) -> dict[str, Any]:
        """POST /v3/contacts/search-and-enrich — search and reveal contact data."""
        if not contacts:
            raise LushaError("At least one contact identifier is required.", status_code=400)
        payload: dict[str, Any] = {
            "contacts": contacts[:100],
            "reveal": reveal or ["phones"],
            "options": {"includePartialProfiles": include_partial_profiles},
        }
        return self._post("/v3/contacts/search-and-enrich", payload)

    def test_connection(self) -> tuple[bool, str, int | None]:
        try:
            response = self.search_and_enrich_contacts(
                [{"email": "connection-test@lusha.invalid"}],
                reveal=["phones"],
            )
            billing = response.get("billing") or {}
            credits = billing.get("creditsCharged")
            if credits is not None:
                return True, f"Connection successful (test request charged {credits} credits).", 200
            return True, "Connection successful.", 200
        except LushaError as exc:
            if exc.status_code in (401, 403):
                return False, exc.message, exc.status_code
            if exc.status_code in (400, 404):
                return True, "Connection successful (API key accepted).", 200
            return False, exc.message, exc.status_code
