"""Notification-ready customer event service.

This module intentionally does not call a paid SMS or WhatsApp provider yet. It
records structured notification-ready events so the integration can be added
behind this boundary without changing order, payment, kitchen, or websocket code.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.observability import log_structured
from app.orders.enums import OrderStatus

if TYPE_CHECKING:
    from app.orders.models import Order

logger = logging.getLogger("app.notifications")


def get_customer_notification_type(order: Order, event_type: str) -> str | None:
    if event_type == "ORDER_STATUS_CHANGED" and order.order_status == OrderStatus.READY.value:
        return "ORDER_READY_FOR_COLLECTION"
    if event_type == "ORDER_PAYMENT_CONFIRMED":
        return "PAYMENT_CONFIRMED"
    if event_type == "ORDER_COLLECTED":
        return "ORDER_COLLECTED"
    if event_type == "ORDER_UNCOLLECTED":
        return "ORDER_UNCOLLECTED"
    if event_type == "ORDER_CANCELLED":
        return "ORDER_CANCELLED"
    return None


def record_customer_notification_event(order: Order, event_type: str) -> None:
    notification_type = get_customer_notification_type(order, event_type)
    if notification_type is None or order.customer_id is None:
        return

    log_structured(
        logger,
        logging.INFO,
        "customer_notification_ready",
        notification_type=notification_type,
        event_type=event_type,
        restaurant_id=order.restaurant_id,
        branch_id=order.branch_id,
        order_id=order.id,
        display_number=order.display_number,
        customer_id=order.customer_id,
        channel=order.channel,
        order_status=order.order_status,
        payment_status=order.payment_status,
        payment_provider=order.payment_provider,
    )
