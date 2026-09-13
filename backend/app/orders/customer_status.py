"""Customer-facing order status messages."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.orders.enums import OrderStatus, PaymentStatus
from app.payments.providers import REMOTE_PAYMENT_PROVIDERS

if TYPE_CHECKING:
    from app.orders.models import Order


def get_customer_status_updated_at(order: Order) -> datetime | None:
    return (
        order.collected_at
        or order.ready_at
        or order.preparing_at
        or order.confirmed_at
        or order.created_at
    )


def payment_proof_required(order: Order) -> bool:
    if order.order_status != OrderStatus.READY.value:
        return False
    if order.payment_status != PaymentStatus.PAID.value:
        return True
    return bool(
        order.payment_provider in REMOTE_PAYMENT_PROVIDERS
        and not order.mobile_transfer_proof_confirmed
    )


def get_customer_stage_label(order: Order) -> str:
    labels = {
        OrderStatus.PENDING_PAYMENT.value: "Order received",
        OrderStatus.CONFIRMED.value: "Confirmed",
        OrderStatus.QUEUED.value: "Queued",
        OrderStatus.PREPARING.value: "Preparing",
        OrderStatus.READY.value: "Ready for collection",
        OrderStatus.COLLECTED.value: "Collected",
        OrderStatus.UNCOLLECTED.value: "Awaiting follow-up",
        OrderStatus.CANCELLED.value: "Cancelled",
        OrderStatus.PAYMENT_EXPIRED.value: "Payment expired",
    }
    return labels.get(order.order_status, "Order update")


def get_customer_status_message(order: Order) -> str:
    if order.order_status == OrderStatus.QUEUED.value:
        return (
            "Your order is moving through the kitchen. Keep your payment proof ready "
            "for collection."
        )
    if order.order_status == OrderStatus.PREPARING.value:
        return "The kitchen is preparing your order."
    if order.order_status == OrderStatus.READY.value:
        if payment_proof_required(order):
            return (
                "Your order is ready. Show your proof of payment with the system "
                "reference at the counter."
            )
        return "Your order is ready and payment has been confirmed. Please collect it."
    if order.order_status == OrderStatus.COLLECTED.value:
        return "Your order has been collected."
    if order.order_status == OrderStatus.UNCOLLECTED.value:
        return "Your order was ready but not collected. Please speak to the counter."
    if order.order_status == OrderStatus.CANCELLED.value:
        return "This order has been cancelled."
    if order.order_status == OrderStatus.PAYMENT_EXPIRED.value:
        return "The payment window for this order has expired."
    if order.payment_status == PaymentStatus.PENDING.value:
        return "Your order was received and will continue through the kitchen."
    return "Waiting for the latest order update."


def get_collection_instruction(order: Order) -> str | None:
    if order.order_status != OrderStatus.READY.value:
        return None
    if payment_proof_required(order):
        return "Give the cashier your order number and payment reference from your phone."
    return "Give the cashier your order number to collect."
