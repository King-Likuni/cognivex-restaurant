"""Pydantic schemas for order workflows."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.payments.schemas import PaymentResponse


class OrderLineCreate(BaseModel):
    menu_item_id: UUID
    quantity: int = Field(..., ge=1, le=99)


class CashierOrderCreate(BaseModel):
    customer_id: UUID | None = None
    items: list[OrderLineCreate] = Field(..., min_length=1)
    payment_method: str = Field(default="CASH")


class PublicCustomerOrderCreate(BaseModel):
    customer_name: str | None = Field(default=None, max_length=120)
    customer_phone_number: str = Field(..., min_length=7, max_length=40)
    channel: Literal["QR", "WHATSAPP"] = "QR"
    payment_provider: str = Field(default="ORANGE_MONEY", min_length=1, max_length=40)
    items: list[OrderLineCreate] = Field(..., min_length=1)


class OrderItemResponse(BaseModel):
    id: UUID
    menu_item_id: UUID
    quantity: int
    unit_price: Decimal
    total_price: Decimal

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: UUID
    restaurant_id: UUID
    branch_id: UUID
    business_date: date
    daily_sequence: int
    display_number: str
    payment_reference: str
    customer_id: UUID | None
    channel: str
    subtotal: Decimal
    total: Decimal
    currency: str
    payment_status: str
    order_status: str
    created_by: UUID | None
    created_at: datetime | None
    confirmed_at: datetime | None
    preparing_at: datetime | None
    ready_at: datetime | None
    collected_at: datetime | None
    items: list[OrderItemResponse] = []

    model_config = {"from_attributes": True}


class OrderTransitionRequest(BaseModel):
    target_status: str


class OrderStatusTokenResponse(BaseModel):
    order_id: UUID
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class CustomerOrderStatusResponse(BaseModel):
    order_id: UUID
    display_number: str
    payment_status: str
    order_status: str
    updated_at: datetime | None


class PublicMenuItemResponse(BaseModel):
    id: UUID
    category_id: UUID
    name: str
    description: str | None
    price: Decimal
    image_url: str | None
    is_available: bool


class PublicMenuCategoryResponse(BaseModel):
    id: UUID
    name: str
    display_order: int
    items: list[PublicMenuItemResponse]


class PublicMenuResponse(BaseModel):
    restaurant_id: UUID
    restaurant_name: str
    branch_id: UUID
    branch_name: str
    currency: str
    categories: list[PublicMenuCategoryResponse]


class PublicCustomerOrderResponse(BaseModel):
    order: OrderResponse
    payment: PaymentResponse
    status_token: OrderStatusTokenResponse
    status_url_path: str
