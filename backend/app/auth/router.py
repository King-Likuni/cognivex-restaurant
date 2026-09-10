"""Auth API router: login, register, and current-user endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.models import PasswordResetToken, User
from app.auth.schemas import (
    LoginResponse,
    MessageResponse,
    PasswordSetupConfirm,
    PasswordSetupPreviewResponse,
    PasswordSetupTokenResponse,
    StaffInviteCreate,
    StaffInviteResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.core.database import get_db
from app.core.dependencies import (
    RoleChecker,
    ensure_restaurant_access,
    get_current_active_user,
)
from app.core.security import create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])
require_user_creator = RoleChecker(["ADMIN", "OWNER"])
require_user_manager = RoleChecker(["ADMIN", "OWNER"])


def serialize_user(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        is_active=user.is_active,
        role_name=user.role.name if user.role else None,
        restaurant_id=user.restaurant_id,
        branch_ids=[branch.id for branch in user.branches],
    )


def serialize_password_setup_token(
    reset_token: PasswordResetToken,
    raw_token: str,
) -> PasswordSetupTokenResponse:
    return PasswordSetupTokenResponse(
        token=raw_token,
        setup_url_path=f"/password-setup?token={raw_token}",
        expires_at=reset_token.expires_at,
    )


def ensure_user_management_scope(
    current_user: User,
    *,
    restaurant_id: UUID | None,
) -> UUID | None:
    current_role = current_user.role.name if current_user.role else None
    if current_role == "ADMIN":
        return restaurant_id
    if current_user.restaurant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not assigned to a restaurant",
        )
    if restaurant_id is not None:
        ensure_restaurant_access(current_user, restaurant_id)
    return current_user.restaurant_id


def ensure_owner_safety(db: Session, user: User, user_in: UserUpdate) -> None:
    if (
        user.restaurant_id is None
        or not user.role
        or user.role.name != "OWNER"
        or not user.is_active
    ):
        return
    changes = user_in.model_dump(exclude_unset=True)
    deactivates_user = changes.get("is_active") is False
    demotes_owner = (
        "role_name" in changes
        and user_in.role_name is not None
        and user_in.role_name.upper() != "OWNER"
    )
    if not deactivates_user and not demotes_owner:
        return
    remaining_owners = service.count_active_restaurant_owners(
        db,
        user.restaurant_id,
        exclude_user_id=user.id,
    )
    if remaining_owners == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one active owner is required",
        )


@router.post("/login", response_model=LoginResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Authenticate a user and return a JWT access token.

    Uses OAuth2 password flow (username field = email).
    """
    user = service.authenticate_user(db, email=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={"role": user.role.name if user.role else None},
    )

    return LoginResponse(access_token=access_token, user=serialize_user(user))


@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: User = Depends(get_current_active_user)):
    """Return the profile of the currently authenticated user."""
    return serialize_user(current_user)


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_creator),
):
    """Create a new user.

    Platform admins can provision tenant owners. Restaurant owners can create
    staff only within their own restaurant.
    """
    current_role = current_user.role.name if current_user.role else None
    requested_role = user_in.role_name.upper()
    if current_role != "ADMIN":
        if requested_role == "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Restaurant users cannot create platform admins",
            )
        if user_in.restaurant_id is not None:
            ensure_restaurant_access(current_user, user_in.restaurant_id)
    try:
        user = service.create_user(db, user_in, created_by=current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        is_active=user.is_active,
        role_name=user.role.name if user.role else None,
        restaurant_id=user.restaurant_id,
        branch_ids=[branch.id for branch in user.branches],
    )


@router.post(
    "/users/invite",
    response_model=StaffInviteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user_invite(
    user_in: StaffInviteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_creator),
):
    """Create staff and return a one-time password setup link."""
    current_role = current_user.role.name if current_user.role else None
    requested_role = user_in.role_name.upper()
    if current_role != "ADMIN":
        if requested_role == "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Restaurant users cannot create platform admins",
            )
        if user_in.restaurant_id is not None:
            ensure_restaurant_access(current_user, user_in.restaurant_id)

    try:
        user, reset_token, raw_token = service.create_user_invite(
            db,
            user_in,
            created_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return StaffInviteResponse(
        user=serialize_user(user),
        invite=serialize_password_setup_token(reset_token, raw_token),
    )


@router.get("/users", response_model=list[UserResponse])
def list_users(
    restaurant_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_manager),
):
    """List platform or restaurant users. Owners are scoped to their restaurant."""
    scoped_restaurant_id = ensure_user_management_scope(
        current_user,
        restaurant_id=restaurant_id,
    )
    users = service.list_users(db, scoped_restaurant_id)
    return [serialize_user(user) for user in users]


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_manager),
):
    """Update staff role, branch assignments, and active status."""
    user = service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    current_role = current_user.role.name if current_user.role else None
    if current_role != "ADMIN":
        ensure_restaurant_access(current_user, user.restaurant_id)
        if user_in.role_name is not None and user_in.role_name.upper() == "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Restaurant users cannot create platform admins",
            )
    if user.id == current_user.id and user_in.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account",
        )

    ensure_owner_safety(db, user, user_in)
    try:
        updated_user = service.update_user(db, user, user_in, changed_by=current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return serialize_user(updated_user)


@router.post("/users/{user_id}/password-reset", response_model=PasswordSetupTokenResponse)
def create_staff_password_reset(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_manager),
):
    """Create a one-time password setup link for an existing active staff member."""
    user = service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    current_role = current_user.role.name if current_user.role else None
    if current_role != "ADMIN":
        ensure_restaurant_access(current_user, user.restaurant_id)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive users must be reactivated before password reset",
        )

    reset_token, raw_token = service.create_password_setup_token(
        db,
        user,
        created_by=current_user.id,
    )
    return serialize_password_setup_token(reset_token, raw_token)


@router.post("/password-setup/confirm", response_model=MessageResponse)
def confirm_password_setup(data: PasswordSetupConfirm, db: Session = Depends(get_db)):
    """Set a password using a valid one-time setup token."""
    user = service.set_password_with_token(db, data.token, data.password)
    if user is None:
        raise HTTPException(status_code=404, detail="Password setup link is invalid or expired")
    return MessageResponse(detail="Password updated")


@router.get("/password-setup/{token}", response_model=PasswordSetupPreviewResponse)
def read_password_setup_token(token: str, db: Session = Depends(get_db)):
    """Preview a valid password setup token without authenticating."""
    reset_token = service.get_valid_password_setup_token(db, token)
    if reset_token is None:
        raise HTTPException(status_code=404, detail="Password setup link is invalid or expired")
    user = reset_token.user
    return PasswordSetupPreviewResponse(
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role_name=user.role.name if user.role else None,
        expires_at=reset_token.expires_at,
    )
