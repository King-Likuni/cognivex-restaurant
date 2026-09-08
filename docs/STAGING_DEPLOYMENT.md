# Staging Deployment

Staging is the pre-production environment used to test Cognivex with production-like settings before a real deployment.

## What Staging Should Prove

- The backend starts with non-development settings.
- Secrets and default passwords are not accepted.
- Migrations run successfully.
- The API can reach PostgreSQL and Redis.
- The frontend can call the staging API.
- Smoke and browser E2E tests pass against deployed URLs.

## Local Container Staging

From the project root:

```powershell
copy .env.staging.example .env.staging
```

Edit `.env.staging` before running anything. Replace every `change-this...` value with a real staging value.

Start the staging stack:

```powershell
docker compose --env-file .env.staging -f docker-compose.staging.yml up --build -d
```

The compose file defaults to `.env.staging`. To validate the template without creating a real staging env file:

```powershell
$env:STAGING_ENV_FILE=".env.staging.example"
docker compose --env-file .env.staging.example -f docker-compose.staging.yml config
Remove-Item Env:\STAGING_ENV_FILE
```

Check containers:

```powershell
docker compose --env-file .env.staging -f docker-compose.staging.yml ps
```

Backend readiness:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8011/ready
```

Frontend:

```text
http://127.0.0.1:3011
```

Stop staging:

```powershell
docker compose --env-file .env.staging -f docker-compose.staging.yml down
```

Stop staging and remove staging database volume:

```powershell
docker compose --env-file .env.staging -f docker-compose.staging.yml down -v
```

## Seed Data

By default, `.env.staging.example` sets:

```text
ENABLE_SAMPLE_DATA=false
RUN_INITIAL_DATA=0
```

That is the safest default. For a disposable local staging rehearsal, you may enable sample data only after changing the seed passwords:

```text
RUN_INITIAL_DATA=1
ENABLE_SAMPLE_DATA=true
INITIAL_ADMIN_PASSWORD=<strong password>
INITIAL_OWNER_PASSWORD=<strong password>
```

Never deploy staging or production with `adminpassword` or `ownerpassword`.

## Staging Smoke Test

Run API smoke checks against a staging backend:

```powershell
.\scripts\smoke_staging.ps1
```

The script loads `.env.staging` automatically. It validates cashier order flow, public QR ordering, WhatsApp-channel ordering, remote payment webhooks, customer status, and frontend E2E.

For API-only staging checks:

```powershell
.\scripts\smoke_staging.ps1 `
  -BackendUrl "https://api-staging.example.com" `
  -AdminEmail "admin@cognivex.com" `
  -AdminPassword "<staging admin password>" `
  -OwnerEmail "owner@chickenspot.com" `
  -OwnerPassword "<staging owner password>" `
  -PaymentWebhookSecret "<staging payment webhook secret>" `
  -SkipE2E
```

## Deployment Checklist

- `.env.staging` exists and is not committed.
- `ENVIRONMENT=staging`.
- `SECRET_KEY`, `PAYMENT_WEBHOOK_SECRET`, and WhatsApp secrets are strong and unique.
- `POSTGRES_PASSWORD` is not a placeholder.
- `BACKEND_CORS_ORIGINS` contains the exact staging frontend URL.
- `VITE_API_BASE_URL` points to the staging backend URL.
- `/health` returns process health.
- `/ready` returns database readiness.
- Migrations are at Alembic head.
- API smoke test passes.
- Playwright E2E passes against the staging frontend.
