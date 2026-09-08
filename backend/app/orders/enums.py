"""Order and payment status values used by services and API payloads."""

from enum import StrEnum


class OrderChannel(StrEnum):
    CASHIER = "CASHIER"
    QR = "QR"
    WHATSAPP = "WHATSAPP"


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    PAID = "PAID"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class OrderStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAYMENT_EXPIRED = "PAYMENT_EXPIRED"
    CONFIRMED = "CONFIRMED"
    QUEUED = "QUEUED"
    PREPARING = "PREPARING"
    READY = "READY"
    COLLECTED = "COLLECTED"
    UNCOLLECTED = "UNCOLLECTED"
    CANCELLED = "CANCELLED"
