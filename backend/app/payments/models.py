"""Payment models."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.orders.enums import PaymentStatus


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_transaction_id",
            name="uq_payments_provider_transaction_id",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, unique=True)
    restaurant_id = Column(
        UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False, index=True
    )

    provider = Column(String, nullable=False)  # CASH, ORANGE_MONEY, FNB
    reference = Column(String, nullable=False, unique=True, index=True)  # e.g., CS01-MM-260903-037
    provider_transaction_id = Column(String, nullable=True)

    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, default="BWP")
    status = Column(String, default=PaymentStatus.PENDING.value)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", back_populates="payment")
    events = relationship("PaymentEvent", back_populates="payment")


class PaymentEvent(Base):
    __tablename__ = "payment_events"
    __table_args__ = (
        UniqueConstraint(
            "payment_id", "provider_event_id", name="uq_payment_events_provider_event_id"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = Column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False, index=True)
    provider_event_id = Column(String, nullable=True)
    event_type = Column(String, nullable=False)
    payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    payment = relationship("Payment", back_populates="events")
