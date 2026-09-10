"""Tenant API router: restaurant and branch management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.database import get_db
from app.core.dependencies import (
    ensure_restaurant_access,
    get_current_active_user,
    require_admin,
    require_restaurant_access,
    require_restaurant_owner,
)
from app.tenants import service
from app.tenants.schemas import (
    BranchCreate,
    BranchResponse,
    BranchUpdate,
    RestaurantCreate,
    RestaurantResponse,
    RestaurantSettingsResponse,
    RestaurantSettingsUpdate,
)

router = APIRouter(prefix="/restaurants", tags=["Restaurants"])


def require_branch_admin(restaurant_id: UUID, current_user: User) -> None:
    role_name = current_user.role.name if current_user.role else None
    if role_name == "ADMIN":
        return
    if role_name == "OWNER":
        ensure_restaurant_access(current_user, restaurant_id)
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only restaurant owners or platform admins can manage branches",
    )


# --------------------------------------------------------------------------- #
# Restaurant CRUD
# --------------------------------------------------------------------------- #
@router.post(
    "/",
    response_model=RestaurantResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_restaurant(
    data: RestaurantCreate,
    db: Session = Depends(get_db),
):
    """Create a new restaurant. Platform admins only."""
    restaurant = service.create_restaurant(db, data)
    return restaurant


@router.get("/", response_model=list[RestaurantResponse], dependencies=[Depends(require_admin)])
def list_restaurants(db: Session = Depends(get_db)):
    """List all active restaurants. Platform admins only."""
    return service.list_restaurants(db)


@router.get(
    "/{restaurant_id}",
    response_model=RestaurantResponse,
    dependencies=[Depends(require_restaurant_access)],
)
def get_restaurant(restaurant_id: UUID, db: Session = Depends(get_db)):
    restaurant = service.get_restaurant(db, restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return restaurant


# --------------------------------------------------------------------------- #
# Branch CRUD
# --------------------------------------------------------------------------- #
@router.post(
    "/{restaurant_id}/branches",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_branch(
    restaurant_id: UUID,
    data: BranchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new branch under a restaurant. Owners and platform admins only."""
    require_branch_admin(restaurant_id, current_user)
    restaurant = service.get_restaurant(db, restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return service.create_branch(db, restaurant_id, data, created_by=current_user)


@router.get(
    "/{restaurant_id}/branches",
    response_model=list[BranchResponse],
)
def list_branches(
    restaurant_id: UUID,
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_restaurant_access),
):
    """List branches the current user can operate for the restaurant."""
    role_name = current_user.role.name if current_user.role else None
    if include_inactive and role_name not in {"ADMIN", "OWNER"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only restaurant owners or platform admins can list inactive branches",
        )
    return service.list_accessible_branches(
        db,
        restaurant_id,
        current_user,
        include_inactive=include_inactive,
    )


@router.patch(
    "/{restaurant_id}/branches/{branch_id}",
    response_model=BranchResponse,
)
def update_branch(
    restaurant_id: UUID,
    branch_id: UUID,
    data: BranchUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update branch details or active status. Owners and platform admins only."""
    require_branch_admin(restaurant_id, current_user)
    try:
        branch = service.update_branch(db, restaurant_id, branch_id, data, changed_by=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    return branch


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
@router.get(
    "/{restaurant_id}/settings",
    response_model=RestaurantSettingsResponse,
    dependencies=[Depends(require_restaurant_owner)],
)
def get_settings(restaurant_id: UUID, db: Session = Depends(get_db)):
    settings = service.get_restaurant_settings(db, restaurant_id)
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")
    return settings


@router.put(
    "/{restaurant_id}/settings",
    response_model=RestaurantSettingsResponse,
    dependencies=[Depends(require_restaurant_owner)],
)
def update_settings(
    restaurant_id: UUID,
    data: RestaurantSettingsUpdate,
    db: Session = Depends(get_db),
):
    """Update restaurant settings. Owners only."""
    return service.update_restaurant_settings(db, restaurant_id, data)
