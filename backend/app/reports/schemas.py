"""Pydantic schemas for management reports."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class TopMenuItemSummary(BaseModel):
    menu_item_id: UUID
    name: str
    quantity: int
    revenue: Decimal


class PaymentMethodSummary(BaseModel):
    provider: str
    payments: int
    revenue: Decimal


class DailySalesReport(BaseModel):
    restaurant_id: UUID
    branch_id: UUID | None
    business_date: date
    orders: int
    collected_orders: int
    ready_orders: int
    uncollected_orders: int
    cancelled_orders: int
    revenue: Decimal
    average_order_value: Decimal
    top_items: list[TopMenuItemSummary]
    sales_by_payment: list[PaymentMethodSummary]
