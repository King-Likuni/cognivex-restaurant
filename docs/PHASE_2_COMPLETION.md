# Phase 2 Completion

Phase 2 adds the operational inventory foundation and the hardening needed before external integrations.

## Completed Scope

- Inventory ingredients and units.
- Branch stock locations.
- Append-only stock movements.
- Stock balance calculation from the movement ledger.
- Menu item recipe links.
- Automatic recipe-based stock consumption when an order is collected.
- Audit logs for manual stock movements and automatic order stock consumption.
- Concurrency-safe daily order numbering with a Postgres transaction advisory lock.
- Integration coverage for stock setup, stock consumption, insufficient stock rejection, and concurrent order creation.
- HMAC webhook signature helpers for future payment and WhatsApp callbacks.
- Staging and production configuration guardrails for secrets, webhook secrets, database password, and CORS.
- Smoke test coverage for inventory setup, recipe linking, order collection, and resulting stock balance.

## Current Quality Gate

From `backend`:

```powershell
.\venv\Scripts\python.exe scripts\quality_gate.py
```

With Uvicorn running:

```powershell
.\venv\Scripts\python.exe scripts\smoke_test_api.py
```

Latest verified result:

- `41 passed`
- Alembic revision: `2d7a5f9c4b11 (head)`
- Live smoke test passed with inventory consumption.

## Remaining Before Pilot

These require provider credentials, frontend consumers, or deployment decisions:

- Orange Money provider implementation.
- FNB payment provider implementation.
- Staging deployment environment.
- Production deployment environment.

## Phase 3 Recommendation

Start with realtime order updates:

- Kitchen board updates after payment, start, ready, collected, and uncollected events.
- Cashier view updates for payment and kitchen status.
- Customer-safe order status channel for QR orders.

Realtime should consume backend workflow events; it should not bypass the existing order state machine.
