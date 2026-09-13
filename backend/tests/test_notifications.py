import logging
from types import SimpleNamespace
from uuid import uuid4

from app.notifications.service import (
    get_customer_notification_type,
    record_customer_notification_event,
)
from app.orders.enums import OrderStatus


def make_order(*, status=OrderStatus.READY.value, customer_id=None):
    return SimpleNamespace(
        restaurant_id=uuid4(),
        branch_id=uuid4(),
        id=uuid4(),
        display_number="#001",
        customer_id=customer_id,
        channel="QR",
        order_status=status,
        payment_status="PENDING",
        payment_provider="ORANGE_MONEY",
    )


def test_notification_type_only_targets_customer_relevant_events():
    order = make_order(status=OrderStatus.READY.value)

    assert get_customer_notification_type(order, "ORDER_STATUS_CHANGED") == (
        "ORDER_READY_FOR_COLLECTION"
    )
    assert get_customer_notification_type(order, "ORDER_PAYMENT_CONFIRMED") == "PAYMENT_CONFIRMED"
    assert get_customer_notification_type(order, "ORDER_CREATED") is None


def test_notification_ready_event_is_structured_log_only(caplog):
    caplog.set_level(logging.INFO, logger="app.notifications")
    order = make_order(customer_id=uuid4())

    record_customer_notification_event(order, "ORDER_STATUS_CHANGED")

    assert "customer_notification_ready" in caplog.text
    assert "ORDER_READY_FOR_COLLECTION" in caplog.text
    assert str(order.id) in caplog.text


def test_notification_ready_event_skips_walk_in_orders(caplog):
    caplog.set_level(logging.INFO, logger="app.notifications")
    order = make_order(customer_id=None)

    record_customer_notification_event(order, "ORDER_STATUS_CHANGED")

    assert "customer_notification_ready" not in caplog.text
