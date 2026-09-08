# Phase 5 Completion

Phase 5 adds the first operational frontend for the Cognivex Restaurant Platform.

## Delivered

- Vite React TypeScript app in `frontend/`
- Token-based login against the live FastAPI backend
- Persisted local session with sign-out
- Role-aware navigation for owner, manager, cashier, and kitchen users
- Cashier screen for menu browsing, cart building, order creation, cash confirmation, sandbox remote payment initiation, customer status links, and pickup handover
- Kitchen screen connected to the backend WebSocket event stream
- Customer-safe status page using short-lived order-scoped tokens
- Playwright browser E2E coverage for the cashier, kitchen, pickup, and dashboard journey
- Inventory screen for ingredients, stock locations, receiving stock, recipe links, and balances
- Dashboard screen for daily revenue, order counts, payment summaries, and top items
- Shared API client and money formatting helpers
- Responsive operational UI with stable controls and restrained styling

## Quality Gate

From `frontend/`:

```powershell
npm install
npm run lint
npm run build
npm run test:e2e
```

The frontend build was verified successfully against the current source. The local development server runs at:

```text
http://127.0.0.1:3000/
```

## Backend Dependency

Keep the backend running before using the console:

```powershell
cd backend
.\venv\Scripts\uvicorn.exe app.main:app --reload
```

The frontend expects the API at `http://127.0.0.1:8000` by default. Override it with `VITE_API_BASE_URL` when needed.

## Operational Handover

- Kitchen staff move paid orders through `QUEUED`, `PREPARING`, and `READY`.
- Cashiers watch the pickup desk for `READY` orders.
- Cashiers mark food `COLLECTED` only after handing it to the customer.
- Missed pickups can be marked `UNCOLLECTED`.
- Revenue, top items, and recipe stock consumption finalize when an order is collected.
