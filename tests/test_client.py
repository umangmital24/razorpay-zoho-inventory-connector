import httpx
import pytest

from zoho_inventory_connector.client import ZohoInventoryClient
from zoho_inventory_connector.config import Settings


@pytest.mark.asyncio
async def test_list_items_sends_auth_and_org_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/inventory/v1/items"
        assert request.headers["Authorization"] == "Zoho-oauthtoken test-token"
        assert request.url.params["organization_id"] == "org-123"
        assert request.url.params["page"] == "2"
        return httpx.Response(
            200,
            json={
                "code": 0,
                "items": [{"item_id": "1", "name": "Coffee"}],
            },
        )

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)
    settings = Settings(
        zoho_access_token="test-token",
        zoho_organization_id="org-123",
        zoho_api_base_url="https://zoho.test",
    )

    client = ZohoInventoryClient(settings, http_client=http)
    try:
        result = await client.list_items(page=2, per_page=10)
    finally:
        await client.aclose()
        await http.aclose()

    assert result["items"][0]["name"] == "Coffee"


@pytest.mark.asyncio
async def test_retries_rate_limit_then_succeeds() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "0"},
                json={"code": 44, "message": "rate limited"},
            )
        return httpx.Response(200, json={"code": 0, "salesorders": []})

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)
    settings = Settings(
        zoho_access_token="test-token",
        zoho_organization_id="org-123",
        zoho_api_base_url="https://zoho.test",
        zoho_max_retries=2,
    )

    client = ZohoInventoryClient(settings, http_client=http)
    try:
        result = await client.list_sales_orders()
    finally:
        await client.aclose()
        await http.aclose()

    assert result["salesorders"] == []
    assert calls == 2
