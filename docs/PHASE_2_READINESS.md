# Phase 2 Readiness Checklist

## Keep Stable

- Modular monolith package layout.
- Tenant and branch scoping on operational records.
- Order state machine and status history.
- Payment provider adapter boundary.
- Audit trail for money and status changes.
- Daily branch order numbering.

## Phase 2 Modules

- Inventory stock locations.
- Ingredients and units.
- Menu item recipes.
- Stock movements.
- Order item inventory consumption.
- Payment provider implementations for Orange Money and FNB.
- WebSocket kitchen/cashier/customer status channels.

## Before Pilot

Completed:

- Cashier order to collected sale journey tests.
- HTTP smoke test covering cashier order, cash confirmation, kitchen ready flow, collection, and daily sales reporting.
- Tenant isolation integration tests for cross-restaurant reads, writes, payments, kitchen actions, and reports.
- Payment and order edge-case tests for wrong amounts, duplicate payment confirmation, unpaid kitchen transitions, sold-out items, and daily numbering boundaries.
- Audit/history tests for payment events, audit logs, and deterministic order status history.
- Backend quality gate for compile, format, lint, tests, migration status, and optional live smoke testing.
- Inventory endpoints for ingredients, stock locations, recipe items, movements, and balances.
- Order collection stock consumption for recipe-backed menu items.
- Daily order numbering concurrency test and Postgres transaction advisory lock.
- HMAC webhook signature helper for provider callbacks.
- Staging and production environment guardrails for secrets, database password, and CORS.
- Remote payment initiation endpoint and signed/idempotent provider webhook processor.

Still needed before a real pilot:

- Add real Orange Money and FNB provider credentials and API adapters.
