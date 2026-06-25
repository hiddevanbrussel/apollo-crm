"""Service layer for Logokit (https://logokit.com).

Logokit serves company logos by domain via an image URL:
    {base_url}/{domain}?token={publishable_token}

The publishable token is meant to be used client-side, so the frontend builds the
image URLs directly. This service is mainly used to validate the token.
"""

from __future__ import annotations

import logging

import httpx

from app.core.crypto import mask_api_key

logger = logging.getLogger("logokit.service")

DEFAULT_TIMEOUT = 15.0
TEST_DOMAIN = "stripe.com"


class LogokitError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class LogokitService:
    def __init__(self, token: str | None, base_url: str = "https://img.logokit.com"):
        self.token = token
        self.base_url = (base_url or "https://img.logokit.com").rstrip("/")

    def logo_url(self, domain: str) -> str:
        return f"{self.base_url}/{domain}?token={self.token or ''}"

    def test_connection(self) -> tuple[bool, str, int | None]:
        if not self.token:
            return False, "No Logokit token configured.", 400
        url = self.logo_url(TEST_DOMAIN)
        logger.info("Logokit test (token=%s)", mask_api_key(self.token))
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
                response = client.get(url)
        except httpx.HTTPError as exc:
            return False, f"Could not reach Logokit: {exc}", 502

        if response.status_code in (401, 403):
            return False, "Logokit rejected the token (unauthorized).", response.status_code
        if response.status_code >= 400:
            return False, f"Logokit returned status {response.status_code}.", response.status_code

        content_type = response.headers.get("content-type", "")
        if "image" not in content_type:
            return False, "Logokit did not return an image. Check the token.", 502
        return True, "Connection successful. Logokit token is valid.", 200
