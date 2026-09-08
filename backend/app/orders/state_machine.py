"""Allowed order workflow transitions."""

from app.orders.enums import OrderStatus

ALLOWED_ORDER_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.DRAFT: {OrderStatus.PENDING_PAYMENT, OrderStatus.CANCELLED},
    OrderStatus.PENDING_PAYMENT: {
        OrderStatus.CONFIRMED,
        OrderStatus.PAYMENT_EXPIRED,
        OrderStatus.CANCELLED,
    },
    OrderStatus.PAYMENT_EXPIRED: {OrderStatus.CANCELLED},
    OrderStatus.CONFIRMED: {OrderStatus.QUEUED, OrderStatus.CANCELLED},
    OrderStatus.QUEUED: {OrderStatus.PREPARING, OrderStatus.CANCELLED},
    OrderStatus.PREPARING: {OrderStatus.READY},
    OrderStatus.READY: {OrderStatus.COLLECTED, OrderStatus.UNCOLLECTED},
    OrderStatus.COLLECTED: set(),
    OrderStatus.UNCOLLECTED: set(),
    OrderStatus.CANCELLED: set(),
}


def can_transition_order(current: OrderStatus | str, target: OrderStatus | str) -> bool:
    current_status = OrderStatus(current)
    target_status = OrderStatus(target)
    return target_status in ALLOWED_ORDER_TRANSITIONS[current_status]


def validate_order_transition(current: OrderStatus | str, target: OrderStatus | str) -> None:
    if not can_transition_order(current, target):
        raise ValueError(f"Cannot transition order from {current} to {target}")
