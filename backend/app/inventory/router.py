"""Inventory API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.database import get_db
from app.core.dependencies import (
    RoleChecker,
    ensure_restaurant_access,
    require_branch_access,
    require_inventory,
    require_inventory_reader,
    require_manager,
)
from app.inventory import service
from app.inventory.enums import StockMovementType
from app.inventory.schemas import (
    IngredientCreate,
    IngredientResponse,
    IngredientUpdate,
    LowStockAlertResponse,
    RecipeItemCreate,
    RecipeItemResponse,
    RecipeItemUpdate,
    StockBalanceResponse,
    StockLocationCreate,
    StockLocationResponse,
    StockMovementCreate,
    StockMovementResponse,
    StockThresholdResponse,
    StockThresholdUpsert,
)

router = APIRouter(prefix="/restaurants/{restaurant_id}/inventory", tags=["Inventory"])
require_inventory_alert_reader = RoleChecker(
    ["OWNER", "MANAGER", "CASHIER", "KITCHEN", "INVENTORY"]
)


def recipe_response(recipe_item) -> RecipeItemResponse:
    return RecipeItemResponse(
        id=recipe_item.id,
        menu_item_id=recipe_item.menu_item_id,
        ingredient_id=recipe_item.ingredient_id,
        ingredient_name=recipe_item.ingredient.name,
        unit=recipe_item.ingredient.unit,
        quantity=recipe_item.quantity,
    )


def threshold_response(threshold) -> StockThresholdResponse:
    return StockThresholdResponse(
        id=threshold.id,
        restaurant_id=threshold.restaurant_id,
        branch_id=threshold.branch_id,
        ingredient_id=threshold.ingredient_id,
        ingredient_name=threshold.ingredient.name,
        unit=threshold.ingredient.unit,
        warning_quantity=threshold.warning_quantity,
        critical_quantity=threshold.critical_quantity,
    )


@router.post(
    "/ingredients",
    response_model=IngredientResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ingredient(
    restaurant_id: UUID,
    data: IngredientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    ensure_restaurant_access(current_user, restaurant_id)
    try:
        return service.create_ingredient(db, restaurant_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/ingredients", response_model=list[IngredientResponse])
def list_ingredients(
    restaurant_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_inventory_reader),
):
    ensure_restaurant_access(current_user, restaurant_id)
    return service.list_ingredients(db, restaurant_id)


@router.patch("/ingredients/{ingredient_id}", response_model=IngredientResponse)
def update_ingredient(
    restaurant_id: UUID,
    ingredient_id: UUID,
    data: IngredientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    ensure_restaurant_access(current_user, restaurant_id)
    try:
        ingredient = service.update_ingredient(db, restaurant_id, ingredient_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if ingredient is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return ingredient


@router.post(
    "/branches/{branch_id}/locations",
    response_model=StockLocationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_stock_location(
    restaurant_id: UUID,
    branch_id: UUID,
    data: StockLocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
    branch_user: User = Depends(require_branch_access),
):
    ensure_restaurant_access(current_user, restaurant_id)
    if branch_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Branch access validation failed")
    try:
        return service.create_stock_location(db, restaurant_id, branch_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/branches/{branch_id}/locations", response_model=list[StockLocationResponse])
def list_stock_locations(
    restaurant_id: UUID,
    branch_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_inventory_reader),
    branch_user: User = Depends(require_branch_access),
):
    ensure_restaurant_access(current_user, restaurant_id)
    if branch_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Branch access validation failed")
    return service.list_stock_locations(db, restaurant_id, branch_id)


@router.put(
    "/menu-items/{menu_item_id}/recipe-items",
    response_model=RecipeItemResponse,
)
def upsert_recipe_item(
    restaurant_id: UUID,
    menu_item_id: UUID,
    data: RecipeItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    ensure_restaurant_access(current_user, restaurant_id)
    try:
        return recipe_response(service.upsert_recipe_item(db, restaurant_id, menu_item_id, data))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/menu-items/{menu_item_id}/recipe-items", response_model=list[RecipeItemResponse])
def list_recipe_items(
    restaurant_id: UUID,
    menu_item_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    ensure_restaurant_access(current_user, restaurant_id)
    try:
        return [
            recipe_response(recipe_item)
            for recipe_item in service.list_recipe_items(db, restaurant_id, menu_item_id)
        ]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch(
    "/menu-items/{menu_item_id}/recipe-items/{recipe_item_id}",
    response_model=RecipeItemResponse,
)
def update_recipe_item(
    restaurant_id: UUID,
    menu_item_id: UUID,
    recipe_item_id: UUID,
    data: RecipeItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    ensure_restaurant_access(current_user, restaurant_id)
    try:
        recipe_item = service.update_recipe_item(
            db,
            restaurant_id,
            menu_item_id,
            recipe_item_id,
            data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if recipe_item is None:
        raise HTTPException(status_code=404, detail="Recipe item not found")
    return recipe_response(recipe_item)


@router.delete(
    "/menu-items/{menu_item_id}/recipe-items/{recipe_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_recipe_item(
    restaurant_id: UUID,
    menu_item_id: UUID,
    recipe_item_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    ensure_restaurant_access(current_user, restaurant_id)
    try:
        deleted = service.delete_recipe_item(db, restaurant_id, menu_item_id, recipe_item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Recipe item not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/branches/{branch_id}/movements",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_stock_movement(
    restaurant_id: UUID,
    branch_id: UUID,
    data: StockMovementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_inventory),
    branch_user: User = Depends(require_branch_access),
):
    ensure_restaurant_access(current_user, restaurant_id)
    if branch_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Branch access validation failed")
    role_name = current_user.role.name if current_user.role else None
    if role_name == "INVENTORY" and data.movement_type != StockMovementType.RECEIVED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inventory users can only receive stock",
        )
    try:
        return service.create_stock_movement(db, restaurant_id, branch_id, data, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/branches/{branch_id}/movements", response_model=list[StockMovementResponse])
def list_stock_movements(
    restaurant_id: UUID,
    branch_id: UUID,
    ingredient_id: UUID | None = Query(default=None),
    stock_location_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_inventory),
    branch_user: User = Depends(require_branch_access),
):
    ensure_restaurant_access(current_user, restaurant_id)
    if branch_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Branch access validation failed")
    return service.list_stock_movements(
        db,
        restaurant_id,
        branch_id,
        ingredient_id=ingredient_id,
        stock_location_id=stock_location_id,
    )


@router.get("/branches/{branch_id}/balances", response_model=list[StockBalanceResponse])
def list_stock_balances(
    restaurant_id: UUID,
    branch_id: UUID,
    stock_location_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_inventory_reader),
    branch_user: User = Depends(require_branch_access),
):
    ensure_restaurant_access(current_user, restaurant_id)
    if branch_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Branch access validation failed")
    return [
        StockBalanceResponse(
            ingredient_id=ingredient.id,
            ingredient_name=ingredient.name,
            unit=ingredient.unit,
            quantity_on_hand=quantity,
        )
        for ingredient, quantity in service.list_stock_balances(
            db,
            restaurant_id,
            branch_id,
            stock_location_id=stock_location_id,
        )
    ]


@router.put(
    "/branches/{branch_id}/thresholds/{ingredient_id}",
    response_model=StockThresholdResponse,
)
def upsert_stock_threshold(
    restaurant_id: UUID,
    branch_id: UUID,
    ingredient_id: UUID,
    data: StockThresholdUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
    branch_user: User = Depends(require_branch_access),
):
    ensure_restaurant_access(current_user, restaurant_id)
    if branch_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Branch access validation failed")
    try:
        return threshold_response(
            service.upsert_stock_threshold(
                db,
                restaurant_id,
                branch_id,
                ingredient_id,
                data,
                current_user,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/branches/{branch_id}/thresholds", response_model=list[StockThresholdResponse])
def list_stock_thresholds(
    restaurant_id: UUID,
    branch_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
    branch_user: User = Depends(require_branch_access),
):
    ensure_restaurant_access(current_user, restaurant_id)
    if branch_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Branch access validation failed")
    return [
        threshold_response(threshold)
        for threshold in service.list_stock_thresholds(db, restaurant_id, branch_id)
    ]


@router.get(
    "/branches/{branch_id}/low-stock-alerts",
    response_model=list[LowStockAlertResponse],
)
def list_low_stock_alerts(
    restaurant_id: UUID,
    branch_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_inventory_alert_reader),
    branch_user: User = Depends(require_branch_access),
):
    ensure_restaurant_access(current_user, restaurant_id)
    if branch_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Branch access validation failed")
    return [
        LowStockAlertResponse(
            ingredient_id=threshold.ingredient_id,
            ingredient_name=threshold.ingredient.name,
            unit=threshold.ingredient.unit,
            quantity_on_hand=quantity_on_hand,
            warning_quantity=threshold.warning_quantity,
            critical_quantity=threshold.critical_quantity,
            severity=severity,
            message=message,
        )
        for threshold, quantity_on_hand, severity, message in service.list_low_stock_alerts(
            db,
            restaurant_id,
            branch_id,
        )
    ]
