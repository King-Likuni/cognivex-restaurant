# Zero-Budget Deployment

This is the recommended free hosting path for the current Cognivex pilot:

- Neon free Postgres for the database.
- Render free web service for the FastAPI backend.
- Vercel free static deployment for the Vite frontend.

Render free web services can sleep after inactivity, so the first request after a quiet period may be slow. That is acceptable for a pilot, but not for a busy restaurant launch.

## 1. Generate Secrets

From the project root:

```powershell
.\scripts\generate_deployment_secrets.ps1
```

Keep the generated values private. Do not paste them into committed files.

## 2. Create Neon Postgres

Create a Neon project and copy the pooled PostgreSQL connection string.

Use it as:

```text
DATABASE_URL=<neon pooled connection string with sslmode=require>
```

Do not use the local Docker database for hosted production.

## 3. Deploy Backend on Render

Render can read the root `render.yaml` blueprint. It deploys only the backend API.

Use these required environment variables in Render:

```text
DATABASE_URL=<Neon pooled connection string>
PAYMENT_WEBHOOK_SECRET=<generated value>
WHATSAPP_WEBHOOK_VERIFY_TOKEN=<generated value>
WHATSAPP_WEBHOOK_APP_SECRET=<generated value>
INITIAL_ADMIN_PASSWORD=<generated value>
BACKEND_CORS_ORIGINS=["https://your-vercel-app.vercel.app"]
```

The blueprint already sets:

```text
ENVIRONMENT=production
ENABLE_SAMPLE_DATA=false
RUN_MIGRATIONS=1
RUN_INITIAL_DATA=0
WEB_CONCURRENCY=1
```

After deploy, confirm:

```powershell
Invoke-RestMethod https://your-render-api.onrender.com/health
Invoke-RestMethod https://your-render-api.onrender.com/ready
```

## 4. Create First Admin User

For the first deployment only, set this in Render:

```text
RUN_INITIAL_DATA=1
```

Redeploy once, confirm login works, then change it back:

```text
RUN_INITIAL_DATA=0
```

This avoids reseeding on every deploy.

## 5. Deploy Frontend on Vercel

Create a Vercel project using the `frontend` directory as the project root.

Use:

```text
Framework Preset: Vite
Build Command: npm run build
Output Directory: dist
```

Set this Vercel environment variable:

```text
VITE_API_BASE_URL=https://your-render-api.onrender.com
```

The frontend includes `frontend/vercel.json` so browser refresh works on routes like `/order/...` and `/status/...`.

## 6. Update Backend CORS

After Vercel gives you the final frontend URL, update Render:

```text
BACKEND_CORS_ORIGINS=["https://your-vercel-app.vercel.app"]
```

Redeploy the backend after changing CORS.

## 7. Smoke-Test Hosted Deployment

Set temporary PowerShell variables for the hosted URLs and credentials:

```powershell
$env:STAGING_BACKEND_URL="https://your-render-api.onrender.com"
$env:STAGING_FRONTEND_URL="https://your-vercel-app.vercel.app"
$env:STAGING_ADMIN_EMAIL="admin@cognivex.com"
$env:STAGING_ADMIN_PASSWORD="<production admin password>"
$env:STAGING_OWNER_EMAIL="owner@chickenspot.com"
$env:STAGING_OWNER_PASSWORD="<owner password if sample data is enabled>"
$env:STAGING_PAYMENT_WEBHOOK_SECRET="<payment webhook secret>"
```

Then run:

```powershell
.\scripts\smoke_staging.ps1
```

For a production database with no sample restaurant, first create a real restaurant, branch, owner, menu category, menu item, ingredient, and stock location through the API or admin UI. The smoke script expects the seeded `Chicken Spot` tenant unless you pass alternate names and credentials.

## Rollback

If a deployment breaks:

- Render: redeploy the previous successful backend deploy.
- Vercel: promote the previous successful frontend deployment.
- Neon: avoid destructive schema changes until migrations are verified locally and in staging.

## References

- Render Blueprint YAML: https://render.com/docs/blueprint-spec
- Render Docker deployment: https://render.com/docs/docker
- Vercel Vite deployment: https://vercel.com/docs/frameworks/frontend/vite
- Vercel rewrites: https://vercel.com/docs/routing/rewrites
