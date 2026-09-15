"""Pydantic schemas for authentication requests and responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

PLATFORM_ROLE_DESCRIPTION = "One of: ADMIN, SUPPORT, FINANCE"
RESTAURANT_ROLE_DESCRIPTION = "One of: OWNER, MANAGER, CASHIER, KITCHEN, INVENTORY"


# --------------------------------------------------------------------------- #
# Request schemas
# --------------------------------------------------------------------------- #
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role_name: str = Field(
        ...,
        description=f"{PLATFORM_ROLE_DESCRIPTION}, OWNER, MANAGER, CASHIER, KITCHEN, INVENTORY",
    )
    restaurant_id: UUID | None = None
    branch_ids: list[UUID] = Field(default_factory=list)


class UserUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    role_name: str | None = Field(
        default=None,
        description=f"{PLATFORM_ROLE_DESCRIPTION}, OWNER, MANAGER, CASHIER, KITCHEN, INVENTORY",
    )
    branch_ids: list[UUID] | None = None
    is_active: bool | None = None


class StaffInviteCreate(BaseModel):
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role_name: str = Field(
        ...,
        description=RESTAURANT_ROLE_DESCRIPTION,
    )
    restaurant_id: UUID | None = None
    branch_ids: list[UUID] = Field(default_factory=list)


class PlatformUserInviteCreate(BaseModel):
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role_name: str = Field(..., description=PLATFORM_ROLE_DESCRIPTION)


class PlatformUserUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    role_name: str | None = Field(default=None, description=PLATFORM_ROLE_DESCRIPTION)
    is_active: bool | None = None


class PasswordSetupConfirm(BaseModel):
    token: str = Field(..., min_length=32)
    password: str = Field(..., min_length=8)


# --------------------------------------------------------------------------- #
# Response schemas
# --------------------------------------------------------------------------- #
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserBranchAssignmentResponse(BaseModel):
    id: UUID
    code: str
    name: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    first_name: str | None
    last_name: str | None
    is_active: bool
    role_name: str | None = None
    restaurant_id: UUID | None = None
    branch_ids: list[UUID] = Field(default_factory=list)
    branch_assignments: list[UserBranchAssignmentResponse] = Field(default_factory=list)
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class PasswordSetupTokenResponse(BaseModel):
    token: str
    setup_url_path: str
    expires_at: datetime


class StaffInviteResponse(BaseModel):
    user: UserResponse
    invite: PasswordSetupTokenResponse


class PlatformUserInviteResponse(BaseModel):
    user: UserResponse
    invite: PasswordSetupTokenResponse


class PasswordSetupPreviewResponse(BaseModel):
    email: str
    first_name: str | None
    last_name: str | None
    role_name: str | None
    expires_at: datetime


class MessageResponse(BaseModel):
    detail: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
