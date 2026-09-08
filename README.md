# Cognivex Restaurant Platform

Modular, multi-tenant POS and restaurant management platform.

## Architecture

- **Backend:** FastAPI, PostgreSQL, Redis, SQLAlchemy 2
- **Frontend:** React, Vite, TypeScript
- **Infrastructure:** Docker Compose

## Product Docs

- [Architecture](docs/ARCHITECTURE.md)
- [Database ERD](docs/DATABASE_ERD.md)
- [MVP Specification](docs/MVP_SPEC.md)
- [API Contracts](docs/API_CONTRACTS.md)
- [Development Workflow](docs/DEVELOPMENT_WORKFLOW.md)
- [Staging Deployment](docs/STAGING_DEPLOYMENT.md)
- [Zero-Budget Deployment](docs/ZERO_BUDGET_DEPLOYMENT.md)
- [Phase 1 Completion](docs/PHASE_1_COMPLETION.md)
- [Phase 2 Completion](docs/PHASE_2_COMPLETION.md)
- [Phase 3 Completion](docs/PHASE_3_COMPLETION.md)
- [Phase 4 Completion](docs/PHASE_4_COMPLETION.md)
- [Phase 5 Completion](docs/PHASE_5_COMPLETION.md)
- [Phase 6 Deployment Readiness](docs/PHASE_6_DEPLOYMENT_READINESS.md)
- [Phase 2 Readiness](docs/PHASE_2_READINESS.md)

## Quickstart

1. Start the local stack:

   ```powershell
   .\scripts\dev_start.ps1
   ```

2. Check service status:

   ```powershell
   .\scripts\dev_status.ps1
   ```

3. Run the quality gate:

   ```powershell
   .\scripts\quality_gate.ps1 -WithSmoke
   ```

4. Stop local services:

   ```powershell
   .\scripts\dev_stop.ps1
   ```

Manual startup is still available when needed:

1. Spin up the database and cache:

   ```bash
   docker-compose up -d
   ```

2. Set up the backend (see `backend/README.md`)
3. Set up the frontend (see `frontend/README.md`)

## Frontend Screens

- Cashier operations
- Kitchen queue
- Inventory management
- Owner dashboard
- Customer QR ordering
- Customer order status tracking
