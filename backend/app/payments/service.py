"""Payment service layer."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.auth.models import User
from app.orders.enums import OrderStatus, PaymentStatus
from app.orders.models import Order
from app.orders.service import transition_order
from app.payments.models import Payment, PaymentEvent
from app.payments.providers import REMOTE_PAYMENT_PROVIDERS, PaymentRequest, get_payment_provider
from app.realtime.events import publish_order_event


def get_order_for_payment(db: Session, restaurant_id: UUID, order_id: UUID) -> Order | None:
    return (
        db.query(Order).filter(Order.id == order_id, Order.restaurant_id == restaurant_id).first()
    )


def normalize_provider(provider: str) -> str:
    return provider.strip().upper()


def initiate_payment(
    db: Session,
    restaurant_id: UUID,
    order_id: UUID,
    provider_name: str,
    initiated_by: User | None,
    customer_phone_number: str | None = None,
) -> Payment:
    provider = get_payment_provider(normalize_provider(provider_name))
    if provider.provider_name == "CASH":
        raise ValueError("Use cash confirmation for CASH payments")

    order = get_order_for_payment(db, restaurant_id, order_id)
    if order is None:
        raise ValueError("Order not found")
    if order.payment_status == PaymentStatus.PAID.value:
        raise ValueError("Order is already paid")
    if order.payment is not None:
        if order.payment.provider != provider.provider_name:
            raise ValueError(
                f"Order already has a payment attempt with provider {order.payment.provider}"
            )
        return order.payment
    if order.order_status != OrderStatus.PENDING_PAYMENT.value:
        raise ValueError("Payment can only be initiated for pending-payment orders")

    previous_order_status = order.order_status
    provider_result = provider.initiate_payment(
        PaymentRequest(
            order_id=str(order.id),
            reference=order.payment_reference,
            amount=order.total,
            currency=order.currency,
            customer_phone_number=customer_phone_number,
        )
    )

    payment = Payment(
        order_id=order.id,
        restaurant_id=restaurant_id,
        provider=provider_result.provider,
        reference=provider_result.reference,
        provider_transaction_id=provider_result.provider_transaction_id,
        amount=provider_result.amount,
        currency=provider_result.currency,
        status=provider_result.status,
    )
    db.add(payment)
    db.flush()
    db.add(
        PaymentEvent(
            payment_id=payment.id,
            event_type="PAYMENT_INITIATED",
            payload=provider_result.raw_payload
            or {
                "provider": provider_result.provider,
                "reference": provider_result.reference,
            },
        )
    )
    db.add(
        AuditLog(
            restaurant_id=restaurant_id,
            user_id=initiated_by.id if initiated_by else None,
            action="PAYMENT_INITIATED",
            entity_type="order",
            entity_id=order.id,
            old_values={
                "payment_status": order.payment_status,
                "order_status": previous_order_status,
            },
            new_values={
                "provider": provider_result.provider,
                "payment_status": provider_result.status,
                "order_status": OrderStatus.QUEUED.value,
                "reference": provider_result.reference,
            },
        )
    )
    transition_order(db, order, OrderStatus.CONFIRMED, initiated_by, commit=False)
    transition_order(db, order, OrderStatus.QUEUED, initiated_by, commit=False)
    db.commit()
    db.refresh(payment)
    return payment


def mark_order_paid_from_provider_callback(
    db: Session,
    payment: Payment,
    provider_transaction_id: str | None,
) -> None:
    order = payment.order
    payment.status = PaymentStatus.PAID.value
    payment.completed_at = datetime.now(UTC)
    if provider_transaction_id is not None:
        payment.provider_transaction_id = provider_transaction_id
    order.payment_status = PaymentStatus.PAID.value
    if order.order_status == OrderStatus.PENDING_PAYMENT.value:
        transition_order(db, order, OrderStatus.CONFIRMED, None, commit=False)
        transition_order(db, order, OrderStatus.QUEUED, None, commit=False)


def process_payment_webhook(
    db: Session,
    provider_name: str,
    payload: dict,
) -> tuple[Payment, PaymentEvent, bool]:
    provider = get_payment_provider(normalize_provider(provider_name))
    if provider.provider_name == "CASH":
        raise ValueError("Cash payments do not use provider callbacks")

    provider_event_id = payload.get("provider_event_id")
    if not provider_event_id:
        raise ValueError("provider_event_id is required")
    missing_fields = {"reference", "status", "amount", "currency"} - set(payload)
    if missing_fields:
        raise ValueError(f"Missing webhook fields: {', '.join(sorted(missing_fields))}")

    result = provider.process_callback(payload)
    try:
        result_status = PaymentStatus(result.status)
    except ValueError as exc:
        raise ValueError(f"Unsupported payment status '{result.status}'") from exc

    payment = (
        db.query(Payment)
        .filter(Payment.provider == provider.provider_name, Payment.reference == result.reference)
        .first()
    )
    if payment is None:
        raise ValueError("Payment not found")

    if Decimal(result.amount) != Decimal(payment.amount):
        raise ValueError("Webhook amount does not match payment")
    if result.currency != payment.currency:
        raise ValueError("Webhook currency does not match payment")
    if (
        result.provider_transaction_id is not None
        and payment.provider_transaction_id is not None
        and result.provider_transaction_id != payment.provider_transaction_id
    ):
        raise ValueError("Webhook transaction ID does not match payment")
    if payment.status == PaymentStatus.PAID.value and result_status != PaymentStatus.PAID:
        raise ValueError("Paid payment cannot be downgraded by provider callback")

    existing_event = (
        db.query(PaymentEvent)
        .filter(
            PaymentEvent.payment_id == payment.id,
            PaymentEvent.provider_event_id == provider_event_id,
        )
        .first()
    )
    if existing_event is not None:
        return payment, existing_event, True

    if result.provider_transaction_id is not None:
        transaction_owner = (
            db.query(Payment)
            .filter(
                Payment.provider == provider.provider_name,
                Payment.provider_transaction_id == result.provider_transaction_id,
                Payment.id != payment.id,
            )
            .first()
        )
        if transaction_owner is not None:
            raise ValueError("Webhook transaction ID is already assigned to another payment")

    should_publish_paid_event = (
        result_status == PaymentStatus.PAID and payment.status != PaymentStatus.PAID.value
    )

    event = PaymentEvent(
        payment_id=payment.id,
        provider_event_id=provider_event_id,
        event_type=f"{provider.provider_name}_{result_status.value}",
        payload=result.raw_payload,
    )
    db.add(event)
    db.add(
        AuditLog(
            restaurant_id=payment.restaurant_id,
            user_id=None,
            action="PAYMENT_WEBHOOK_PROCESSED",
            entity_type="payment",
            entity_id=payment.id,
            old_values={"status": payment.status},
            new_values={
                "provider": provider.provider_name,
                "provider_event_id": provider_event_id,
                "status": result_status.value,
                "reference": result.reference,
                "provider_transaction_id": result.provider_transaction_id,
            },
        )
    )

    if should_publish_paid_event:
        mark_order_paid_from_provider_callback(db, payment, result.provider_transaction_id)
    elif result_status in {PaymentStatus.FAILED, PaymentStatus.EXPIRED}:
        payment.status = result_status.value
        payment.order.payment_status = result_status.value
        if (
            result_status == PaymentStatus.EXPIRED
            and payment.order.order_status == OrderStatus.PENDING_PAYMENT.value
        ):
            transition_order(db, payment.order, OrderStatus.PAYMENT_EXPIRED, None, commit=False)

    db.commit()
    db.refresh(payment)
    db.refresh(event)
    if should_publish_paid_event:
        publish_order_event(payment.order, "ORDER_PAYMENT_CONFIRMED")
    return payment, event, False


def confirm_cash_payment(
    db: Session,
    restaurant_id: UUID,
    order_id: UUID,
    amount_received: Decimal,
    confirmed_by: User,
) -> Payment:
    order = get_order_for_payment(db, restaurant_id, order_id)
    if order is None:
        raise ValueError("Order not found")
    if order.payment is not None and order.payment.status == PaymentStatus.PAID.value:
        raise ValueError("Order is already paid")
    if order.order_status != OrderStatus.PENDING_PAYMENT.value:
        raise ValueError("Cash payment can only be confirmed for pending-payment orders")
    if amount_received < Decimal(order.total):
        raise ValueError("Amount received is less than order total")

    payment = Payment(
        order_id=order.id,
        restaurant_id=restaurant_id,
        provider="CASH",
        reference=order.payment_reference,
        amount=order.total,
        currency=order.currency,
        status=PaymentStatus.PAID.value,
        completed_at=datetime.now(UTC),
    )
    db.add(payment)
    db.flush()

    db.add(
        PaymentEvent(
            payment_id=payment.id,
            event_type="CASH_CONFIRMED",
            payload={
                "amount_received": str(amount_received),
                "order_total": str(order.total),
                "confirmed_by": str(confirmed_by.id),
            },
        )
    )
    db.add(
        AuditLog(
            restaurant_id=restaurant_id,
            user_id=confirmed_by.id,
            action="CASH_PAYMENT_CONFIRMED",
            entity_type="order",
            entity_id=order.id,
            old_values={
                "payment_status": order.payment_status,
                "order_status": order.order_status,
            },
            new_values={
                "payment_status": PaymentStatus.PAID.value,
                "order_status": OrderStatus.QUEUED.value,
                "amount_received": str(amount_received),
                "amount_paid": str(order.total),
            },
        )
    )

    order.payment_status = PaymentStatus.PAID.value
    transition_order(db, order, OrderStatus.CONFIRMED, confirmed_by, commit=False)
    transition_order(db, order, OrderStatus.QUEUED, confirmed_by, commit=False)

    db.commit()
    db.refresh(payment)
    db.refresh(order)
    publish_order_event(order, "ORDER_PAYMENT_CONFIRMED")
    return payment


def confirm_mobile_transfer_payment(
    db: Session,
    restaurant_id: UUID,
    order_id: UUID,
    amount_received: Decimal,
    confirmed_by: User,
    payment_reference_used: str,
) -> Payment:
    order = get_order_for_payment(db, restaurant_id, order_id)
    if order is None:
        raise ValueError("Order not found")
    if order.payment is None:
        raise ValueError("Remote payment has not been initiated for this order")

    payment = order.payment
    if payment.provider not in REMOTE_PAYMENT_PROVIDERS:
        raise ValueError("Only mobile transfer payments can be manually confirmed here")
    if payment.status == PaymentStatus.PAID.value:
        raise ValueError("Order is already paid")
    if order.order_status != OrderStatus.READY.value:
        raise ValueError(
            "Mobile transfer can only be confirmed when the order is ready for collection"
        )
    if amount_received < Decimal(order.total):
        raise ValueError("Amount received is less than order total")

    normalized_payment_reference = payment_reference_used.strip().upper()
    if normalized_payment_reference != order.payment_reference.upper():
        raise ValueError("Payment reference does not match this order")

    previous_payment_status = payment.status
    previous_order_status = order.order_status
    payment.status = PaymentStatus.PAID.value
    payment.completed_at = datetime.now(UTC)
    order.payment_status = PaymentStatus.PAID.value

    db.add(
        PaymentEvent(
            payment_id=payment.id,
            provider_event_id=normalized_payment_reference,
            event_type=f"{payment.provider}_MANUAL_CONFIRMED",
            payload={
                "amount_received": str(amount_received),
                "order_total": str(order.total),
                "confirmed_by": str(confirmed_by.id),
                "payment_reference_used": normalized_payment_reference,
            },
        )
    )
    db.add(
        AuditLog(
            restaurant_id=restaurant_id,
            user_id=confirmed_by.id,
            action="MOBILE_TRANSFER_PAYMENT_CONFIRMED",
            entity_type="order",
            entity_id=order.id,
            old_values={
                "payment_status": previous_payment_status,
                "order_status": previous_order_status,
            },
            new_values={
                "provider": payment.provider,
                "payment_status": PaymentStatus.PAID.value,
                "order_status": order.order_status,
                "amount_received": str(amount_received),
                "amount_paid": str(order.total),
                "payment_reference_used": normalized_payment_reference,
            },
        )
    )

    db.commit()
    db.refresh(payment)
    db.refresh(order)
    publish_order_event(order, "ORDER_PAYMENT_CONFIRMED")
    return payment
