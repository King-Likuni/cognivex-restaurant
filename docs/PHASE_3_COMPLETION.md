# Phase 3 Completion

Phase 3 adds realtime workflow visibility for staff and customer-safe order tracking.

## Completed Scope

- In-process realtime event bus for order workflow events.
- Staff kitchen WebSocket channel.
- Staff cashier WebSocket channel.
- Customer order-status WebSocket channel.
- Short-lived order-status token endpoint.
- Realtime events published after successful database commits.
- Integration tests for staff branch sockets and customer order-status token enforcement.

## Channels

| Audience | Path |
| --- | --- |
| Kitchen staff | `/ws/restaurants/{restaurant_id}/branches/{branch_id}/kitchen?token={staff_jwt}` |
| Cashier staff | `/ws/restaurants/{restaurant_id}/branches/{branch_id}/cashier?token={staff_jwt}` |
| Customer order status | `/ws/orders/{order_id}/status?token={order_status_token}` |

## Events

Current order workflow events include:

- `ORDER_CREATED`
- `ORDER_PAYMENT_CONFIRMED`
- `ORDER_STATUS_CHANGED`
- `ORDER_COLLECTED`
- `ORDER_UNCOLLECTED`

## Production Note

The current broadcaster is intentionally in-process for local development and a single API process. Before multi-process deployment, replace the event bus internals with Redis pub/sub while preserving the same publishing API.

## Latest Verification

- Realtime integration tests passed.
- Customer order-status socket rejects missing order token.
- Staff kitchen socket receives branch-scoped order events.
