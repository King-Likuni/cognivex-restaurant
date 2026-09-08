# Development Workflow

This project has root-level scripts for running the full local stack with repeatable commands.

## Start

From the project root:

```powershell
.\scripts\dev_start.ps1
```

This script:

- Starts Docker Compose services when Docker is available.
- Runs Alembic migrations.
- Seeds local data.
- Installs frontend dependencies when `node_modules` is missing.
- Starts the backend at `http://127.0.0.1:8000`.
- Starts the frontend at `http://127.0.0.1:3000`.
- Writes logs and process metadata under `.dev/`.

Useful options:

```powershell
.\scripts\dev_start.ps1 -SkipDocker
.\scripts\dev_start.ps1 -SkipMigrations -SkipSeed
.\scripts\dev_start.ps1 -BackendPort 8001 -FrontendPort 3001
```

## Status

```powershell
.\scripts\dev_status.ps1
```

This checks tracked process IDs, port listeners, backend health, frontend availability, and Docker Compose status when Docker is accessible.

## Stop

```powershell
.\scripts\dev_stop.ps1
```

This stops only the tracked backend and frontend processes created by `dev_start.ps1`, then stops Docker Compose services. To keep the database and Redis containers running:

```powershell
.\scripts\dev_stop.ps1 -KeepDocker
```

## Quality Gate

```powershell
.\scripts\quality_gate.ps1
```

This runs:

- Backend compile, format check, Ruff lint, pytest, and Alembic current through `backend/scripts/quality_gate.py`.
- Frontend lint.
- Frontend production build.

Include the live API smoke test:

```powershell
.\scripts\quality_gate.ps1 -WithSmoke
```

The root quality gate starts a temporary no-reload backend at `http://127.0.0.1:8010` for smoke/E2E checks, then stops it. This avoids conflicts with a manually running `uvicorn --reload` server on port `8000`.

During frontend-only work:

```powershell
.\scripts\quality_gate.ps1 -SkipBackend
```

During backend-only work:

```powershell
.\scripts\quality_gate.ps1 -SkipFrontend
```

Include browser end-to-end tests:

```powershell
.\scripts\quality_gate.ps1 -WithSmoke -WithE2E
```

The frontend E2E tests create their own temporary menu data through the API, then drive the browser through cashier, kitchen, pickup, and dashboard workflows.
By default, Playwright uses a temporary frontend port at `http://127.0.0.1:3010` during the root quality gate.

## Port Conflicts

If startup reports that a port is already in use:

```powershell
.\scripts\dev_status.ps1
netstat -ano | findstr :8000
netstat -ano | findstr :3000
```

Prefer stopping tracked services with `dev_stop.ps1`. Kill manual/stale processes only after confirming the PID belongs to the local dev server.
