"""Pydantic schemas for restaurant and branch management."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.auth.schemas import PasswordSetupTokenResponse, UserResponse


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
    status: str = "ACTIVE"
    is_active: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class RestaurantOnboardingCreate(BaseModel):
    restaurant_name: str = Field(..., min_length=1, max_length=200)
    restaurant_code: str | None = Field(default=None, min_length=2, max_length=12)
    branch_name: str = Field(..., min_length=1, max_length=200)
    branch_code: str | None = Field(default=None, min_length=1, max_length=12)
    branch_location: str | None = Field(default=None, max_length=200)
    owner_email: EmailStr
    owner_first_name: str = Field(..., min_length=1, max_length=100)
    owner_last_name: str = Field(..., min_length=1, max_length=100)


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


class RestaurantOnboardingResponse(BaseModel):
    restaurant: RestaurantResponse
    branch: BranchResponse
    owner: UserResponse
    invite: PasswordSetupTokenResponse


class RestaurantLifecycleUpdate(BaseModel):
    status: Literal["ACTIVE", "SUSPENDED"]


class PlatformRestaurantSummary(BaseModel):
    id: UUID
    code: str
    name: str
    status: str
    is_active: bool
    branch_count: int
    owner_email: str | None
    owner_name: str | None
    created_at: datetime | None


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
