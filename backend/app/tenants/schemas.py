"""Pydantic schemas for restaurant and branch management."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Restaurant
# --------------------------------------------------------------------------- #
class RestaurantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str | None = Field(default=None, min_length=2, max_length=12)


class RestaurantResponse(BaseModel):
    id: UUID
    code: str
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# Branch
# --------------------------------------------------------------------------- #
class BranchCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str | None = Field(default=None, min_length=1, max_length=12)
    location: str | None = None


class BranchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, min_length=1, max_length=12)
    location: str | None = None
    is_active: bool | None = None


class BranchResponse(BaseModel):
    id: UUID
    restaurant_id: UUID
    code: str
    name: str
    location: str | None
    is_active: bool

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# Restaurant Settings
# --------------------------------------------------------------------------- #
class RestaurantSettingsUpdate(BaseModel):
    currency: str = "BWP"
    max_unpaid_amount: Decimal = Decimal("50.00")
    max_uncollected_orders: int = 1
    remote_cash_enabled: bool = True


class RestaurantSettingsResponse(BaseModel):
    restaurant_id: UUID
    currency: str
    max_unpaid_amount: Decimal
    max_uncollected_orders: int
    remote_cash_enabled: bool

    model_config = {"from_attributes": True}
