# API Contracts

## Conventions

Base path: `/api/v1`

All authenticated endpoints use bearer tokens unless explicitly marked public.

All operational records include `restaurant_id`. Branch-scoped operations include `branch_id`.

Errors use FastAPI's standard response shape:

```json
{
  "detail": "Human readable error"
}
```

## Auth

### Login

`POST /auth/login`

Form fields:

| Field | Type | Required |
| --- | --- | --- |
| username | email | Yes |
| password | string | Yes |

Response:

```json
{
  "access_token": "jwt",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "owner@example.com",
    "first_name": "Restaurant",
    "last_name": "Owner",
    "is_active": true,
    "role_name": "OWNER",
    "restaurant_id": "uuid"
  }
}
```

### Current User

`GET /auth/me`

Roles: any authenticated active user.

### Create User

`POST /auth/users`

Roles: `OWNER`, `MANAGER`

Request:

```json
{
  "email": "cashier@example.com",
  "password": "strong-password",
  "first_name": "Cashier",
  "last_name": "One",
  "role_name": "CASHIER",
  "restaurant_id": "uuid",
  "branch_ids": ["uuid"]
}
```

Rules:

- `ADMIN` users must not have a restaurant.
- Non-admin users must have a restaurant.
- Branch IDs must belong to the user's restaurant.

## Restaurants and Branches

### Create Restaurant

`POST /restaurants/`

Roles: `ADMIN`

Request:

```json
{
  "name": "Chicken Spot",
  "code": "CS01"
}
```

Response:

```json
{
  "id": "uuid",
  "code": "CS01",
  "name": "Chicken Spot",
  "is_active": true
}
```

Rules:

- `code` is optional at creation, but every restaurant receives a stable code.
- Restaurant code is used in payment references.

### List Restaurants

`GET /restaurants/`

Roles: `ADMIN`

### Get Restaurant

`GET /restaurants/{restaurant_id}`

Roles: `ADMIN`, or authenticated user from the same restaurant.

### Create Branch

`POST /restaurants/{restaurant_id}/branches`

Roles: `OWNER`

Request:

```json
{
  "name": "Main Mall",
  "code": "MM",
  "location": "Gaborone"
}
```

Rules:

- `code` is optional at creation, but every branch receives a stable code.
- Branch code is unique within the restaurant.
- Branch code is used in payment references.

### List Branches

`GET /restaurants/{restaurant_id}/branches`

Roles: `ADMIN`, or authenticated user from the same restaurant.

### Get Settings

`GET /restaurants/{restaurant_id}/settings`

Roles: `OWNER`

### Update Settings

`PUT /restaurants/{restaurant_id}/settings`

Roles: `OWNER`

Request:

```json
{
  "currency": "BWP",
  "max_unpaid_amount": "50.00",
  "max_uncollected_orders": 1,
  "remote_cash_enabled": true
}
```

## Menu

Planned endpoints for MVP implementation.

### Create Category

`POST /restaurants/{restaurant_id}/menu/categories`

Roles: `OWNER`, `MANAGER`

Request:

```json
{
  "name": "Chicken",
  "display_order": 1
}
```

### List Categories

`GET /restaurants/{restaurant_id}/menu/categories`

Roles: public for QR/WhatsApp menu display, authenticated for management.

Rules:

- Public responses include active categories only.
- Management responses may include inactive categories.

### Create Menu Item

`POST /restaurants/{restaurant_id}/menu/items`

Roles: `OWNER`, `MANAGER`

Request:

```json
{
  "category_id": "uuid",
  "name": "Chicken and Chips",
  "description": "Quarter chicken with chips",
  "price": "55.00",
  "image_url": "https://example.com/item.jpg",
  "is_available": true
}
```

### Update Availability

`PATCH /restaurants/{restaurant_id}/menu/items/{item_id}/availability`

Roles: `OWNER`, `MANAGER`, `CASHIER`

Request:

```json
{
  "is_available": false
}
```

## Inventory

Inventory is ledger-based. Stock is never overwritten; every change is recorded as a `stock_movement`.

### Create Ingredient

`POST /restaurants/{restaurant_id}/inventory/ingredients`

Roles: `OWNER`, `MANAGER`

Request:

```json
{
  "name": "Chicken Portion",
  "unit": "portion"
}
```

### List Ingredients

`GET /restaurants/{restaurant_id}/inventory/ingredients`

Roles: `OWNER`, `MANAGER`

### Create Stock Location

`POST /restaurants/{restaurant_id}/inventory/branches/{branch_id}/locations`

Roles: `OWNER`, `MANAGER`

Request:

```json
{
  "name": "Kitchen"
}
```

