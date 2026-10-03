from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import ZohoInventoryClient
from .config import get_settings
from .service import ZohoInventoryService

mcp = FastMCP(
    "zoho-inventory",
    instructions=(
        "Read-only Zoho Inventory connector. Never claim a mutation occurred: "
        "this server exposes only retrieval and analysis primitives."
    ),
)


def _service() -> ZohoInventoryService:
    settings = get_settings()
    return ZohoInventoryService(ZohoInventoryClient(settings), settings)


async def _run(call: str, **kwargs: Any) -> dict[str, Any]:
    service = _service()
    try:
        method = getattr(service, call)
        return await method(**kwargs)
    finally:
        await service.client.aclose()


@mcp.tool()
async def list_organizations() -> dict[str, Any]:
    """List Zoho Inventory organizations available to the authorized user."""
    return await _run("list_organizations")


@mcp.tool()
async def list_items(page: int = 1, per_page: int = 100) -> dict[str, Any]:
    """List inventory items with bounded pagination."""
    return await _run("list_items", page=page, per_page=per_page)


@mcp.tool()
async def search_items(
    query: str,
    page: int = 1,
    per_page: int = 100,
) -> dict[str, Any]:
    """Search inventory items by Zoho search_text (for example name or SKU)."""
    return await _run("search_items", query=query, page=page, per_page=per_page)


@mcp.tool()
async def get_item(item_id: str) -> dict[str, Any]:
    """Retrieve one inventory item by its Zoho item ID."""
    return await _run("get_item", item_id=item_id)


@mcp.tool()
async def list_low_stock_items(
    threshold_override: float | None = None,
    max_pages: int | None = None,
) -> dict[str, Any]:
    """Find items at/below Zoho reorder level, or at/below an explicit threshold."""
    return await _run(
        "list_low_stock_items",
        threshold_override=threshold_override,
        max_pages=max_pages,
    )


@mcp.tool()
async def list_sales_orders(page: int = 1, per_page: int = 100) -> dict[str, Any]:
    """List Zoho sales orders with bounded pagination."""
    return await _run("list_sales_orders", page=page, per_page=per_page)


@mcp.tool()
async def get_sales_order(salesorder_id: str) -> dict[str, Any]:
    """Retrieve a sales order and its line items."""
    return await _run("get_sales_order", salesorder_id=salesorder_id)


@mcp.tool()
async def search_sales_orders(
    query: str | None = None,
    status: str | None = None,
    max_pages: int | None = None,
) -> dict[str, Any]:
    """Search bounded sales-order pages by customer/order/reference and/or exact status."""
    return await _run(
        "search_sales_orders",
        query=query,
        status=status,
        max_pages=max_pages,
    )


@mcp.tool()
async def find_open_orders_for_low_stock(
    threshold_override: float | None = None,
    max_pages: int | None = None,
    max_orders: int | None = None,
) -> dict[str, Any]:
    """Correlate low-stock items with line items in non-closed sales orders."""
    return await _run(
        "find_open_orders_for_low_stock",
        threshold_override=threshold_override,
        max_pages=max_pages,
        max_orders=max_orders,
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
