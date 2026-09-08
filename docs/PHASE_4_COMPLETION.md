# Phase 4 Completion

Phase 4 adds the backend foundation for non-cash payment providers.

## Completed Scope

- Staff endpoint to initiate remote provider payments.
- Sandbox provider adapter for `ORANGE_MONEY` and `FNB`.
- Signed payment webhook endpoint.
- HMAC signature verification using `X-Cognivex-Signature`.
- Idempotent provider callback handling with `provider_event_id`.
- Amount, currency, reference, status, and transaction-ID validation.
- Provider `PAID` callbacks move orders into the kitchen queue.
- Payment webhook audit logging and payment-event history.
- Smoke test coverage for a sandbox remote payment callback.

## Implemented Endpoints

- `POST /api/v1/restaurants/{restaurant_id}/orders/{order_id}/payments`
- `POST /api/v1/webhooks/payments/{provider}`

## Provider Integration Boundary

Real Orange Money and FNB integrations should replace only the provider adapter internals. The order lifecycle, payment records, payment events, webhook verification, and audit trail are already in place.

## Remaining Before Pilot

- Real provider credentials.
- Provider-specific initiate-payment API calls.
- Provider-specific callback payload normalization.
- Deployment-specific webhook URLs and secret rotation.
