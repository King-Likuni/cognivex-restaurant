# Phase 6 Deployment Readiness

Phase 6 prepares the project for staging and production-style operation.

## Delivered

- Backend Dockerfile with healthcheck and deployment entrypoint
- Frontend Dockerfile with Nginx static serving and SPA fallback
- Staging Docker Compose file for backend, frontend, PostgreSQL, and Redis
- `.env.staging.example` template
- Staging smoke-test script
- `/ready` endpoint for database readiness
- `DATABASE_URL` support for managed database providers
- Stronger staging/production secret validation
- Safer seed-data behavior for staging and production
- Docker ignore files for smaller, cleaner build contexts
- Deployment and staging runbook
- Public QR/customer ordering API and frontend route
- WhatsApp-channel order contract for future WhatsApp Business webhook integration

## Quality Checks

Run the full local gate before creating staging artifacts:

```powershell
.\scripts\quality_gate.ps1 -WithSmoke -WithE2E
```

The root quality gate uses temporary no-reload local services for live checks: backend port `8010` and frontend port `3010`.

The smoke and E2E checks include customer-facing ordering via:

```text
/order/restaurants/{restaurant_id}/branches/{branch_id}
```

WhatsApp-channel ordering is covered at the API contract level. Live WhatsApp messaging requires Meta WhatsApp Business credentials before production use.

Validate staging compose syntax without creating secrets:

```powershell
$env:STAGING_ENV_FILE=".env.staging.example"
docker compose --env-file .env.staging.example -f docker-compose.staging.yml config
Remove-Item Env:\STAGING_ENV_FILE
```

## Next Step

Choose the actual staging host, create real staging secrets, deploy the staging stack, then run:

```powershell
.\scripts\smoke_staging.ps1 -BackendUrl "<staging-api-url>" -FrontendUrl "<staging-frontend-url>" -AdminEmail "<admin-email>" -AdminPassword "<admin-password>" -OwnerEmail "<owner-email>" -OwnerPassword "<owner-password>" -PaymentWebhookSecret "<webhook-secret>"
```
