"""Auth API router: login, register, and current-user endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.models import User
from app.auth.schemas import (
    LoginResponse,
    UserCreate,
    UserResponse,
)
from app.core.database import get_db
from app.core.dependencies import (
    RoleChecker,
    ensure_restaurant_access,
    get_current_active_user,
)
from app.core.security import create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])
require_user_creator = RoleChecker(["ADMIN", "OWNER", "MANAGER"])


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

    return LoginResponse(
        access_token=access_token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active,
            role_name=user.role.name if user.role else None,
            restaurant_id=user.restaurant_id,
        ),
    )


@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: User = Depends(get_current_active_user)):
    """Return the profile of the currently authenticated user."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        is_active=current_user.is_active,
        role_name=current_user.role.name if current_user.role else None,
        restaurant_id=current_user.restaurant_id,
    )


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

    Platform admins can provision tenant owners. Restaurant owners and managers
    can create staff only within their own restaurant.
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
    if current_role == "MANAGER" and requested_role == "OWNER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Managers cannot create restaurant owners",
        )

    try:
        user = service.create_user(db, user_in)
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
    )
