from __future__ import annotations

from typing import Any

from .client import ZohoInventoryClient
from .config import Settings


CLOSED_ORDER_STATUSES = {"fulfilled", "void", "cancelled", "canceled", "closed"}


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _has_more(payload: dict[str, Any], records: list[Any], per_page: int) -> bool:
    page_context = payload.get("page_context") or {}
    if isinstance(page_context, dict) and "has_more_page" in page_context:
        return bool(page_context["has_more_page"])
    return len(records) >= per_page


class ZohoInventoryService:
    """Agent-facing read-only primitives with bounded scans and normalized output."""

    def __init__(self, client: ZohoInventoryClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    async def list_organizations(self) -> dict[str, Any]:
        payload = await self.client.list_organizations()
        organizations = payload.get("organizations") or []
        return {
            "organizations": [
                {
                    "organization_id": str(org.get("organization_id", "")),
                    "name": org.get("name"),
                    "is_default_org": org.get("is_default_org"),
                    "currency_code": org.get("currency_code"),
                    "time_zone": org.get("time_zone"),
                }
                for org in organizations
            ]
        }

    @staticmethod
    def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
        stock = None
        for key in ("actual_available_stock", "available_stock", "stock_on_hand"):
            stock = _to_float(item.get(key))
            if stock is not None:
                break
        return {
            "item_id": str(item.get("item_id") or item.get("item_master_id") or ""),
            "name": item.get("name"),
            "sku": item.get("sku"),
            "status": item.get("status"),
            "unit": item.get("unit"),
            "rate": item.get("rate"),
            "available_stock": stock,
            "reorder_level": _to_float(item.get("reorder_level")),
            "is_combo_product": item.get("is_combo_product"),
        }

    async def list_items(
        self,
        *,
        page: int = 1,
        per_page: int = 100,
        search_text: str | None = None,
        filter_by: str | None = None,
    ) -> dict[str, Any]:
        payload = await self.client.list_items(
            page=page,
            per_page=per_page,
            search_text=search_text,
            filter_by=filter_by,
        )
        items = payload.get("items") or []
        return {
            "items": [self.normalize_item(item) for item in items],
            "page_context": payload.get("page_context"),
        }

    async def search_items(
        self,
        query: str,
        *,
        page: int = 1,
        per_page: int = 100,
    ) -> dict[str, Any]:
        if not query.strip():
            raise ValueError("query must not be empty")
        return await self.list_items(
            page=page,
            per_page=per_page,
            search_text=query.strip(),
        )

    async def get_item(self, item_id: str) -> dict[str, Any]:
        if not item_id.strip():
            raise ValueError("item_id must not be empty")
        payload = await self.client.get_item(item_id.strip())
        item = payload.get("item") or {}
        return {
            "item": self.normalize_item(item),
            "raw": item,
        }

    async def list_low_stock_items(
        self,
        *,
        threshold_override: float | None = None,
        max_pages: int | None = None,
        per_page: int = 100,
    ) -> dict[str, Any]:
        pages = min(max_pages or self.settings.zoho_max_scan_pages, 20)
        low_stock: list[dict[str, Any]] = []

        for page in range(1, pages + 1):
            payload = await self.client.list_items(page=page, per_page=per_page)
            raw_items = payload.get("items") or []
            for raw in raw_items:
                item = self.normalize_item(raw)
                stock = item["available_stock"]
                reorder = item["reorder_level"]
                threshold = threshold_override if threshold_override is not None else reorder

                if stock is None or threshold is None:
                    continue
                if stock <= threshold:
                    item["low_stock_threshold"] = threshold
                    item["units_below_or_at_threshold"] = threshold - stock
                    low_stock.append(item)

            if not _has_more(payload, raw_items, per_page):
                break

        return {
            "items": low_stock,
            "count": len(low_stock),
            "scan_bounded_to_pages": pages,
            "threshold_mode": (
                "explicit" if threshold_override is not None else "zoho_reorder_level"
            ),
        }

    @staticmethod
    def normalize_order(order: dict[str, Any]) -> dict[str, Any]:
        return {
            "salesorder_id": str(order.get("salesorder_id") or ""),
            "salesorder_number": order.get("salesorder_number"),
            "reference_number": order.get("reference_number"),
            "customer_id": str(order.get("customer_id") or ""),
            "customer_name": order.get("customer_name"),
            "status": order.get("status"),
            "date": order.get("date"),
            "shipment_date": order.get("shipment_date"),
            "currency_code": order.get("currency_code"),
            "total": order.get("total"),
        }

    async def list_sales_orders(
        self,
        *,
        page: int = 1,
        per_page: int = 100,
    ) -> dict[str, Any]:
        payload = await self.client.list_sales_orders(page=page, per_page=per_page)
        orders = payload.get("salesorders") or []
        return {
            "salesorders": [self.normalize_order(order) for order in orders],
            "page_context": payload.get("page_context"),
        }

    async def get_sales_order(self, salesorder_id: str) -> dict[str, Any]:
        if not salesorder_id.strip():
            raise ValueError("salesorder_id must not be empty")
        payload = await self.client.get_sales_order(salesorder_id.strip())
        order = payload.get("salesorder") or payload.get("sales_order") or {}
        return {
            "salesorder": self.normalize_order(order),
            "line_items": [
                {
                    "item_id": str(line.get("item_id") or ""),
                    "name": line.get("name"),
                    "quantity": line.get("quantity"),
                    "quantity_shipped": line.get("quantity_shipped"),
                    "rate": line.get("rate"),
                    "item_total": line.get("item_total"),
                }
                for line in (order.get("line_items") or [])
            ],
        }

    async def search_sales_orders(
        self,
        *,
        query: str | None = None,
        status: str | None = None,
        max_pages: int | None = None,
        per_page: int = 100,
    ) -> dict[str, Any]:
        pages = min(max_pages or self.settings.zoho_max_scan_pages, 20)
        query_lower = (query or "").strip().lower()
        status_lower = (status or "").strip().lower()
        matches: list[dict[str, Any]] = []

        for page in range(1, pages + 1):
            payload = await self.client.list_sales_orders(page=page, per_page=per_page)
            raw_orders = payload.get("salesorders") or []
            for raw in raw_orders:
                order = self.normalize_order(raw)
                if status_lower and str(order.get("status") or "").lower() != status_lower:
                    continue
                if query_lower:
                    haystack = " ".join(
                        str(order.get(key) or "")
                        for key in (
                            "salesorder_number",
                            "reference_number",
                            "customer_name",
                            "customer_id",
                        )
                    ).lower()
                    if query_lower not in haystack:
                        continue
                matches.append(order)

            if not _has_more(payload, raw_orders, per_page):
                break

        return {
            "salesorders": matches,
            "count": len(matches),
            "scan_bounded_to_pages": pages,
        }

    async def find_open_orders_for_low_stock(
        self,
        *,
        threshold_override: float | None = None,
        max_pages: int | None = None,
        max_orders: int | None = None,
    ) -> dict[str, Any]:
        pages = min(max_pages or self.settings.zoho_max_scan_pages, 20)
        order_limit = min(
            max_orders or self.settings.zoho_max_correlation_orders,
            200,
        )

        low_result = await self.list_low_stock_items(
            threshold_override=threshold_override,
            max_pages=pages,
        )
        low_items = {
            item["item_id"]: item
            for item in low_result["items"]
            if item.get("item_id")
        }
        if not low_items:
            return {
                "low_stock_items": [],
                "order_exposure": [],
                "orders_inspected": 0,
                "note": "No low-stock items found in the bounded inventory scan.",
            }

        exposure: list[dict[str, Any]] = []
        inspected = 0

        for page in range(1, pages + 1):
            payload = await self.client.list_sales_orders(page=page, per_page=100)
            summaries = payload.get("salesorders") or []

            for summary in summaries:
                status = str(summary.get("status") or "").lower()
                if status in CLOSED_ORDER_STATUSES:
                    continue
                if inspected >= order_limit:
                    break

                order_id = str(summary.get("salesorder_id") or "")
                if not order_id:
                    continue

                details_payload = await self.client.get_sales_order(order_id)
                order = (
                    details_payload.get("salesorder")
                    or details_payload.get("sales_order")
                    or {}
                )
                inspected += 1

                affected_lines = []
                for line in order.get("line_items") or []:
                    item_id = str(line.get("item_id") or "")
                    if item_id in low_items:
                        affected_lines.append(
                            {
                                "item_id": item_id,
                                "name": line.get("name"),
                                "ordered_quantity": line.get("quantity"),
                                "quantity_shipped": line.get("quantity_shipped"),
                                "inventory": low_items[item_id],
                            }
                        )

                if affected_lines:
                    exposure.append(
                        {
                            "salesorder": self.normalize_order(order or summary),
                            "affected_line_items": affected_lines,
                        }
                    )

            if inspected >= order_limit or not _has_more(payload, summaries, 100):
                break

        return {
            "low_stock_items": list(low_items.values()),
            "order_exposure": exposure,
            "orders_inspected": inspected,
            "order_scan_limit": order_limit,
            "page_scan_limit": pages,
        }
