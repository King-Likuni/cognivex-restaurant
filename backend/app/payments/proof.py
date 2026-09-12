"""Payment proof helpers shared across payments and order collection."""

from sqlalchemy.orm import Session

from app.payments.models import Payment, PaymentEvent
from app.payments.providers import REMOTE_PAYMENT_PROVIDERS


def requires_mobile_transfer_proof(payment: Payment | None) -> bool:
    return payment is not None and payment.provider in REMOTE_PAYMENT_PROVIDERS


def has_confirmed_mobile_transfer_proof(
    db: Session,
    payment: Payment,
    expected_reference: str,
) -> bool:
    normalized_reference = expected_reference.strip().upper()
    return (
        db.query(PaymentEvent.id)
        .filter(
            PaymentEvent.payment_id == payment.id,
            PaymentEvent.event_type == f"{payment.provider}_MANUAL_CONFIRMED",
            PaymentEvent.provider_event_id == normalized_reference,
        )
        .first()
        is not None
    )