Rules:

- Stock locations are branch-scoped.
- For automatic order consumption, the backend uses the branch location named `Kitchen` when present, otherwise the first branch location.

### Add or Update Recipe Item

`PUT /restaurants/{restaurant_id}/inventory/menu-items/{menu_item_id}/recipe-items`

Roles: `OWNER`, `MANAGER`

Request:

```json
{
  "ingredient_id": "uuid",
  "quantity": "1.250"
}
```

Rules:

- Quantity is the amount of ingredient consumed by one menu item.
- The menu item and ingredient must belong to the same restaurant.

### List Recipe Items

`GET /restaurants/{restaurant_id}/inventory/menu-items/{menu_item_id}/recipe-items`

Roles: `OWNER`, `MANAGER`

### Create Stock Movement

`POST /restaurants/{restaurant_id}/inventory/branches/{branch_id}/movements`

Roles: `OWNER`, `MANAGER`

Request:

```json
{
  "stock_location_id": "uuid",
  "ingredient_id": "uuid",
  "movement_type": "RECEIVED",
  "quantity": "10.000"
}
```

Rules:

- `RECEIVED` movements must be positive.
- `WASTAGE` movements must be negative.
- `ADJUSTMENT` movements can be positive or negative, but not zero.
- `ORDER_CONSUMPTION` movements are system-created when a recipe-backed order is collected.
- Manual stock movements write audit logs.

### List Stock Balances

`GET /restaurants/{restaurant_id}/inventory/branches/{branch_id}/balances`

Roles: `OWNER`, `MANAGER`

Query parameters:

| Name | Type | Required |
| --- | --- | --- |
| stock_location_id | uuid | No |

Rules:

- Balances are calculated from the movement ledger.
- Collected recipe-backed orders reduce stock through negative `ORDER_CONSUMPTION` movements.

## Orders

Planned endpoints for MVP implementation.

### Create Cashier Order

`POST /restaurants/{restaurant_id}/branches/{branch_id}/orders/cashier`

Roles: `OWNER`, `MANAGER`, `CASHIER`

Request:

```json
{
  "customer_id": "uuid",
  "items": [
    {
      "menu_item_id": "uuid",
      "quantity": 2
    }
  ],
  "payment_method": "CASH"
}
```

Response:

```json
{
  "id": "uuid",
  "restaurant_id": "uuid",
  "branch_id": "uuid",
  "business_date": "2026-09-03",
  "daily_sequence": 37,
  "display_number": "#037",
  "payment_reference": "CS01-MM-260903-037",
  "channel": "CASHIER",
  "subtotal": "110.00",
  "total": "110.00",
  "currency": "BWP",
  "payment_status": "PENDING",
  "order_status": "PENDING_PAYMENT"
}
```

Rules:

- Server calculates totals from current menu prices.
- Server generates `daily_sequence`, `display_number`, and payment reference.
- Sold-out items are rejected.
- Branch must belong to the restaurant.

### Public Customer Menu

`GET /public/restaurants/{restaurant_id}/branches/{branch_id}/menu`

Auth: public QR/WhatsApp customer flow.

Response:

```json
{
  "restaurant_id": "uuid",
  "restaurant_name": "Chicken Spot",
  "branch_id": "uuid",
  "branch_name": "Main Mall",
  "currency": "BWP",
  "categories": [
    {
      "id": "uuid",
      "name": "Chicken",
      "display_order": 1,
      "items": [
        {
          "id": "uuid",
          "category_id": "uuid",
          "name": "Chicken and Chips",
          "description": "Quarter chicken with chips",
          "price": "55.00",
          "image_url": null,
          "is_available": true
        }
      ]
    }
  ]
}
```

Rules:

- Only active restaurants, active branches, active categories, and available menu items are returned.
- No staff bearer token is required.

### Create Public Customer Order

`POST /public/restaurants/{restaurant_id}/branches/{branch_id}/orders`

Auth: public QR/WhatsApp customer flow.

Request:

```json
{
  "customer_name": "Customer Name",
  "customer_phone_number": "+26771112222",
  "channel": "QR",
  "payment_provider": "ORANGE_MONEY",
  "items": [
    {
      "menu_item_id": "uuid",
      "quantity": 2
    }
  ]
}
```

Response:

```json
{
  "order": {
    "id": "uuid",
    "display_number": "#001",
    "payment_reference": "CS-MM-260906-001",
    "channel": "QR",
    "total": "110.00",
    "payment_status": "PENDING",
    "order_status": "PENDING_PAYMENT"
  },
  "payment": {
    "provider": "ORANGE_MONEY",
    "reference": "CS-MM-260906-001",
    "status": "PENDING"
  },
  "status_token": {
    "order_id": "uuid",
    "access_token": "jwt",
    "token_type": "bearer",
    "expires_in_seconds": 14400
  },
  "status_url_path": "/customer/restaurants/.../status?token=..."
}
```

