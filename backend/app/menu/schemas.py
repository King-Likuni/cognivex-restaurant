"""Pydantic schemas for menu management."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class MenuCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    display_order: int = Field(default=0, ge=0)


class MenuCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    display_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class MenuCategoryResponse(BaseModel):
    id: UUID
    restaurant_id: UUID
    name: str
    display_order: int
    is_active: bool

    model_config = {"from_attributes": True}


class MenuItemCreate(BaseModel):
    category_id: UUID
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    price: Decimal = Field(..., gt=Decimal("0.00"))
    image_url: str | None = None
    is_available: bool = True


class MenuItemUpdate(BaseModel):
    category_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    price: Decimal | None = Field(default=None, gt=Decimal("0.00"))
    image_url: str | None = None
    is_available: bool | None = None


class MenuItemAvailabilityUpdate(BaseModel):
    is_available: bool


class MenuItemResponse(BaseModel):
    id: UUID
    category_id: UUID
    restaurant_id: UUID
    name: str
    description: str | None
    price: Decimal
    image_url: str | None
    is_available: bool
    is_available_for_sale: bool = True
    stock_status: str = "UNTRACKED"
    stock_message: str | None = None

    model_config = {"from_attributes": True}
