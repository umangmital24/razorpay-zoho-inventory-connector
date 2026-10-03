# Assumptions and limitations

## Current scope

This submission is deliberately read-only. It supports organization discovery, inventory reads, sales-order reads, bounded search, low-stock detection, and a cross-entity correlation workflow.

It does **not** expose create/update/delete/approve/fulfill operations.

## Assumptions

1. The merchant has a Zoho Inventory account and can register/authorize an OAuth client.
2. The configured OAuth client receives only the documented read scopes required by this connector.
3. `ZOHO_ORGANIZATION_ID` belongs to the authenticated account.
4. The connector runs in one Zoho data center at a time; the base URLs are explicit configuration.
5. Low-stock detection prefers `actual_available_stock`, then `available_stock`, then `stock_on_hand`. Without an explicit threshold it uses Zoho's `reorder_level`.
6. Sales-order text search is intentionally implemented as a bounded scan of documented list results because the core list endpoint does not document a general `search_text` parameter.

## Limitations

### Bounded, not exhaustive, cross-order search

`search_sales_orders` and `find_open_orders_for_low_stock` cap the number of pages/orders inspected. This protects merchant API quota and prevents an agent prompt from triggering an unbounded account scan.

For a very large merchant, results can therefore be partial. The response includes the applied bounds so the agent should not represent them as exhaustive.

### Low-stock fields can vary by inventory configuration

Zoho accounts with warehouses, batches, locations, or variants can have richer stock semantics than a single top-level stock number. This connector returns a useful default but a production deployment should define merchant-specific stock semantics.

### No webhook/local index

The assignment implementation reads Zoho on demand. For large catalogs or high request volume, a production connector should maintain a permission-aware local index fed by supported webhooks/scheduled incremental sync, then use Zoho as the source of truth for confirmation.

### Rate limiting is process-local

The connector retries HTTP 429 and transient 5xx errors with bounded exponential backoff. It does not implement a distributed token bucket across multiple connector replicas.

### Token storage

Refresh tokens are read from environment variables for the assignment. Production credentials should live in a KMS-backed/managed secrets store, encrypted per tenant, with rotation and access auditing.

### No write operations

This is intentional. If write tools were introduced, they should have:
- narrower write scopes,
- explicit operation allowlists,
- idempotency controls,
- amount/quantity limits where relevant,
- actor and tenant audit logs,
- preview/dry-run output,
- human approval for high-impact actions.

## Appropriate long-term fix

For a multi-merchant Agent Studio deployment, I would turn the connector into a tenant-aware integration service with encrypted OAuth credential storage, distributed rate limiting, per-tenant audit logs, tracing/metrics, a durable sync/index for large datasets, and policy-enforced write tools requiring explicit approvals.
