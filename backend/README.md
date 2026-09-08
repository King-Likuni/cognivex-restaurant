# Backend

FastAPI service for the Cognivex Restaurant Platform modular monolith.

## Local Setup

1. Copy the root environment sample:

   ```bash
   copy ..\.env.example ..\.env
   ```

2. Start infrastructure from the repository root:

   ```bash
   docker compose up -d
   ```

3. Create and activate a virtual environment:

   ```bash
   py -3.12 -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements-dev.txt
   ```

4. Run migrations and seed local data:

   ```bash
   alembic upgrade head
   python -m app.initial_data
   ```

5. Start the API:

   ```bash
   uvicorn app.main:app --reload
   ```

## Smoke Test

With Uvicorn running, test the first protected API journey:

```powershell
.\venv\Scripts\python.exe scripts\smoke_test_api.py
```

The smoke test logs in, finds the seeded restaurant and branch, creates a menu category, creates a menu item, creates a cashier order, confirms cash payment, moves the order through the kitchen board to ready, collects it, and checks the daily sales report.

## Automated Tests

Run the unit and integration suite:

```powershell
.\venv\Scripts\python.exe -m pytest
```

Integration tests use `TEST_DATABASE_URL` when set, otherwise they use the local development database URL and create an isolated temporary PostgreSQL schema for each test session.

## Quality Gate

Before moving to a new feature slice, run the backend quality gate:

```powershell
.\venv\Scripts\python.exe scripts\quality_gate.py
```

To format and apply safe lint fixes first:

```powershell
.\venv\Scripts\python.exe scripts\quality_gate.py --fix
```

With Uvicorn already running, include the live API smoke test:

```powershell
.\venv\Scripts\python.exe scripts\quality_gate.py --with-smoke
```

The gate compiles Python modules, checks formatting, runs Ruff linting, runs the automated tests, checks the current Alembic revision, and optionally runs the smoke test against `http://127.0.0.1:8000`.

## Boundaries

- `auth`: users, roles, authentication, and authorization.
- `tenants`: restaurants, branches, and restaurant settings.
- `menu`: categories, menu items, availability, and future modifiers.
- `orders`: order lifecycle, numbering, and kitchen state transitions.
- `payments`: provider adapter contracts, payment records, and callbacks.
- `inventory`: Phase 2 stock, recipe, and consumption models.
- `audit`: money-sensitive and workflow-sensitive audit events.

Operational records should carry `restaurant_id`; branch-scoped records should also carry `branch_id`.
