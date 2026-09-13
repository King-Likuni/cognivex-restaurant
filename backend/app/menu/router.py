"""Menu management API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.database import get_db
from app.core.dependencies import (
    ensure_restaurant_access,
    require_branch_access,
    require_cashier,
    require_manager,
)
from app.menu import service
from app.menu.schemas import (
    MenuCategoryCreate,
    MenuCategoryResponse,
    MenuCategoryUpdate,
    MenuItemAvailabilityUpdate,
    MenuItemCreate,
    MenuItemResponse,
    MenuItemUpdate,
)

router = APIRouter(prefix="/restaurants/{restaurant_id}/menu", tags=["Menu"])


@router.post(
    "/categories",
    response_model=MenuCategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    restaurant_id: UUID,
    data: MenuCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    ensure_restaurant_access(current_user, restaurant_id)
    return service.create_category(db, restaurant_id, data)


def menu_item_response(item, stock_status=None) -> MenuItemResponse:
    return MenuItemResponse(
        id=item.id,
        category_id=item.category_id,
        restaurant_id=item.restaurant_id,
        name=item.name,
        description=item.description,
        price=item.price,
        image_url=item.image_url,
        is_available=item.is_available,
        is_available_for_sale=(
            stock_status.is_available_for_sale if stock_status is not None else item.is_available
        ),
        stock_status=stock_status.stock_status if stock_status is not None else "UNTRACKED",
        stock_message=stock_status.stock_message if stock_status is not None else None,
    )


@router.get("/categories", response_model=list[MenuCategoryResponse])
def list_categories(
    restaurant_id: UUID,
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_cashier),
):
    ensure_restaurant_access(current_user, restaurant_id)
    return service.list_categories(db, restaurant_id, include_inactive=include_inactive)


@router.patch("/categories/{category_id}", response_model=MenuCategoryResponse)
def update_category(
    restaurant_id: UUID,
    category_id: UUID,
    data: MenuCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    ensure_restaurant_access(current_user, restaurant_id)
    category = service.update_category(db, restaurant_id, category_id, data)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.post("/items", response_model=MenuItemResponse, status_code=status.HTTP_201_CREATED)
def create_item(
    restaurant_id: UUID,
    data: MenuItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    ensure_restaurant_access(current_user, restaurant_id)
    try:
        return menu_item_response(service.create_item(db, restaurant_id, data))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/items", response_model=list[MenuItemResponse])
def list_items(
    restaurant_id: UUID,
    include_unavailable: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_cashier),
):
    ensure_restaurant_access(current_user, restaurant_id)
    return [
        menu_item_response(item)
        for item in service.list_items(
            db,
            restaurant_id,
            include_unavailable=include_unavailable,
        )
    ]


@router.get("/branches/{branch_id}/items", response_model=list[MenuItemResponse])
def list_branch_items(
    restaurant_id: UUID,
    branch_id: UUID,
    include_unavailable: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_cashier),
    branch_user: User = Depends(require_branch_access),
):
    ensure_restaurant_access(current_user, restaurant_id)
    if branch_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Branch access validation failed")
    try:
        return [
            menu_item_response(item, stock_status)
            for item, stock_status in service.list_branch_items(
                db,
                restaurant_id,
                branch_id,
                include_unavailable=include_unavailable,
            )
        ]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/items/{item_id}", response_model=MenuItemResponse)
def update_item(
    restaurant_id: UUID,
    item_id: UUID,
    data: MenuItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    ensure_restaurant_access(current_user, restaurant_id)
    try:
        item = service.update_item(db, restaurant_id, item_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Menu item not found")
    return menu_item_response(item)


@router.patch("/items/{item_id}/availability", response_model=MenuItemResponse)
def update_item_availability(
    restaurant_id: UUID,
    item_id: UUID,
    data: MenuItemAvailabilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_cashier),
):
    ensure_restaurant_access(current_user, restaurant_id)
    item = service.update_item_availability(db, restaurant_id, item_id, data)
    if item is None:
        raise HTTPException(status_code=404, detail="Menu item not found")
    return menu_item_response(item)
