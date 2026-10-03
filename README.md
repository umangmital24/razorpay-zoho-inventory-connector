# Razorpay Zoho Inventory Connector

A read-only, production-minded private connector that exposes Zoho Inventory data to an AI agent through MCP (Model Context Protocol).

Built for the Razorpay Forward-Deployed Engineer, Agent Studio assignment.

## What the agent can do

- Discover accessible Zoho Inventory organizations.
- List, search, and retrieve inventory items.
- Identify low-stock items using Zoho stock/reorder fields or an explicit threshold.
- List and retrieve sales orders.
- Search sales orders by customer, order number, reference number, or status.
- Correlate low-stock items with open sales orders in a bounded, rate-limit-aware workflow.

The connector is intentionally **read-only**. It does not create, update, delete, approve, or fulfill orders or inventory.

## Architecture

```text
Agent / MCP Client
       |
       v
MCP tools (read-only)
       |
       v
ZohoInventoryService
       |
       v
ZohoInventoryClient
  |             |
  |             +--> retry/backoff + 429 handling
  +--> OAuth token provider / refresh
       |
       v
Zoho Inventory REST API
```

## Zoho API scopes

Use the least-privilege read scopes:

```text
ZohoInventory.settings.READ
ZohoInventory.items.READ
ZohoInventory.salesorders.READ
```

## Setup

### 1. Install

Python 3.11+ is recommended.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 2. Register a Zoho OAuth client

Create a client in the Zoho API Console and add a redirect URI, for example:

```text
http://localhost:8080/callback
```

Zoho has multiple data centers. Configure the account/API domains for the account you are connecting:

| Data center | Accounts base | API base |
|---|---|---|
| US / .com | `https://accounts.zoho.com` | `https://www.zohoapis.com` |
| India / .in | `https://accounts.zoho.in` | `https://www.zohoapis.in` |
| EU / .eu | `https://accounts.zoho.eu` | `https://www.zohoapis.eu` |
| AU / .com.au | `https://accounts.zoho.com.au` | `https://www.zohoapis.com.au` |
| CA / .ca | `https://accounts.zohocloud.ca` | `https://www.zohoapis.ca` |

### 3. Generate OAuth consent URL

Copy the sample environment file first:

```bash
cp .env.example .env
```

Set `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REDIRECT_URI`, and the correct data-center URLs in your local `.env`.

Then:

```bash
python scripts/oauth_setup.py auth-url
```

Open the generated URL, approve the read-only scopes, and copy the returned `code`.

Exchange it immediately (Zoho authorization codes are short-lived):

```bash
python scripts/oauth_setup.py exchange --code "<authorization-code>"
```

Store the returned refresh token in your local `.env` as `ZOHO_REFRESH_TOKEN`.

> Never commit the `.env` file, access token, refresh token, client secret, or customer data.

### 4. Find the organization ID

With OAuth configured:

```bash
python examples/demo.py organizations
```

Copy the target `organization_id` into `.env` as `ZOHO_ORGANIZATION_ID`.

### 5. Run the MCP server

```bash
python -m zoho_inventory_connector.mcp_server
```

The server uses MCP stdio transport by default.

## Example agent workflow

Merchant asks:

> Which products are low on stock, and do we have open orders that depend on them?

The agent can call:

1. `list_low_stock_items`
2. `find_open_orders_for_low_stock`
3. Return a grounded summary with item IDs, stock levels, order IDs, and customers.

The correlation workflow is bounded by configurable page/order limits to avoid accidentally scanning an entire merchant account or exhausting API quotas.

## CLI demo

```bash
python examples/demo.py items --search "coffee"
python examples/demo.py low-stock
python examples/demo.py orders
python examples/demo.py order-search --query "Acme"
python examples/demo.py risk
```

## MCP tools

| Tool | Purpose |
|---|---|
| `list_organizations` | List organizations available to the authorized user |
| `list_items` | Paginated item listing |
| `search_items` | Search inventory by Zoho `search_text` |
| `get_item` | Retrieve one item |
| `list_low_stock_items` | Find items at/below reorder level or explicit threshold |
| `list_sales_orders` | Paginated sales-order listing |
| `get_sales_order` | Retrieve one sales order |
| `search_sales_orders` | Bounded local search over order summaries |
| `find_open_orders_for_low_stock` | Correlate low stock with open order line items |

See [docs/MCP_TOOL_SPEC.md](docs/MCP_TOOL_SPEC.md) for schemas and behavior.

## Reliability and guardrails

- **Read-only by design:** no mutation tools are exposed.
- **Least-privilege OAuth:** only settings/items/sales-order READ scopes are requested.
- **Automatic token refresh:** short-lived access tokens are refreshed with the OAuth refresh token.
- **401 recovery:** one forced refresh is attempted before failing.
- **Rate-limit handling:** HTTP 429 and transient 5xx errors use bounded exponential backoff and honor `Retry-After` when present.
- **Bounded scans:** agent-side search/correlation has explicit page/order limits.
- **No secrets in source:** configuration is environment-based and `.env` is gitignored.
- **Normalized errors:** upstream auth/rate-limit/API failures are surfaced as typed connector errors rather than hallucinated data.

## Testing

```bash
ruff check .
pytest -q
```

Tests use mocked HTTP/fake service dependencies; CI does not require Zoho credentials.

## CI

GitHub Actions runs linting and tests on every push and pull request.

## Assumptions and limitations

See [LIMITATIONS.md](LIMITATIONS.md).

## Long-term production improvements

For a production merchant deployment I would add encrypted tenant-specific credential storage, a durable distributed rate limiter, per-tenant audit logs, observability/SLIs, webhook or CDC-style sync for large catalogs, stronger field-level data minimization, and explicit human approval before any future write-capable tools are enabled.
