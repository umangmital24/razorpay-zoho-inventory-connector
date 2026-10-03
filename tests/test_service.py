import pytest

from zoho_inventory_connector.config import Settings
from zoho_inventory_connector.service import ZohoInventoryService


class FakeClient:
    async def list_items(self, *, page=1, per_page=100, search_text=None, filter_by=None):
        if page > 1:
            return {"code": 0, "items": [], "page_context": {"has_more_page": False}}
        return {
            "code": 0,
            "items": [
                {
                    "item_id": "low-1",
                    "name": "Coffee Beans",
                    "sku": "COF-1",
                    "available_stock": 2,
                    "reorder_level": 5,
                },
                {
                    "item_id": "ok-1",
                    "name": "Cups",
                    "sku": "CUP-1",
                    "available_stock": 50,
                    "reorder_level": 10,
                },
            ],
            "page_context": {"has_more_page": False},
        }

    async def get_item(self, item_id):
        return {"code": 0, "item": {"item_id": item_id, "name": "Coffee Beans"}}

    async def list_sales_orders(self, *, page=1, per_page=100):
        if page > 1:
            return {"code": 0, "salesorders": [], "page_context": {"has_more_page": False}}
        return {
            "code": 0,
            "salesorders": [
                {
                    "salesorder_id": "so-open",
                    "salesorder_number": "SO-1",
                    "customer_name": "Acme Cafe",
                    "status": "confirmed",
                },
                {
                    "salesorder_id": "so-closed",
                    "salesorder_number": "SO-2",
                    "customer_name": "Done Cafe",
                    "status": "fulfilled",
                },
            ],
            "page_context": {"has_more_page": False},
        }

    async def get_sales_order(self, salesorder_id):
        assert salesorder_id == "so-open"
        return {
            "code": 0,
            "salesorder": {
                "salesorder_id": "so-open",
                "salesorder_number": "SO-1",
                "customer_name": "Acme Cafe",
                "status": "confirmed",
                "line_items": [
                    {
                        "item_id": "low-1",
                        "name": "Coffee Beans",
                        "quantity": 10,
                        "quantity_shipped": 0,
                    }
                ],
            },
        }

    async def list_organizations(self):
        return {
            "code": 0,
            "organizations": [
                {
                    "organization_id": "org-1",
                    "name": "Demo Merchant",
                    "is_default_org": True,
                }
            ],
        }


@pytest.mark.asyncio
async def test_low_stock_uses_reorder_level() -> None:
    service = ZohoInventoryService(
        FakeClient(),
        Settings(zoho_access_token="x", zoho_organization_id="org-1"),
    )

    result = await service.list_low_stock_items()

    assert result["count"] == 1
    assert result["items"][0]["item_id"] == "low-1"
    assert result["items"][0]["low_stock_threshold"] == 5


@pytest.mark.asyncio
async def test_correlates_low_stock_with_open_orders_only() -> None:
    service = ZohoInventoryService(
        FakeClient(),
        Settings(zoho_access_token="x", zoho_organization_id="org-1"),
    )

    result = await service.find_open_orders_for_low_stock()

    assert result["orders_inspected"] == 1
    assert len(result["order_exposure"]) == 1
    exposure = result["order_exposure"][0]
    assert exposure["salesorder"]["salesorder_id"] == "so-open"
    assert exposure["affected_line_items"][0]["item_id"] == "low-1"


@pytest.mark.asyncio
async def test_sales_order_search_is_bounded_and_matches_customer() -> None:
    service = ZohoInventoryService(
        FakeClient(),
        Settings(zoho_access_token="x", zoho_organization_id="org-1"),
    )

    result = await service.search_sales_orders(query="acme", max_pages=1)

    assert result["count"] == 1
    assert result["salesorders"][0]["customer_name"] == "Acme Cafe"
