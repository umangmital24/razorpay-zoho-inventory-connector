from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx

from .auth import ZohoTokenProvider
from .config import Settings
from .errors import AuthenticationError, RateLimitError, ZohoAPIError


class ZohoInventoryClient:
    API_PREFIX = "/inventory/v1"

    def __init__(
        self,
        settings: Settings,
        token_provider: ZohoTokenProvider | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._http = http_client or httpx.AsyncClient(
            timeout=settings.zoho_request_timeout_seconds
        )
        self._owns_http = http_client is None
        self._token_provider = token_provider or ZohoTokenProvider(settings)
        self._owns_token_provider = token_provider is None

    async def __aenter__(self) -> ZohoInventoryClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()
        if self._owns_token_provider:
            await self._token_provider.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        organization_scoped: bool = True,
    ) -> dict[str, Any]:
        query = dict(params or {})
        if organization_scoped:
            query["organization_id"] = self.settings.require_organization_id()

        force_refresh = False
        last_status = 0

        for attempt in range(self.settings.zoho_max_retries):
            token = await self._token_provider.get_access_token(force_refresh=force_refresh)
            force_refresh = False

            response = await self._http.request(
                method,
                f"{self.settings.zoho_api_base_url}{self.API_PREFIX}{path}",
                params=query,
                headers={
                    "Authorization": f"Zoho-oauthtoken {token}",
                    "Accept": "application/json",
                    "User-Agent": "razorpay-zoho-inventory-connector/0.1.0",
                },
            )
            last_status = response.status_code

            if response.status_code == 401 and attempt == 0:
                self._token_provider.invalidate()
                if self.settings.zoho_access_token:
                    raise AuthenticationError(
                        "Zoho rejected ZOHO_ACCESS_TOKEN with HTTP 401. "
                        "Provide a valid token or configure refresh-token auth."
                    )
                force_refresh = True
                continue

            if response.status_code == 429 or 500 <= response.status_code < 600:
                if attempt + 1 >= self.settings.zoho_max_retries:
                    if response.status_code == 429:
                        raise RateLimitError(
                            "Zoho rate limit remained active after bounded retries."
                        )
                    break
                await asyncio.sleep(self._retry_delay(response, attempt))
                continue

            payload = self._decode_json(response)

            if response.is_error:
                raise self._api_error(response.status_code, payload)

            code = payload.get("code")
            if code not in (None, 0, "0"):
                raise self._api_error(response.status_code, payload)

            return payload

        raise ZohoAPIError(
            status_code=last_status,
            message="Upstream Zoho service remained unavailable after bounded retries.",
        )

    @staticmethod
    def _decode_json(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ZohoAPIError(
                status_code=response.status_code,
                message="Zoho returned a non-JSON response.",
            ) from exc
        if not isinstance(payload, dict):
            raise ZohoAPIError(
                status_code=response.status_code,
                message="Zoho returned an unexpected response shape.",
            )
        return payload

    @staticmethod
    def _api_error(status_code: int, payload: dict[str, Any]) -> ZohoAPIError:
        return ZohoAPIError(
            status_code=status_code,
            code=payload.get("code"),
            message=str(payload.get("message") or payload.get("error") or "request failed"),
            details=payload.get("details"),
        )

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(0.0, min(float(retry_after), 30.0))
            except ValueError:
                pass
        return min(2**attempt + random.uniform(0, 0.25), 8.0)

    async def list_organizations(self) -> dict[str, Any]:
        return await self._request("GET", "/organizations", organization_scoped=False)

    async def list_items(
        self,
        *,
        page: int = 1,
        per_page: int = 100,
        search_text: str | None = None,
        filter_by: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "page": max(page, 1),
            "per_page": min(max(per_page, 1), 200),
        }
        if search_text:
            params["search_text"] = search_text
        if filter_by:
            params["filter_by"] = filter_by
        return await self._request("GET", "/items", params=params)

    async def get_item(self, item_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/items/{item_id}")

    async def list_sales_orders(
        self,
        *,
        page: int = 1,
        per_page: int = 100,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/salesorders",
            params={
                "page": max(page, 1),
                "per_page": min(max(per_page, 1), 200),
            },
        )

    async def get_sales_order(self, salesorder_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/salesorders/{salesorder_id}")
