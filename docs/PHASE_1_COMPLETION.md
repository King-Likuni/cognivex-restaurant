# Phase 1 Completion

Phase 1 establishes the backend foundation for a real Cognivex restaurant product. The goal is not a full commercial platform yet; it is a stable base that can safely accept Phase 2 features.

## Completed Scope

- Multi-tenant restaurant and branch model.
- Role-based authentication and authorization.
- Restaurant-scoped menu categories and items.
- Cashier order creation with branch/day numbering.
- Cash payment confirmation with payment records and payment events.
- Kitchen workflow from queued to preparing to ready.
- Collection and uncollected terminal order states.
- Daily sales reporting for collected paid orders.
- Audit logs for money-sensitive and terminal workflow actions.
- Deterministic order status history with per-order sequencing.
- Alembic migrations for local and future database setup.
- Automated unit, integration, and live smoke coverage.

## Quality Gate

Before treating Phase 1 as healthy, run this from `backend`:

```powershell
.\venv\Scripts\python.exe scripts\quality_gate.py
```

When the local API is running, use the fuller gate:

```powershell
.\venv\Scripts\python.exe scripts\quality_gate.py --with-smoke
```

The gate must pass before Phase 2 changes are merged into the working baseline.

## Known Non-Blocking Warnings

The test suite currently reports upstream deprecation warnings from FastAPI/Starlette test tooling. They do not block Phase 2, but should be revisited when dependency versions are upgraded.

## Phase 2 Entry Criteria

Phase 2 can start when:

- `alembic current` reports the latest revision.
- The quality gate passes.
- The smoke test passes against the running API.
- Swagger login and protected endpoints work for the seeded owner.

## Recommended Phase 2 Direction

Start Phase 2 with inventory service endpoints because the database extension points already exist:

- Ingredients.
- Stock locations.
- Stock movements.
- Menu item recipe links.
- Order-driven stock consumption.

Keep inventory ledger-based and append-only. Do not overwrite historical stock movements.
