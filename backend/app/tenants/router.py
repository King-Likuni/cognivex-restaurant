"""Tenant API router: restaurant and branch management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.database import get_db
from app.core.dependencies import (
    require_admin,
    require_restaurant_access,
    require_restaurant_owner,
)
from app.tenants import service
from app.tenants.schemas import (
    BranchCreate,
    BranchResponse,
    RestaurantCreate,
    RestaurantResponse,
    RestaurantSettingsResponse,
    RestaurantSettingsUpdate,
)

router = APIRouter(prefix="/restaurants", tags=["Restaurants"])


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
    dependencies=[Depends(require_restaurant_owner)],
)
def create_branch(
    restaurant_id: UUID,
    data: BranchCreate,
    db: Session = Depends(get_db),
):
    """Create a new branch under a restaurant. Owners only."""
    restaurant = service.get_restaurant(db, restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return service.create_branch(db, restaurant_id, data)


@router.get(
    "/{restaurant_id}/branches",
    response_model=list[BranchResponse],
)
def list_branches(
    restaurant_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_restaurant_access),
):
    """List branches the current user can operate for the restaurant."""
    return service.list_accessible_branches(db, restaurant_id, current_user)


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
