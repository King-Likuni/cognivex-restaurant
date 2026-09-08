"""Pydantic schemas for kitchen workflows."""

from pydantic import BaseModel

from app.orders.schemas import OrderResponse


class KitchenBoardResponse(BaseModel):
    new: list[OrderResponse]
    preparing: list[OrderResponse]
    ready: list[OrderResponse]
