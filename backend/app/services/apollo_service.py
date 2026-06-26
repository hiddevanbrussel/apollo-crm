"""Service layer that talks to the Apollo.io REST API.

Apollo is only used as a *data source*. Nothing is persisted on Apollo's side;
callers decide what to store in the local CRM database.

Endpoints used (official Apollo API):
  - People API search       : POST /api/v1/mixed_people/api_search  (prospecting; no credits)
  - People search (legacy)  : POST /api/v1/mixed_people/search
  - Organization search    : POST /api/v1/mixed_companies/search
  - People enrichment      : POST /api/v1/people/match
  - Bulk people enrichment : POST /api/v1/people/bulk_match
  - Organization enrichment: POST /api/v1/organizations/enrich
  - User profile / credits  : GET /api/v1/users/api_profile
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.crypto import mask_api_key

logger = logging.getLogger("apollo.service")

DEFAULT_TIMEOUT = 30.0


class ApolloError(Exception):
    """Raised when the Apollo API returns an error or is misconfigured."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ApolloService:
    """Thin client around the Apollo.io HTTP API."""

    def __init__(self, api_key: str | None, base_url: str = "https://api.apollo.io"):
        self.api_key = api_key
        self.base_url = (base_url or "https://api.apollo.io").rstrip("/")

    # -- internal helpers ----------------------------------------------------
    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "accept": "application/json",
            "X-Api-Key": self.api_key or "",
        }

    def _require_key(self) -> None:
        if not self.api_key:
            raise ApolloError("Apollo API key is not configured.", status_code=400)

    @staticmethod
    def _handle_response(response: httpx.Response) -> dict[str, Any]:
        if response.status_code == 401:
            raise ApolloError("Apollo rejected the API key (401 Unauthorized).", status_code=401)
        if response.status_code == 422:
            raise ApolloError(
                f"Apollo could not process the request (422): {response.text[:300]}",
                status_code=422,
            )
        if response.status_code >= 400:
            raise ApolloError(
                f"Apollo API error {response.status_code}: {response.text[:300]}",
                status_code=response.status_code,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ApolloError("Apollo returned an invalid JSON response.", status_code=502) from exc

    def _post(
        self,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._require_key()
        url = f"{self.base_url}{path}"
        # Never log the full API key.
        logger.info("Apollo POST %s (key=%s)", path, mask_api_key(self.api_key))
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
                response = client.post(
                    url,
                    json=payload if payload is not None else None,
                    params=params,
                    headers=self._headers(),
                )
        except httpx.HTTPError as exc:
            raise ApolloError(f"Could not reach Apollo API: {exc}", status_code=502) from exc
        return self._handle_response(response)

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        self._require_key()
        url = f"{self.base_url}{path}"
        # Never log the full API key.
        logger.info("Apollo GET %s (key=%s)", path, mask_api_key(self.api_key))
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
                response = client.get(url, params=params, headers=self._headers())
        except httpx.HTTPError as exc:
            raise ApolloError(f"Could not reach Apollo API: {exc}", status_code=502) from exc
        return self._handle_response(response)

    @staticmethod
    def _clean(payload: dict[str, Any]) -> dict[str, Any]:
        """Drop None / empty values so we only send meaningful filters."""
        cleaned: dict[str, Any] = {}
        for key, value in payload.items():
            if value is None:
                continue
            if isinstance(value, (list, dict, str)) and len(value) == 0:
                continue
            cleaned[key] = value
        return cleaned

    # -- public API ----------------------------------------------------------
    def search_people(self, filters: dict[str, Any]) -> dict[str, Any]:
        """Search for people. Returns raw Apollo response."""
        payload = self._clean(filters)
        return self._post("/api/v1/mixed_people/search", payload)

    def search_people_api(self, filters: dict[str, Any]) -> dict[str, Any]:
        """Search people via /api/v1/mixed_people/api_search. Returns raw response."""
        payload = self._clean(filters)
        return self._post("/api/v1/mixed_people/api_search", payload)

    def search_people_by_domains(
        self, domains: list[str], page: int = 1, per_page: int = 25
    ) -> dict[str, Any]:
        """Find people working at organizations matching the given domains."""
        return self.search_people_api(
            {
                "q_organization_domains_list": [d for d in domains if d],
                "page": page,
                "per_page": per_page,
            }
        )

    def get_person(self, person_id: str) -> dict[str, Any]:
        """Fetch the complete profile for a single person via GET /api/v1/people/{id}."""
        if not person_id:
            raise ApolloError("A person id is required.", status_code=400)
        return self._get(f"/api/v1/people/{person_id}", {})

    def search_organizations(self, filters: dict[str, Any]) -> dict[str, Any]:
        """Search for organizations. Returns raw Apollo response."""
        payload = self._clean(filters)
        return self._post("/api/v1/mixed_companies/search", payload)

    def enrich_person(self, data: dict[str, Any]) -> dict[str, Any]:
        """Enrich a single person via /people/match (query parameters)."""
        params = self._clean(data)
        for key, value in list(params.items()):
            if isinstance(value, bool):
                params[key] = str(value).lower()
        return self._post("/api/v1/people/match", params=params)

    def enrich_people_bulk(self, data: dict[str, Any]) -> dict[str, Any]:
        """Enrich multiple people via /people/bulk_match."""
        details = data.get("details") or []
        payload = {
            "details": [self._clean(d) for d in details],
            "reveal_personal_emails": data.get("reveal_personal_emails", False),
            "reveal_phone_number": data.get("reveal_phone_number", False),
        }
        return self._post("/api/v1/people/bulk_match", payload)

    def enrich_organization(self, data: dict[str, Any]) -> dict[str, Any]:
        """Enrich a single organization via GET /api/v1/organizations/enrich.

        Apollo's organization enrichment endpoint is a GET request that takes the
        company ``domain`` as a query parameter.
        """
        domain = (data or {}).get("domain")
        if isinstance(domain, str):
            domain = domain.strip()
        if not domain:
            raise ApolloError(
                "A company domain is required to enrich an organization.", status_code=400
            )
        return self._get("/api/v1/organizations/enrich", {"domain": domain})

    def get_api_profile(self, *, include_credit_usage: bool = True) -> dict[str, Any]:
        """Fetch the authenticated Apollo user profile (GET /api/v1/users/api_profile)."""
        params: dict[str, Any] = {}
        if include_credit_usage:
            params["include_credit_usage"] = "true"
        return self._get("/api/v1/users/api_profile", params)

    def test_connection(self) -> tuple[bool, str, int | None]:
        """Light-weight connectivity/credentials test.

        Performs a minimal org search; a 200 means key + base URL are valid.
        """
        try:
            self._post("/api/v1/mixed_companies/search", {"page": 1, "per_page": 1})
            return True, "Connection successful. Apollo API key is valid.", 200
        except ApolloError as exc:
            return False, exc.message, exc.status_code
