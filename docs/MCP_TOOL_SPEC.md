# MCP tool specification

All tools are read-only. IDs are returned as strings to avoid loss of precision in agent runtimes.

## `list_organizations`

**Purpose:** discover Zoho organizations available to the OAuth principal.

**Input:** none.

**Output:** organization ID, name, default flag, currency, and timezone.

**Scope:** `ZohoInventory.settings.READ`.

---

## `list_items`

**Input**
- `page: int = 1`
- `per_page: int = 100` (clamped to 1..200)

**Output:** normalized item summaries plus Zoho page context when available.

**Scope:** `ZohoInventory.items.READ`.

---

## `search_items`

**Input**
- `query: str`
- `page: int = 1`
- `per_page: int = 100`

Uses Zoho's documented `search_text` on the items list endpoint.

**Scope:** `ZohoInventory.items.READ`.

---

## `get_item`

**Input**
- `item_id: str`

Returns a normalized item plus the source item object for fields not covered by the normalized schema.

**Scope:** `ZohoInventory.items.READ`.

---

## `list_low_stock_items`

**Input**
- `threshold_override: float | null`
- `max_pages: int | null`

Without an override, compares available stock against Zoho's `reorder_level`. The scan is bounded.

**Scope:** `ZohoInventory.items.READ`.

---

## `list_sales_orders`

**Input**
- `page: int = 1`
- `per_page: int = 100`

Returns normalized sales-order summaries.

**Scope:** `ZohoInventory.salesorders.READ`.

---

## `get_sales_order`

**Input**
- `salesorder_id: str`

Returns order metadata and line items.

**Scope:** `ZohoInventory.salesorders.READ`.

---

## `search_sales_orders`

**Input**
- `query: str | null`
- `status: str | null`
- `max_pages: int | null`

Performs a bounded local filter over documented list results. Query matching covers order number, reference number, customer name, and customer ID.

The result includes `scan_bounded_to_pages` so an agent does not overstate completeness.

**Scope:** `ZohoInventory.salesorders.READ`.

---

## `find_open_orders_for_low_stock`

**Input**
- `threshold_override: float | null`
- `max_pages: int | null`
- `max_orders: int | null`

Workflow primitive:
1. discover low-stock item IDs;
2. list a bounded set of sales orders;
3. skip closed/fulfilled/void/cancelled orders;
4. retrieve order details;
5. correlate order line-item IDs with low-stock item IDs.

The response reports both page and order inspection limits.

**Scopes:**
- `ZohoInventory.items.READ`
- `ZohoInventory.salesorders.READ`

## Error contract

The connector raises explicit errors rather than returning fabricated data:

- `AuthenticationError`: OAuth token/auth failure.
- `RateLimitError`: 429 persisted after bounded retries.
- `ZohoAPIError`: upstream API/non-JSON/unavailable error.
- `ValueError`: invalid or missing local tool input/configuration.

## Mutation policy

No tool performs POST/PUT/PATCH/DELETE operations against Zoho Inventory. A future write-capable connector should expose writes separately and require policy checks and human approval for high-impact actions.
