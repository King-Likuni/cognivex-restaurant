"""Pydantic schemas for payment workflows."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class PaymentInitiateRequest(BaseModel):
    provider: str = Field(..., min_length=1, max_length=40)
    customer_phone_number: str | None = Field(default=None, max_length=40)


class CashPaymentConfirmRequest(BaseModel):
    amount_received: Decimal = Field(..., gt=Decimal("0.00"))


class MobileTransferConfirmRequest(BaseModel):
    amount_received: Decimal = Field(..., gt=Decimal("0.00"))
    payment_reference_used: str = Field(..., min_length=1, max_length=80)


class PaymentResponse(BaseModel):
    id: UUID
    order_id: UUID
    restaurant_id: UUID
    provider: str
    reference: str
    provider_transaction_id: str | None
    amount: Decimal
    currency: str
    status: str
    created_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class PaymentWebhookResponse(BaseModel):
    payment_id: UUID
    reference: str
    provider: str
    status: str
    event_type: str
    idempotent: bool = False
