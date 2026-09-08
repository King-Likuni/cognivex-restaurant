# MVP Specification

## Purpose

Cognivex Restaurant Platform V1 reduces restaurant queue friction, kitchen coordination problems, uncollected orders, and manual sales records.

The MVP must prove one reliable commercial journey:

`customer/cashier creates order -> payment is confirmed -> kitchen prepares -> order is ready -> customer is notified -> order is collected -> sale is reportable`

## In Scope

### Ordering Channels

| Channel | MVP Status | Notes |
| --- | --- | --- |
| Cashier / walk-in | Included | Staff creates order and confirms cash/manual payment. |
| QR self-ordering | Included | Customer scans branch QR, orders without an account, then selects payment method. |
| WhatsApp ordering | Included | Structured menu flow through WhatsApp Business webhooks. |
| Public web ordering | Excluded | Later product, separate from QR self-ordering. |
| Delivery app integrations | Excluded | Later. |
| Native Android / iOS apps | Excluded | Later. |

### Payment Methods

| Method | MVP Status | Notes |
| --- | --- | --- |
| Cash | Included | Cashier-confirmed and audited. |
| Orange Money | Included where integration permits | Must use provider adapter. Mock adapter is acceptable until credentials are available. |
| FNB / Pay-to-Cell / merchant payment | Included where integration permits | Must use provider adapter. Mock adapter is acceptable until credentials are available. |
| Visa / Mastercard gateway | Excluded | Later. |
| Other wallets | Excluded | Later. |

### User Roles

| Role | Access |
| --- | --- |
| ADMIN | Cognivex platform administration across restaurants. |
| OWNER | Full access inside one restaurant. |
| MANAGER | Restaurant operations, staff, menu, reporting, and settings as delegated. |
| CASHIER | Create orders, confirm allowed payments, view collection queue. |
| KITCHEN | View kitchen queue and move orders through preparation states. |

All non-admin users must be scoped to one `restaurant_id`. Branch-scoped work must also honor branch access.

## Core Entities

- `restaurants`
- `branches`
- `users`
- `roles`
- `user_branches`
- `customers`
- `menu_categories`
- `menu_items`
- `orders`
- `order_items`
- `order_status_history`
- `payments`
- `payment_events`
- `notifications`
- `audit_logs`
- `restaurant_settings`

Phase 2 inventory entities may exist in schema as placeholders, but no MVP workflow should depend on full inventory calculations.

## Order Identity Rules

Each order has three identifiers:

| Identifier | Example | Rule |
| --- | --- | --- |
| System ID | `9b8d90d8-...` | UUID, permanent, internal. |
| Display number | `#037` | Resets per restaurant, branch, and business date. |
| Payment reference | `CS01-MM-260903-037` | Unique provider-facing reference. |

Display numbers must be generated server-side. Clients must never submit their own daily sequence.

## Order State Machine

Primary flow:

`DRAFT -> PENDING_PAYMENT -> CONFIRMED -> QUEUED -> PREPARING -> READY -> COLLECTED`

Alternative outcomes:

`PENDING_PAYMENT -> PAYMENT_EXPIRED -> CANCELLED`

`READY -> UNCOLLECTED`

Allowed transitions are enforced by the backend. The kitchen cannot move unpaid orders into preparation unless an explicit restaurant setting later permits that workflow.

## Workflow Requirements

### Cashier Order

1. Cashier selects branch.
2. Cashier adds available menu items.
3. System calculates subtotal and total.
4. System assigns display number and payment reference.
5. Cashier confirms cash or supported manual payment.
6. Order becomes `CONFIRMED`, then enters kitchen queue as `QUEUED`.
7. Audit log records cashier, amount, payment method, time, and order.

Acceptance criteria:

- Cashier cannot order sold-out items.
- Cash payment confirmation creates a payment record.
- Kitchen sees the order without manual database work.
- Sale appears in daily reports after collection or according to reporting rules.

### QR Self-Ordering

1. Customer scans branch QR code.
2. Customer views only available menu items.
3. Customer builds cart without creating an account.
4. Customer chooses available payment method.
5. System creates order and payment reference.
6. Payment confirmation moves order into kitchen queue.
7. Customer can view order status from the same session.

Acceptance criteria:

- QR route resolves to a specific branch.
- Customer cannot see another branch's operational data.
- Remote cash is hidden when restaurant rules disallow it.

### WhatsApp Ordering

1. Meta WhatsApp sends webhook to backend.
2. Webhook signature is verified before processing.
3. Structured conversation flow presents menu choices.
4. Customer selects category, item, quantity, and payment method.
5. System creates order and payment reference.
6. Payment confirmation moves order into kitchen queue.
7. Customer receives important notifications only.

Acceptance criteria:

- Duplicate webhook deliveries are idempotent.
- Structured flow works without AI.
- Customers are notified when order is ready.

### Kitchen Display

Kitchen display has three operational columns:

- `NEW` for queued orders.
- `PREPARING` for active preparation.
- `READY` for completed orders.

Kitchen actions:

- Start: `QUEUED -> PREPARING`
- Ready: `PREPARING -> READY`

Acceptance criteria:

- Kitchen staff cannot edit prices or payments.
- Buttons are large enough for touch screens.
- State changes are recorded in order status history.

### Manager Dashboard

V1 dashboard shows:

- Today's order count.
- Today's revenue.
- Average order value.
- Average preparation time.
- Uncollected orders.
- Cancelled orders.
- Top menu items.
- Sales by payment method.
- Hourly sales.

Reports must export CSV in MVP.

## Payment Verification Rules

A payment is valid only when:

- Reference matches the order payment reference.
- Amount matches expected total.
- Currency matches expected currency.
- Provider status is successful.
- Provider transaction ID has not already been used.
- Callback or provider event ID has not already been processed.

Screenshots are not authoritative payment verification.

## Notification Rules

Notify customers for:

- Order confirmed.
- Order ready.
- Collection reminder.
- Payment expired.
- Order cancelled.

Avoid noisy notifications for every tiny state change.

## No-Show Rules

Customer profile tracks:

- `total_orders`
- `completed_orders`
- `cancelled_orders`
- `uncollected_orders`

Restaurant settings control:

- remote cash enabled
- maximum unpaid amount
- maximum uncollected orders

If a customer exceeds the configured uncollected-order threshold, remote cash payment should be disabled for that customer.

## Security Requirements

Before pilot:

- Strong production secrets.
- HTTPS in production.
- Password hashing.
- Tenant isolation tests.
- API authentication.
- Role authorization.
- Webhook signature verification.
- Payment idempotency.
- Audit trail for money-sensitive actions.
- Environment-specific config.
- Database backup process.

Cognivex must never store customer Orange Money PINs, banking credentials, or card details.

## Out of Scope for MVP

- Full inventory automation.
- Ingredient costing and profit calculations.
- Payroll.
- Employee scheduling.
- Supplier/procurement workflows.
- Accounting integrations.
- Loyalty and promotions.
- Reservations.
- Delivery fleet management.
- Native mobile apps.

These must not block the first restaurant pilot.

## Pilot Readiness Definition

The system is pilot-ready when these journeys pass automated or documented manual tests:

- Cashier order paid with cash, prepared, ready, collected, and reported.
- QR order created and paid through a mock or real provider.
- WhatsApp order created through structured flow.
- Duplicate payment callback rejected safely.
- Wrong payment amount rejected safely.
- Tenant isolation confirmed.
- Daily order numbering resets correctly.
- Sold-out menu item cannot be ordered.
- Uncollected order can be marked and reported.
