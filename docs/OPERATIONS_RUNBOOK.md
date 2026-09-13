# Cognivex Operations Runbook

This runbook covers the zero-budget production path: Vercel frontend, Render backend,
and Neon PostgreSQL.

## Daily Owner Routine

1. Open the owner Dashboard.
2. Confirm the selected branch and business date.
3. Download these CSV files after close of business:
   - Owner report
   - Orders
   - Payments
   - Audit logs
   - Inventory balances
4. Store exports in a dated folder, for example:
   `Cognivex Backups/Chicken Spot/2026-09-13/`.
5. Confirm total revenue in the Payments export matches the mobile-money and cash records.

## Database Backups

Neon should be treated as the source of truth for operational data.

Recommended rhythm:

- Daily: owner CSV exports after close of business.
- Weekly: Neon database branch or snapshot before major changes.
- Before every production release: confirm there is a recent Neon restore point.

Minimum data to preserve:

- Restaurants and branches
- Staff users and role assignments
- Menus and prices
- Orders and order items
- Payments and payment events
- Audit logs
- Inventory ingredients, stock movements, and recipe links

## Restore Checklist

Use this when data is lost, corrupted, or a migration causes production problems.

1. Stop new operational use of the affected restaurant account.
2. Identify the last good Neon restore point or branch.
3. Restore into a separate Neon branch first.
4. Point a staging Render service at the restored branch.
5. Run the staging smoke test.
6. Confirm owner login, QR order creation, payment proof confirmation, collection, and reports.
7. Only then promote the restored database connection to production.

Never test a restore directly against the production database.

## Deployment Rollback

### Backend on Render

1. Open Render.
2. Go to `cognivex-restaurant-api`.
3. Open Deploys.
4. Select the last known good deploy.
5. Roll back or redeploy that version.
6. Check:
   - `/health`
   - `/ready`
   - Login
   - Owner Dashboard
   - QR order flow

### Frontend on Vercel

1. Open Vercel.
2. Go to the Cognivex project.
3. Open Deployments.
4. Promote or redeploy the last known good frontend deployment.
5. Confirm the frontend points to the correct Render API URL.

## Payment Incident Checklist

Use this when Orange Money or Pay2Cell proof confirmation does not behave as expected.

1. Confirm the order is `READY`.
2. Confirm the order is in Payment Queue, not Pickup Desk.
3. Ask the customer to show proof with the system-created reference.
4. Enter the reference exactly as shown.
5. If rejected, check Audit for `Mobile Transfer Proof Rejected`.
6. Do not mark the order collected until the matching proof has been accepted.
7. Compare the Payments export against mobile-money records at close of business.

## Database Unavailable

If `/ready` returns an error:

1. Check Neon project status.
2. Check Render environment variable `DATABASE_URL`.
3. Restart the Render service.
4. If still failing, restore a recent Neon branch and test in staging.

## Release Checklist

Before pushing a release:

1. Run:
   `.\scripts\quality_gate.ps1 -WithSmoke -WithE2E`
2. Confirm all tests pass.
3. Confirm migrations are at Alembic head.
4. Push to GitHub.
5. Confirm Vercel deployment.
6. Redeploy Render if auto-deploy is off.
7. Test:
   - Owner login
   - Cashier order
   - QR customer order
   - Kitchen ready flow
   - Mobile transfer proof confirmation
   - Pickup collection
   - Owner report downloads