Rules:

- Creates a `QR` or `WHATSAPP` channel order.
- Only available items are orderable.
- Customer orders require a remote payment provider.
- A paid provider callback moves the order through `CONFIRMED` into `QUEUED`.
- The response includes a short-lived status token for the customer tracking page.

### List Branch Orders

`GET /restaurants/{restaurant_id}/branches/{branch_id}/orders`

Roles: `OWNER`, `MANAGER`, `CASHIER`, `KITCHEN`

Query parameters:

| Name | Type | Notes |
| --- | --- | --- |
| status | string | Optional order status filter. |
| business_date | date | Defaults to current business date. |
| channel | string | Optional channel filter. |

### Transition Order

`POST /restaurants/{restaurant_id}/branches/{branch_id}/orders/{order_id}/transition`

Roles depend on target state.

Request:

```json
{
  "target_status": "PREPARING"
}
```

Rules:

- Backend validates allowed transition.
- Every transition writes `order_status_history`.
- Money-sensitive transitions write `audit_logs`.

### Collect Order

`POST /restaurants/{restaurant_id}/branches/{branch_id}/orders/{order_id}/collect`

Roles: `OWNER`, `MANAGER`, `CASHIER`

Transition: `READY -> COLLECTED`

Rules:

- Order must be paid.
- Collection writes order status history.
- Collection writes audit log.
- Recipe-backed orders consume stock before collection is committed.
- Customer completed-order counter is incremented when the order has a customer.

### Create Order Status Token

`GET /restaurants/{restaurant_id}/branches/{branch_id}/orders/{order_id}/status-token`

Roles: `OWNER`, `MANAGER`, `CASHIER`

Response:

```json
{
  "order_id": "uuid",
  "access_token": "jwt",
  "token_type": "bearer",
  "expires_in_seconds": 14400
}
```

Rules:

- Token is scoped to one order.
- Token purpose is `order_status`.
- Token is used by customer order-status WebSockets.

### Get Customer Order Status

`GET /restaurants/{restaurant_id}/branches/{branch_id}/orders/{order_id}/customer-status`

Auth: order status token query parameter.

Query parameters:

| Name | Type | Notes |
| --- | --- | --- |
| token | string | Short-lived token created by the cashier order status token endpoint. |

Response:

```json
{
  "order_id": "uuid",
  "display_number": "#001",
  "payment_status": "PAID",
  "order_status": "READY",
  "updated_at": "2026-09-05T12:00:00Z"
}
```

Rules:

- Does not require staff bearer authentication.
- Token must be scoped to the requested order.
- Response is intentionally limited to customer-safe status details.

### Mark Uncollected

`POST /restaurants/{restaurant_id}/branches/{branch_id}/orders/{order_id}/uncollected`

Roles: `OWNER`, `MANAGER`, `CASHIER`

Transition: `READY -> UNCOLLECTED`

Rules:

- Action writes order status history.
- Action writes audit log.
- Customer uncollected-order counter is incremented when the order has a customer.

## Kitchen

### Kitchen Board

`GET /restaurants/{restaurant_id}/branches/{branch_id}/kitchen/board`

Roles: `OWNER`, `MANAGER`, `KITCHEN`

Response:

```json
{
  "new": [],
  "preparing": [],
  "ready": []
}
```

### Start Preparing

`POST /restaurants/{restaurant_id}/branches/{branch_id}/kitchen/orders/{order_id}/start`

Transition: `QUEUED -> PREPARING`

### Mark Ready

`POST /restaurants/{restaurant_id}/branches/{branch_id}/kitchen/orders/{order_id}/ready`

Transition: `PREPARING -> READY`

## Payments

### Initiate Payment

`POST /restaurants/{restaurant_id}/orders/{order_id}/payments`

Roles: `OWNER`, `MANAGER`, `CASHIER`

Request:

```json
{
  "provider": "ORANGE_MONEY",
  "customer_phone_number": "+26770000000"
}
```

Response:

```json
{
  "id": "uuid",
  "order_id": "uuid",
  "restaurant_id": "uuid",
  "provider": "ORANGE_MONEY",
  "reference": "CS-MM-260904-009",
  "provider_transaction_id": null,
  "amount": "55.00",
  "currency": "BWP",
  "status": "PENDING",
  "created_at": "2026-09-05T10:00:00Z",
  "completed_at": null
}
```

