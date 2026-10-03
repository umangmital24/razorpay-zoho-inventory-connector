from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from .config import Settings
from .errors import AuthenticationError


class ZohoTokenProvider:
    """Provides a valid Zoho OAuth access token and refreshes it when needed."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._client = http_client
        self._owns_client = http_client is None
        self._cached_token: str | None = settings.zoho_access_token
        self._expires_at = float("inf") if settings.zoho_access_token else 0.0
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "ZohoTokenProvider":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def invalidate(self) -> None:
        if not self.settings.zoho_access_token:
            self._cached_token = None
            self._expires_at = 0.0

    async def get_access_token(self, *, force_refresh: bool = False) -> str:
        if self.settings.zoho_access_token:
            return self.settings.zoho_access_token

        self.settings.validate_runtime_auth()
        now = time.monotonic()
        if not force_refresh and self._cached_token and now < self._expires_at - 60:
            return self._cached_token

        async with self._lock:
            now = time.monotonic()
            if not force_refresh and self._cached_token and now < self._expires_at - 60:
                return self._cached_token
            return await self._refresh()

    async def _refresh(self) -> str:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.settings.zoho_request_timeout_seconds
            )

        response = await self._client.post(
            f"{self.settings.zoho_accounts_base_url}/oauth/v2/token",
            data={
                "refresh_token": self.settings.zoho_refresh_token,
                "client_id": self.settings.zoho_client_id,
                "client_secret": self.settings.zoho_client_secret,
                "grant_type": "refresh_token",
            },
        )

        try:
            payload: dict[str, Any] = response.json()
        except ValueError as exc:
            raise AuthenticationError(
                f"Zoho OAuth returned non-JSON response (HTTP {response.status_code})."
            ) from exc

        token = payload.get("access_token")
        if response.is_error or not token:
            error = payload.get("error") or payload.get("message") or "token refresh failed"
            raise AuthenticationError(
                f"Zoho OAuth token refresh failed (HTTP {response.status_code}): {error}"
            )

        expires_in = int(payload.get("expires_in", 3600))
        self._cached_token = str(token)
        self._expires_at = time.monotonic() + max(expires_in, 60)
        return self._cached_token
