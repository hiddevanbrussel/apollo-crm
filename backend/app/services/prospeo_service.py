"""Thin client for the Prospeo REST API (https://prospeo.io/api-docs)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.crypto import mask_api_key

logger = logging.getLogger("prospeo.service")

DEFAULT_TIMEOUT = 30.0


class ProspeoError(Exception):
    def __init__(self, message: str, status_code: int | None = None, error_code: str | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class ProspeoService:
    def __init__(self, api_key: str | None, base_url: str = "https://api.prospeo.io"):
        self.api_key = api_key
        self.base_url = (base_url or "https://api.prospeo.io").rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-KEY": self.api_key or "",
        }

    def _require_key(self) -> None:
        if not self.api_key:
            raise ProspeoError("Prospeo API key is not configured.", status_code=400)

    @staticmethod
    def _parse_body(response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise ProspeoError("Prospeo returned an invalid JSON response.", status_code=502) from exc
        if not isinstance(body, dict):
            raise ProspeoError("Prospeo returned an unexpected response.", status_code=502)
        return body

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        body = self._parse_body(response)
        if body.get("error"):
            error_code = body.get("error_code") or body.get("message") or "PROSPEO_ERROR"
            raise ProspeoError(
                f"Prospeo error ({error_code}).",
                status_code=response.status_code or 400,
                error_code=str(error_code),
            )
        if response.status_code >= 400:
            raise ProspeoError(
                f"Prospeo API error {response.status_code}: {response.text[:300]}",
                status_code=response.status_code,
            )
        return body

    def _post(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self._require_key()
        url = f"{self.base_url}{path}"
        logger.info("Prospeo POST %s (key=%s)", path, mask_api_key(self.api_key))
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
                response = client.post(url, json=payload or {}, headers=self._headers())
        except httpx.HTTPError as exc:
            raise ProspeoError(f"Could not reach Prospeo API: {exc}", status_code=502) from exc
        return self._handle_response(response)

    def _get(self, path: str) -> dict[str, Any]:
        self._require_key()
        url = f"{self.base_url}{path}"
        logger.info("Prospeo GET %s (key=%s)", path, mask_api_key(self.api_key))
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
                response = client.get(url, headers=self._headers())
        except httpx.HTTPError as exc:
            raise ProspeoError(f"Could not reach Prospeo API: {exc}", status_code=502) from exc
        return self._handle_response(response)

    def enrich_person(
        self,
        data: dict[str, Any],
        *,
        only_verified_email: bool = False,
        enrich_mobile: bool = False,
    ) -> dict[str, Any]:
        """POST /enrich-person — match and enrich one person."""
        payload: dict[str, Any] = {"data": data}
        if only_verified_email:
            payload["only_verified_email"] = True
        if enrich_mobile:
            payload["enrich_mobile"] = True
        return self._post("/enrich-person", payload)

    def get_account(self) -> dict[str, Any]:
        """GET /account-information — free connectivity/credits check."""
        return self._get("/account-information")

    def test_connection(self) -> tuple[bool, str, int | None]:
        try:
            response = self.get_account()
            info = response.get("response") or {}
            credits = info.get("remaining_credits")
            plan = info.get("current_plan") or "unknown"
            if credits is not None:
                return True, f"Connection successful. Plan {plan}, {credits} credits remaining.", 200
            return True, f"Connection successful. Plan {plan}.", 200
        except ProspeoError as exc:
            return False, exc.message, exc.status_code
