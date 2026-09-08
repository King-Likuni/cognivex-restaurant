"""Order domain models."""

import uuid

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.orders.enums import OrderStatus, PaymentStatus


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint(
            "restaurant_id",
            "branch_id",
            "business_date",
            "daily_sequence",
            name="uq_orders_daily_sequence_per_branch",
        ),
        UniqueConstraint(
            "restaurant_id",
            "branch_id",
            "business_date",
            "display_number",
            name="uq_orders_display_number_per_branch",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(
        UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False, index=True
    )
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False, index=True)

    business_date = Column(Date, nullable=False, index=True)
    daily_sequence = Column(Integer, nullable=False)
    display_number = Column(String, nullable=False)  # e.g. "#037"
    payment_reference = Column(String, unique=True, index=True, nullable=False)

    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    channel = Column(String, nullable=False)  # CASHIER, QR, WHATSAPP

    subtotal = Column(Numeric(10, 2), nullable=False)
    total = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, default="BWP")

    payment_status = Column(String, default=PaymentStatus.PENDING.value)
    order_status = Column(String, default=OrderStatus.DRAFT.value)

    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    preparing_at = Column(DateTime(timezone=True), nullable=True)
    ready_at = Column(DateTime(timezone=True), nullable=True)
    collected_at = Column(DateTime(timezone=True), nullable=True)

    items = relationship("OrderItem", back_populates="order")
    status_history = relationship("OrderStatusHistory", back_populates="order")
    payment = relationship("Payment", uselist=False, back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True)
    menu_item_id = Column(UUID(as_uuid=True), ForeignKey("menu_items.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    total_price = Column(Numeric(10, 2), nullable=False)

    order = relationship("Order", back_populates="items")
    menu_item = relationship("MenuItem")


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"
    __table_args__ = (
        UniqueConstraint("order_id", "sequence", name="uq_order_status_history_order_sequence"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    previous_status = Column(String, nullable=True)
    new_status = Column(String, nullable=False)
    changed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())

    order = relationship("Order", back_populates="status_history")
