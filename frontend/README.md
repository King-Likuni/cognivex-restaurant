# Frontend

React operations console for the Cognivex Restaurant Platform.

## Local Setup

```powershell
npm install
npm run dev
```

The app expects the backend API at `http://127.0.0.1:8000` by default.

To override it, create `frontend/.env`:

```powershell
VITE_API_BASE_URL="http://127.0.0.1:8000"
```

## Available Screens

- Cashier: create orders, confirm cash, initiate remote payments, generate customer status links, and close pickup handover.
- Kitchen: live branch queue, start preparing, mark ready.
- Customer status: token-scoped live status page for a single order.
- Inventory: create ingredients, stock locations, receive stock, link recipes, review balances.
- Dashboard: daily sales, order counts, top items, payment summaries.

## Quality Gate

```powershell
npm run lint
npm run build
npm run test:e2e
```

The E2E tests require the backend to be running at `http://127.0.0.1:8000`.
