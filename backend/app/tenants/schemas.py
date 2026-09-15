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
    subscription_status: str = "TRIAL"
    subscription_started_at: datetime | None = None
    subscription_renews_at: datetime | None = None
    suspension_reason: str | None = None
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
    suspension_reason: str | None = Field(default=None, max_length=300)


class RestaurantPlatformNotesUpdate(BaseModel):
    platform_notes: str | None = Field(default=None, max_length=2000)


class RestaurantSubscriptionUpdate(BaseModel):
    subscription_status: Literal["TRIAL", "ACTIVE", "OVERDUE", "CANCELLED"]
    subscription_started_at: datetime | None = None
    subscription_renews_at: datetime | None = None


class PlatformRestaurantSummary(BaseModel):
    id: UUID
    code: str
    name: str
    status: str
    subscription_status: str
    subscription_started_at: datetime | None
    subscription_renews_at: datetime | None
    suspension_reason: str | None
    platform_notes: str | None
    is_active: bool
    branch_count: int
    active_user_count: int
    owner_email: str | None
    owner_name: str | None
    owner_setup_expires_at: datetime | None
    owner_setup_expired: bool
    today_order_count: int
    today_revenue: Decimal
    pending_payment_count: int
    failed_payment_count: int
    low_stock_alert_count: int
    critical_stock_alert_count: int
    last_order_at: datetime | None
    order_access_status: str
    order_access_message: str | None
    order_access_blocked: bool
    subscription_grace_ends_at: datetime | None
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