Rules:

- Provider logic must go through `PaymentProvider`.
- `CASH` is confirmed through the cash confirmation endpoint instead.
- Existing pending attempts are reused idempotently for the same provider.
- One successful payment per order.
- Existing successful payment for an order cannot be replaced.

### Confirm Cash Payment

`POST /restaurants/{restaurant_id}/orders/{order_id}/payments/cash/confirm`

Roles: `OWNER`, `MANAGER`, `CASHIER`

Request:

```json
{
  "amount_received": "110.00"
}
```

Rules:

- Amount must be at least order total.
- Writes payment record.
- Writes audit log.
- Moves order through `CONFIRMED` and into `QUEUED`.
- Writes order status history for each transition.

### Provider Callback

`POST /webhooks/payments/{provider}`

Auth: provider signature verification.

Header:

```http
X-Cognivex-Signature: sha256=<hex-hmac>
```

Rules:

- Verify webhook signature before processing.
- Callback payloads must include `provider_event_id`, `reference`, `status`, `amount`, and `currency`.
- Process callbacks idempotently.
- Reject mismatched reference, amount, currency, or duplicate transaction ID.
- A `PAID` callback moves the order from `PENDING_PAYMENT` through `CONFIRMED` into `QUEUED`.
- Replayed callbacks return `idempotent: true` without writing duplicate payment events.

Example payload:

```json
{
  "provider_event_id": "om-event-001",
  "reference": "CS-MM-260904-009",
  "status": "PAID",
  "amount": "55.00",
  "currency": "BWP",
  "provider_transaction_id": "om-txn-001"
}
```

Response:

```json
{
  "payment_id": "uuid",
  "reference": "CS-MM-260904-009",
  "provider": "ORANGE_MONEY",
  "status": "PAID",
  "event_type": "ORANGE_MONEY_PAID",
  "idempotent": false
}
```

## WhatsApp

WhatsApp-channel order creation is supported through the public customer order endpoint by sending `"channel": "WHATSAPP"`.

Full Meta WhatsApp Business webhook integration still requires provider credentials and webhook verification before live customer messaging can be enabled.

### Webhook Verification

`GET /webhooks/whatsapp`

Auth: Meta verification token.

### Webhook Events

`POST /webhooks/whatsapp`

Auth: Meta signature verification.

Rules:

- Duplicate message IDs are idempotent.
- Conversation flow is structured.
- AI chat is not part of MVP ordering.

## Reports

### Daily Sales

`GET /restaurants/{restaurant_id}/reports/daily-sales`

Roles: `OWNER`, `MANAGER`

Query parameters:

| Name | Type | Required |
| --- | --- | --- |
| business_date | date | Yes |
| branch_id | uuid | No |

### Export Daily Sales CSV

`GET /restaurants/{restaurant_id}/reports/daily-sales.csv`

Roles: `OWNER`, `MANAGER`

Daily sales response:

```json
{
  "restaurant_id": "uuid",
  "branch_id": "uuid",
  "business_date": "2026-09-04",
  "orders": 10,
  "collected_orders": 8,
  "ready_orders": 1,
  "uncollected_orders": 1,
  "cancelled_orders": 0,
  "revenue": "495.00",
  "average_order_value": "61.88",
  "top_items": [],
  "sales_by_payment": []
}
```

Revenue, top items, and sales by payment count paid `COLLECTED` orders only. `READY` and `UNCOLLECTED` orders are visible as operational counts but are not treated as completed sales.

## Realtime

WebSocket channels:

| Channel | Path | Audience |
| --- | --- | --- |
| Kitchen board | `/ws/restaurants/{restaurant_id}/branches/{branch_id}/kitchen?token={staff_jwt}` | Kitchen staff |
| Cashier updates | `/ws/restaurants/{restaurant_id}/branches/{branch_id}/cashier?token={staff_jwt}` | Cashier staff |
| Customer order status | `/ws/orders/{order_id}/status?token={order_status_token}` | QR/customer session |

Rules:

- Authenticate staff WebSockets.
- Customer status sockets must use short-lived order-scoped tokens.
- Broadcast only branch-scoped updates.
- Realtime publishes workflow events after the database commit succeeds.
- Realtime must not bypass the order state machine.

Event payload:

```json
{
  "type": "ORDER_PAYMENT_CONFIRMED",
  "restaurant_id": "uuid",
  "branch_id": "uuid",
  "order_id": "uuid",
  "display_number": "#001",
  "order_status": "QUEUED",
  "payment_status": "PAID",
  "channel": "CASHIER",
  "occurred_at": "2026-09-04T18:00:00+00:00"
}
```
