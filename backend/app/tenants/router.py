"""Tenant API router: restaurant and branch management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.schemas import PasswordSetupTokenResponse
from app.core.database import get_db
from app.core.dependencies import (
    ensure_restaurant_access,
    get_current_active_user,
    require_admin,
    require_platform_reader,
    require_restaurant_access,
    require_restaurant_owner,
)
from app.tenants import service
from app.tenants.schemas import (
    BranchCreate,
    BranchResponse,
    BranchUpdate,
    PlatformRestaurantSummary,
    RestaurantCreate,
    RestaurantLifecycleUpdate,
    RestaurantOnboardingCreate,
    RestaurantOnboardingResponse,
    RestaurantPlatformNotesUpdate,
    RestaurantResponse,
    RestaurantSettingsResponse,
    RestaurantSettingsUpdate,
    RestaurantSetupStatus,
    RestaurantSubscriptionUpdate,
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
    "/onboard",
    response_model=RestaurantOnboardingResponse,
    status_code=status.HTTP_201_CREATED,
)
def onboard_restaurant(
    data: RestaurantOnboardingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Provision a restaurant, first branch, and owner setup link in one workflow."""
    try:
        restaurant, branch, owner, reset_token, raw_token = service.create_restaurant_onboarding(
            db,
            data,
            created_by=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RestaurantOnboardingResponse(
        restaurant=restaurant,
        branch=branch,
        owner={
            "id": owner.id,
            "email": owner.email,
            "first_name": owner.first_name,
            "last_name": owner.last_name,
            "is_active": owner.is_active,
            "role_name": owner.role.name if owner.role else None,
            "restaurant_id": owner.restaurant_id,
            "branch_ids": [assigned_branch.id for assigned_branch in owner.branches],
            "branch_assignments": [
                {
                    "id": assigned_branch.id,
                    "code": assigned_branch.code,
                    "name": assigned_branch.name,
                }
                for assigned_branch in sorted(
                    owner.branches,
                    key=lambda assigned_branch: assigned_branch.name.lower(),
                )
            ],
            "created_at": owner.created_at,
        },
        invite={
            "token": raw_token,
            "setup_url_path": f"/password-setup?token={raw_token}",
            "expires_at": reset_token.expires_at,
        },
    )


@router.get(
    "/platform",
    response_model=list[PlatformRestaurantSummary],
    dependencies=[Depends(require_platform_reader)],
)
def list_platform_restaurants(db: Session = Depends(get_db)):
    """List restaurants with platform-level lifecycle and ownership summary."""
    return service.list_platform_restaurants(db)


@router.get(
    "/{restaurant_id}/setup/status",
    response_model=RestaurantSetupStatus,
)
def get_restaurant_setup_status(
    restaurant_id: UUID,
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_restaurant_owner),
):
    """Return the owner setup readiness checklist for a restaurant."""
    ensure_restaurant_access(current_user, restaurant_id)
    setup_status = service.restaurant_setup_status(db, restaurant_id, branch_id=branch_id)
    if setup_status is None:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return setup_status


@router.patch(
    "/{restaurant_id}/lifecycle",
    response_model=RestaurantResponse,
)
def update_restaurant_lifecycle(
    restaurant_id: UUID,
    data: RestaurantLifecycleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Suspend or reactivate a restaurant tenant. Platform admins only."""
    try:
        restaurant = service.update_restaurant_lifecycle(
            db,
            restaurant_id,
            data.status,
            changed_by=current_user,
            suspension_reason=data.suspension_reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if restaurant is None:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return restaurant


@router.patch(
    "/{restaurant_id}/platform-notes",
    response_model=RestaurantResponse,
)
def update_restaurant_platform_notes(
    restaurant_id: UUID,
    data: RestaurantPlatformNotesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update private platform-only tenant notes. Platform admins only."""
    restaurant = service.update_restaurant_platform_notes(
        db,
        restaurant_id,
        data,
        changed_by=current_user,
    )
    if restaurant is None:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return restaurant


@router.patch(
    "/{restaurant_id}/subscription",
    response_model=RestaurantResponse,
)
def update_restaurant_subscription(
    restaurant_id: UUID,
    data: RestaurantSubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update tenant subscription state. Platform admins only."""
    try:
        restaurant = service.update_restaurant_subscription(
            db,
            restaurant_id,
            data,
            changed_by=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if restaurant is None:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return restaurant


@router.post(
    "/{restaurant_id}/owner-setup-link",
    response_model=PasswordSetupTokenResponse,
)
def create_owner_setup_link(
    restaurant_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a one-time password setup link for the tenant's active owner."""
    setup_token = service.create_owner_setup_link(db, restaurant_id, created_by=current_user)
    if setup_token is None:
        raise HTTPException(status_code=404, detail="Active owner not found")
    reset_token, raw_token = setup_token
    return PasswordSetupTokenResponse(
        token=raw_token,
        setup_url_path=f"/password-setup?token={raw_token}",
        expires_at=reset_token.expires_at,
    )


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
    """List all restaurants. Platform admins only."""
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
