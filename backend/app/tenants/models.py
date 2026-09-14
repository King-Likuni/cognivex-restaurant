import uuid

from sqlalchemy import (
    Boolean,
    Column,
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


class Restaurant(Base):
    __tablename__ = "restaurants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    status = Column(String, default="ACTIVE", nullable=False)
    subscription_status = Column(String, default="TRIAL", nullable=False)
    subscription_started_at = Column(DateTime(timezone=True), nullable=True)
    subscription_renews_at = Column(DateTime(timezone=True), nullable=True)
    suspension_reason = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    branches = relationship("Branch", back_populates="restaurant")
    users = relationship("User", back_populates="restaurant")


class Branch(Base):
    __tablename__ = "branches"
    __table_args__ = (
        UniqueConstraint("restaurant_id", "code", name="uq_branches_restaurant_code"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    location = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

    restaurant = relationship("Restaurant", back_populates="branches")


class RestaurantSettings(Base):
    __tablename__ = "restaurant_settings"

    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id"), primary_key=True)
    currency = Column(String, default="BWP")
    max_unpaid_amount = Column(Numeric(10, 2), default=50.00)
    max_uncollected_orders = Column(Integer, default=1)
    remote_cash_enabled = Column(Boolean, default=True)
