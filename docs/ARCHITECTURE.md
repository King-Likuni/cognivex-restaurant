# Cognivex Restaurant Platform Architecture

## Product Boundary

The MVP is a modular monolith for cashier, QR self-ordering, WhatsApp ordering, kitchen workflow, payment confirmation, customer notification, and sales records.

Public web ordering, delivery apps, native mobile apps, full inventory, payroll, accounting, loyalty, and procurement are outside the initial commercial V1.

## Core Workflow

`ORDER -> PAYMENT / PAYMENT CONFIRMATION -> KITCHEN -> PREPARATION -> READY -> CUSTOMER NOTIFICATION -> COLLECTION -> SALES RECORD`

## Tenant Model

The platform owns many restaurants. Each restaurant owns one or more branches. Operational records must be scoped by `restaurant_id`; branch operational records must also be scoped by `branch_id`.

Platform admins may cross restaurant boundaries. Restaurant owners, managers, cashiers, and kitchen staff must be constrained to their own restaurant and assigned branches.

## Order Identifiers

- System ID: immutable UUID.
- Customer display number: daily branch sequence such as `#037`.
- Payment reference: globally unique reference such as `CS01-MM-260903-037`.

The database enforces one daily sequence and display number per restaurant, branch, and business date.

## Payment Architecture

Payment integrations must be implemented behind provider adapters. The rest of the application should ask the payment service to initiate, verify, process callbacks, and refund without knowing provider-specific details.

The payment layer must reject duplicate callbacks, wrong amounts, reused transaction IDs, and mismatched references.

## Phase 2 Readiness

Inventory begins as its own module with stock locations, ingredients, recipe items, stock movements, and order item consumption. MVP sales can later consume inventory without rewriting orders or menu items.
