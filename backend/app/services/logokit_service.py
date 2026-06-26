"""Service layer for Logokit (https://logokit.com).

Logo API authentication uses a publishable token (pk_…) as a query parameter:
    https://img.logokit.com/{domain}?token={pk_token}

See https://docs.logokit.com/authentication
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

import httpx

from app.core.crypto import mask_api_key

logger = logging.getLogger("logokit.service")

DEFAULT_TIMEOUT = 15.0
TEST_DOMAIN = "stripe.com"
ALLOWED_SIZES = (64, 128, 256)


class LogokitError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def normalize_logo_domain(domain: str | None) -> str | None:
    if not domain:
        return None
    value = domain.strip().lower()
    if value.startswith("www."):
        value = value[4:]
    return value or None


def snap_logo_size(size: int | None) -> int:
    """LogoKit only accepts 64, 128, or 256."""
    if size is None or size <= 64:
        return 64
    if size <= 128:
        return 128
    return 256


def validate_publishable_token(token: str | None) -> str | None:
    """Return an error message when the token is missing or wrong type."""
    value = (token or "").strip()
    if not value:
        return "No Logokit token configured."
    if value.startswith("sk_"):
        return (
            "This looks like a Brand API secret token (sk_…). "
            "Use a Logo API publishable token (pk_…) from Logokit → API Tokens → Logo API."
        )
    if not value.startswith("pk_"):
        return (
            "Logo API publishable tokens start with pk_. "
            "Find yours under Logokit → API Tokens → Logo API Tokens."
        )
    return None


class LogokitService:
    def __init__(self, token: str | None, base_url: str = "https://img.logokit.com"):
        self.token = token
        self.base_url = (base_url or "https://img.logokit.com").rstrip("/")

    def logo_url(self, domain: str, *, size: int = 64) -> str:
        normalized = normalize_logo_domain(domain) or domain
        params = {
            "token": self.token or "",
            "size": snap_logo_size(size),
        }
        return f"{self.base_url}/{normalized}?{urlencode(params)}"

    def test_connection(self) -> tuple[bool, str, int | None]:
        token_error = validate_publishable_token(self.token)
        if token_error:
            return False, token_error, 400

        url = self.logo_url(TEST_DOMAIN, size=64)
        logger.info("Logokit test (token=%s)", mask_api_key(self.token))
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
                response = client.get(url)
        except httpx.HTTPError as exc:
            return False, f"Could not reach Logokit: {exc}", 502

        if response.status_code in (401, 403):
            return (
                False,
                "Logokit rejected the token. Use a publishable Logo API token (pk_…) from your Logokit account.",
                response.status_code,
            )
        if response.status_code == 429:
            return False, "Logokit rate limit exceeded. Try again later.", 429
        if response.status_code >= 400:
            detail = response.text.strip()[:160]
            suffix = f" Response: {detail}" if detail else ""
            return False, f"Logokit returned status {response.status_code}.{suffix}", response.status_code

        content_type = (response.headers.get("content-type") or "").lower()
        if not content_type.startswith("image/"):
            return (
                False,
                "Logokit did not return an image. Check that the token is a Logo API publishable token (pk_…).",
                502,
            )
        if len(response.content) < 32:
            return False, "Logokit returned an empty image response.", 502

        return True, "Connection successful. Logokit Logo API token is valid.", 200
