"""Inventory service layer."""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.auth.models import User
from app.inventory.enums import StockMovementType
from app.inventory.models import (
    Ingredient,
    MenuItemRecipeItem,
    StockLocation,
    StockMovement,
    StockThreshold,
)
from app.inventory.schemas import (
    IngredientCreate,
    IngredientUpdate,
    RecipeItemCreate,
    RecipeItemUpdate,
    StockLocationCreate,
    StockMovementCreate,
    StockThresholdUpsert,
)
from app.menu.models import MenuItem
from app.orders.models import Order
from app.tenants.models import Branch


@dataclass(frozen=True)
class MenuItemStockStatus:
    is_available_for_sale: bool
    stock_status: str
    stock_message: str | None = None


def get_branch(db: Session, restaurant_id: UUID, branch_id: UUID) -> Branch | None:
    return (
        db.query(Branch)
        .filter(
            Branch.id == branch_id,
            Branch.restaurant_id == restaurant_id,
            Branch.is_active.is_(True),
        )
        .first()
    )


def create_ingredient(db: Session, restaurant_id: UUID, data: IngredientCreate) -> Ingredient:
    existing = (
        db.query(Ingredient)
        .filter(
            Ingredient.restaurant_id == restaurant_id,
            func.lower(Ingredient.name) == data.name.strip().lower(),
        )
        .first()
    )
    if existing is not None:
        raise ValueError("Ingredient already exists")

    ingredient = Ingredient(
        restaurant_id=restaurant_id,
        name=data.name.strip(),
        unit=data.unit.strip(),
    )
    db.add(ingredient)
    db.commit()
    db.refresh(ingredient)
    return ingredient


def list_ingredients(db: Session, restaurant_id: UUID) -> list[Ingredient]:
    return (
        db.query(Ingredient)
        .filter(Ingredient.restaurant_id == restaurant_id)
        .order_by(Ingredient.name)
        .all()
    )


def get_ingredient(db: Session, restaurant_id: UUID, ingredient_id: UUID) -> Ingredient | None:
    return (
        db.query(Ingredient)
        .filter(Ingredient.restaurant_id == restaurant_id, Ingredient.id == ingredient_id)
        .first()
    )


def update_ingredient(
    db: Session,
    restaurant_id: UUID,
    ingredient_id: UUID,
    data: IngredientUpdate,
) -> Ingredient | None:
    ingredient = get_ingredient(db, restaurant_id, ingredient_id)
    if ingredient is None:
        return None

    updates = data.model_dump(exclude_unset=True)
    if "name" in updates:
        name = updates["name"].strip()
        duplicate = (
            db.query(Ingredient)
            .filter(
                Ingredient.restaurant_id == restaurant_id,
                Ingredient.id != ingredient_id,
                func.lower(Ingredient.name) == name.lower(),
            )
            .first()
        )
        if duplicate is not None:
            raise ValueError("Ingredient already exists")
        ingredient.name = name
    if "unit" in updates:
        ingredient.unit = updates["unit"].strip()

    db.commit()
    db.refresh(ingredient)
    return ingredient


def create_stock_location(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    data: StockLocationCreate,
) -> StockLocation:
    branch = get_branch(db, restaurant_id, branch_id)
    if branch is None:
        raise ValueError("Branch not found")

    existing = (
        db.query(StockLocation)
        .filter(
            StockLocation.branch_id == branch_id,
            func.lower(StockLocation.name) == data.name.strip().lower(),
        )
        .first()
    )
    if existing is not None:
        raise ValueError("Stock location already exists for this branch")

    location = StockLocation(
        restaurant_id=restaurant_id,
        branch_id=branch_id,
        name=data.name.strip(),
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


def list_stock_locations(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
) -> list[StockLocation]:
    return (
        db.query(StockLocation)
        .filter(StockLocation.restaurant_id == restaurant_id, StockLocation.branch_id == branch_id)
        .order_by(StockLocation.name)
        .all()
    )


def get_stock_location(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    stock_location_id: UUID,
) -> StockLocation | None:
    return (
        db.query(StockLocation)
        .filter(
            StockLocation.id == stock_location_id,
            StockLocation.restaurant_id == restaurant_id,
            StockLocation.branch_id == branch_id,
        )
        .first()
    )


def get_menu_item(db: Session, restaurant_id: UUID, menu_item_id: UUID) -> MenuItem | None:
    return (
        db.query(MenuItem)
        .filter(MenuItem.id == menu_item_id, MenuItem.restaurant_id == restaurant_id)
        .first()
    )


def upsert_recipe_item(
    db: Session,
    restaurant_id: UUID,
    menu_item_id: UUID,
    data: RecipeItemCreate,
) -> MenuItemRecipeItem:
    menu_item = get_menu_item(db, restaurant_id, menu_item_id)
    if menu_item is None:
        raise ValueError("Menu item not found")
    ingredient = get_ingredient(db, restaurant_id, data.ingredient_id)
    if ingredient is None:
        raise ValueError("Ingredient not found")

    recipe_item = (
        db.query(MenuItemRecipeItem)
        .filter(
            MenuItemRecipeItem.menu_item_id == menu_item_id,
            MenuItemRecipeItem.ingredient_id == data.ingredient_id,
        )
        .first()
    )
    if recipe_item is None:
        recipe_item = MenuItemRecipeItem(
            menu_item_id=menu_item_id,
            ingredient_id=data.ingredient_id,
            quantity=data.quantity,
        )
        db.add(recipe_item)
    else:
        recipe_item.quantity = data.quantity

    db.commit()
    db.refresh(recipe_item)
    return recipe_item


def list_recipe_items(
    db: Session,
    restaurant_id: UUID,
    menu_item_id: UUID,
) -> list[MenuItemRecipeItem]:
    menu_item = get_menu_item(db, restaurant_id, menu_item_id)
    if menu_item is None:
        raise ValueError("Menu item not found")
    return (
        db.query(MenuItemRecipeItem)
        .join(Ingredient, Ingredient.id == MenuItemRecipeItem.ingredient_id)
        .filter(
            MenuItemRecipeItem.menu_item_id == menu_item_id,
            Ingredient.restaurant_id == restaurant_id,
        )
        .order_by(Ingredient.name)
        .all()
    )


def update_recipe_item(
    db: Session,
    restaurant_id: UUID,
    menu_item_id: UUID,
    recipe_item_id: UUID,
    data: RecipeItemUpdate,
) -> MenuItemRecipeItem | None:
    menu_item = get_menu_item(db, restaurant_id, menu_item_id)
    if menu_item is None:
        raise ValueError("Menu item not found")
    recipe_item = (
        db.query(MenuItemRecipeItem)
        .join(Ingredient, Ingredient.id == MenuItemRecipeItem.ingredient_id)
        .filter(
            MenuItemRecipeItem.id == recipe_item_id,
            MenuItemRecipeItem.menu_item_id == menu_item_id,
            Ingredient.restaurant_id == restaurant_id,
        )
        .first()
    )
    if recipe_item is None:
        return None
    recipe_item.quantity = data.quantity
    db.commit()
    db.refresh(recipe_item)
    return recipe_item


def delete_recipe_item(
    db: Session,
    restaurant_id: UUID,
    menu_item_id: UUID,
    recipe_item_id: UUID,
) -> bool:
    menu_item = get_menu_item(db, restaurant_id, menu_item_id)
    if menu_item is None:
        raise ValueError("Menu item not found")
    recipe_item = (
        db.query(MenuItemRecipeItem)
        .join(Ingredient, Ingredient.id == MenuItemRecipeItem.ingredient_id)
        .filter(
            MenuItemRecipeItem.id == recipe_item_id,
            MenuItemRecipeItem.menu_item_id == menu_item_id,
            Ingredient.restaurant_id == restaurant_id,
        )
        .first()
    )
    if recipe_item is None:
        return False
    db.delete(recipe_item)
    db.commit()
    return True


def get_stock_balance(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    ingredient_id: UUID,
    *,
    stock_location_id: UUID | None = None,
) -> Decimal:
    query = db.query(func.coalesce(func.sum(StockMovement.quantity), 0)).filter(
        StockMovement.restaurant_id == restaurant_id,
        StockMovement.branch_id == branch_id,
        StockMovement.ingredient_id == ingredient_id,
    )
    if stock_location_id is not None:
        query = query.filter(StockMovement.stock_location_id == stock_location_id)
    return Decimal(query.scalar() or 0)


def list_stock_balances(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    *,
    stock_location_id: UUID | None = None,
) -> list[tuple[Ingredient, Decimal]]:
    grouped = (
        db.query(StockMovement.ingredient_id, func.coalesce(func.sum(StockMovement.quantity), 0))
        .filter(
            StockMovement.restaurant_id == restaurant_id,
            StockMovement.branch_id == branch_id,
        )
        .group_by(StockMovement.ingredient_id)
    )
    if stock_location_id is not None:
        grouped = grouped.filter(StockMovement.stock_location_id == stock_location_id)
    balances_by_ingredient = {
        ingredient_id: Decimal(quantity or 0) for ingredient_id, quantity in grouped.all()
    }
    ingredients = list_ingredients(db, restaurant_id)
    return [
        (ingredient, balances_by_ingredient.get(ingredient.id, Decimal("0.000")))
        for ingredient in ingredients
    ]


def get_thresholds_by_ingredient(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
) -> dict[UUID, StockThreshold]:
    return {
        threshold.ingredient_id: threshold
        for threshold in db.query(StockThreshold)
        .filter(
            StockThreshold.restaurant_id == restaurant_id,
            StockThreshold.branch_id == branch_id,
        )
        .all()
    }


def get_balances_by_ingredient(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    *,
    stock_location_id: UUID | None = None,
) -> dict[UUID, Decimal]:
    grouped = (
        db.query(StockMovement.ingredient_id, func.coalesce(func.sum(StockMovement.quantity), 0))
        .filter(
            StockMovement.restaurant_id == restaurant_id,
            StockMovement.branch_id == branch_id,
        )
        .group_by(StockMovement.ingredient_id)
    )
    if stock_location_id is not None:
        grouped = grouped.filter(StockMovement.stock_location_id == stock_location_id)
    return {ingredient_id: Decimal(quantity or 0) for ingredient_id, quantity in grouped.all()}


def summarize_menu_item_stock(
    *,
    item_name: str,
    required_by_ingredient: dict[UUID, Decimal],
    ingredients_by_id: dict[UUID, Ingredient],
    balances_by_ingredient: dict[UUID, Decimal],
    thresholds_by_ingredient: dict[UUID, StockThreshold],
) -> MenuItemStockStatus:
    if not required_by_ingredient:
        return MenuItemStockStatus(
            is_available_for_sale=True,
            stock_status="UNTRACKED",
            stock_message="No recipe stock tracking configured",
        )

    low_messages: list[str] = []
    for ingredient_id, required_quantity in required_by_ingredient.items():
        ingredient = ingredients_by_id[ingredient_id]
        quantity_on_hand = balances_by_ingredient.get(ingredient_id, Decimal("0.000"))
        threshold = thresholds_by_ingredient.get(ingredient_id)
        if quantity_on_hand < required_quantity:
            return MenuItemStockStatus(
                is_available_for_sale=False,
                stock_status="OUT_OF_STOCK",
                stock_message=f"{item_name} cannot be sold: not enough {ingredient.name}.",
            )
        if threshold is not None and quantity_on_hand <= threshold.critical_quantity:
            return MenuItemStockStatus(
                is_available_for_sale=False,
                stock_status="CRITICAL_STOCK",
                stock_message=(
                    f"{item_name} is paused: {ingredient.name} is at critical stock level."
                ),
            )
        if threshold is not None and quantity_on_hand <= threshold.warning_quantity:
            low_messages.append(
                f"{ingredient.name} is low ({quantity_on_hand:.3f} {ingredient.unit})"
            )

    if low_messages:
        return MenuItemStockStatus(
            is_available_for_sale=True,
            stock_status="LOW_STOCK",
            stock_message=f"{item_name} can still be sold, but {'; '.join(low_messages)}.",
        )
    return MenuItemStockStatus(
        is_available_for_sale=True,
        stock_status="AVAILABLE",
        stock_message="Stock is available",
    )


def get_menu_item_stock_statuses(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    menu_item_ids: list[UUID],
) -> dict[UUID, MenuItemStockStatus]:
    if not menu_item_ids:
        return {}

    location = get_default_consumption_location(db, restaurant_id, branch_id)
    balances_by_ingredient = get_balances_by_ingredient(
        db,
        restaurant_id,
        branch_id,
        stock_location_id=location.id if location else None,
    )
    thresholds_by_ingredient = get_thresholds_by_ingredient(db, restaurant_id, branch_id)
    recipe_items = (
        db.query(MenuItemRecipeItem)
        .join(Ingredient, Ingredient.id == MenuItemRecipeItem.ingredient_id)
        .filter(
            MenuItemRecipeItem.menu_item_id.in_(menu_item_ids),
            Ingredient.restaurant_id == restaurant_id,
        )
        .all()
    )
    required_by_item: dict[UUID, dict[UUID, Decimal]] = defaultdict(dict)
    ingredients_by_id: dict[UUID, Ingredient] = {}
    for recipe_item in recipe_items:
        required_by_item[recipe_item.menu_item_id][recipe_item.ingredient_id] = Decimal(
            recipe_item.quantity
        )
        ingredients_by_id[recipe_item.ingredient_id] = recipe_item.ingredient

    items = (
        db.query(MenuItem)
        .filter(MenuItem.restaurant_id == restaurant_id, MenuItem.id.in_(menu_item_ids))
        .all()
    )
    return {
        item.id: (
            MenuItemStockStatus(
                is_available_for_sale=False,
                stock_status="MANUALLY_UNAVAILABLE",
                stock_message=f"{item.name} is currently unavailable.",
            )
            if not item.is_available
            else summarize_menu_item_stock(
                item_name=item.name,
                required_by_ingredient=required_by_item.get(item.id, {}),
                ingredients_by_id=ingredients_by_id,
                balances_by_ingredient=balances_by_ingredient,
                thresholds_by_ingredient=thresholds_by_ingredient,
            )
        )
        for item in items
    }


def validate_order_stock_available(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    items,
) -> None:
    menu_item_ids = [line.menu_item_id for line in items]
    if not menu_item_ids:
        return
    recipe_items = (
        db.query(MenuItemRecipeItem)
        .join(Ingredient, Ingredient.id == MenuItemRecipeItem.ingredient_id)
        .filter(
            MenuItemRecipeItem.menu_item_id.in_(menu_item_ids),
            Ingredient.restaurant_id == restaurant_id,
        )
        .all()
    )
    if not recipe_items:
        return

    location = get_default_consumption_location(db, restaurant_id, branch_id)
    if location is None:
        raise ValueError("Stock location is required before selling recipe-based items")

    ordered_quantities: dict[UUID, int] = defaultdict(int)
    for line in items:
        ordered_quantities[line.menu_item_id] += line.quantity

    required_by_ingredient: dict[UUID, Decimal] = defaultdict(lambda: Decimal("0.000"))
    ingredients_by_id: dict[UUID, Ingredient] = {}
    for recipe_item in recipe_items:
        required_by_ingredient[recipe_item.ingredient_id] += (
            Decimal(recipe_item.quantity) * ordered_quantities[recipe_item.menu_item_id]
        )
        ingredients_by_id[recipe_item.ingredient_id] = recipe_item.ingredient

    thresholds_by_ingredient = get_thresholds_by_ingredient(db, restaurant_id, branch_id)
    for ingredient_id, required_quantity in required_by_ingredient.items():
        ingredient = ingredients_by_id[ingredient_id]
        quantity_on_hand = get_stock_balance(
            db,
            restaurant_id,
            branch_id,
            ingredient_id,
            stock_location_id=location.id,
        )
        if quantity_on_hand < required_quantity:
            raise ValueError(f"Insufficient stock for ingredient '{ingredient.name}'")
        threshold = thresholds_by_ingredient.get(ingredient_id)
        if threshold is not None and quantity_on_hand <= threshold.critical_quantity:
            raise ValueError(f"Ingredient '{ingredient.name}' is at critical stock level")


def upsert_stock_threshold(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    ingredient_id: UUID,
    data: StockThresholdUpsert,
    updated_by: User,
) -> StockThreshold:
    branch = get_branch(db, restaurant_id, branch_id)
    if branch is None:
        raise ValueError("Branch not found")
    ingredient = get_ingredient(db, restaurant_id, ingredient_id)
    if ingredient is None:
        raise ValueError("Ingredient not found")

    threshold = (
        db.query(StockThreshold)
        .filter(
            StockThreshold.restaurant_id == restaurant_id,
            StockThreshold.branch_id == branch_id,
            StockThreshold.ingredient_id == ingredient_id,
        )
        .first()
    )
    previous_values = None
    if threshold is None:
        threshold = StockThreshold(
            restaurant_id=restaurant_id,
            branch_id=branch_id,
            ingredient_id=ingredient_id,
            warning_quantity=data.warning_quantity,
            critical_quantity=data.critical_quantity,
            updated_by=updated_by.id,
        )
        db.add(threshold)
    else:
        previous_values = {
            "warning_quantity": str(threshold.warning_quantity),
            "critical_quantity": str(threshold.critical_quantity),
        }
        threshold.warning_quantity = data.warning_quantity
        threshold.critical_quantity = data.critical_quantity
        threshold.updated_by = updated_by.id

    db.flush()
    db.add(
        AuditLog(
            restaurant_id=restaurant_id,
            user_id=updated_by.id,
            action="STOCK_THRESHOLD_UPDATED",
            entity_type="stock_threshold",
            entity_id=threshold.id,
            old_values=previous_values,
            new_values={
                "branch_id": str(branch_id),
                "ingredient_id": str(ingredient_id),
                "warning_quantity": str(data.warning_quantity),
                "critical_quantity": str(data.critical_quantity),
            },
        )
    )
    db.commit()
    db.refresh(threshold)
    return threshold


def list_stock_thresholds(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
) -> list[StockThreshold]:
    return (
        db.query(StockThreshold)
        .join(Ingredient, Ingredient.id == StockThreshold.ingredient_id)
        .filter(
            StockThreshold.restaurant_id == restaurant_id,
            StockThreshold.branch_id == branch_id,
        )
        .order_by(Ingredient.name)
        .all()
    )


def list_low_stock_alerts(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
) -> list[tuple[StockThreshold, Decimal, str, str]]:
    balances_by_ingredient = {
        ingredient.id: quantity
        for ingredient, quantity in list_stock_balances(db, restaurant_id, branch_id)
    }
    alerts: list[tuple[StockThreshold, Decimal, str, str]] = []
    for threshold in list_stock_thresholds(db, restaurant_id, branch_id):
        quantity_on_hand = balances_by_ingredient.get(
            threshold.ingredient_id,
            Decimal("0.000"),
        )
        severity = None
        if quantity_on_hand <= threshold.critical_quantity:
            severity = "CRITICAL"
        elif quantity_on_hand <= threshold.warning_quantity:
            severity = "LOW"
        if severity is None:
            continue
        message = (
            f"{threshold.ingredient.name} is {quantity_on_hand:.3f} {threshold.ingredient.unit}. "
            "Check balances and place a stock order."
        )
        alerts.append((threshold, quantity_on_hand, severity, message))
    return sorted(
        alerts,
        key=lambda row: (
            0 if row[2] == "CRITICAL" else 1,
            row[1],
            row[0].ingredient.name.lower(),
        ),
    )


def create_stock_movement(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    data: StockMovementCreate,
    created_by: User,
) -> StockMovement:
    location = get_stock_location(db, restaurant_id, branch_id, data.stock_location_id)
    if location is None:
        raise ValueError("Stock location not found")
    ingredient = get_ingredient(db, restaurant_id, data.ingredient_id)
    if ingredient is None:
        raise ValueError("Ingredient not found")

    movement = StockMovement(
        restaurant_id=restaurant_id,
        branch_id=branch_id,
        stock_location_id=data.stock_location_id,
        ingredient_id=data.ingredient_id,
        movement_type=data.movement_type.value,
        quantity=data.quantity,
        created_by=created_by.id,
    )
    db.add(movement)
    db.flush()
    db.add(
        AuditLog(
            restaurant_id=restaurant_id,
            user_id=created_by.id,
            action="STOCK_MOVEMENT_CREATED",
            entity_type="stock_movement",
            entity_id=movement.id,
            old_values=None,
            new_values={
                "branch_id": str(branch_id),
                "stock_location_id": str(data.stock_location_id),
                "ingredient_id": str(data.ingredient_id),
                "movement_type": data.movement_type.value,
                "quantity": str(data.quantity),
            },
        )
    )
    db.commit()
    db.refresh(movement)
    return movement


def list_stock_movements(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    *,
    ingredient_id: UUID | None = None,
    stock_location_id: UUID | None = None,
) -> list[StockMovement]:
    query = db.query(StockMovement).filter(
        StockMovement.restaurant_id == restaurant_id,
        StockMovement.branch_id == branch_id,
    )
    if ingredient_id is not None:
        query = query.filter(StockMovement.ingredient_id == ingredient_id)
    if stock_location_id is not None:
        query = query.filter(StockMovement.stock_location_id == stock_location_id)
    return query.order_by(StockMovement.created_at, StockMovement.id).all()


def get_default_consumption_location(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
) -> StockLocation | None:
    locations = list_stock_locations(db, restaurant_id, branch_id)
    for location in locations:
        if location.name.strip().lower() == "kitchen":
            return location
    return locations[0] if locations else None


def consume_order_stock(db: Session, order: Order, changed_by: User) -> list[StockMovement]:
    menu_item_ids = [line.menu_item_id for line in order.items]
    recipe_items = (
        db.query(MenuItemRecipeItem)
        .join(Ingredient, Ingredient.id == MenuItemRecipeItem.ingredient_id)
        .filter(
            MenuItemRecipeItem.menu_item_id.in_(menu_item_ids),
            Ingredient.restaurant_id == order.restaurant_id,
        )
        .all()
    )
    if not recipe_items:
        return []

    ordered_quantities: dict[UUID, int] = defaultdict(int)
    for line in order.items:
        ordered_quantities[line.menu_item_id] += line.quantity
    required_by_ingredient: dict[UUID, Decimal] = defaultdict(lambda: Decimal("0.000"))
    ingredients_by_id: dict[UUID, Ingredient] = {}
    for recipe_item in recipe_items:
        required_by_ingredient[recipe_item.ingredient_id] += (
            Decimal(recipe_item.quantity) * ordered_quantities[recipe_item.menu_item_id]
        )
        ingredients_by_id[recipe_item.ingredient_id] = recipe_item.ingredient

    location = get_default_consumption_location(db, order.restaurant_id, order.branch_id)
    if location is None:
        raise ValueError("Stock location is required before recipe-based consumption")

    for ingredient_id, required_quantity in required_by_ingredient.items():
        available_quantity = get_stock_balance(
            db,
            order.restaurant_id,
            order.branch_id,
            ingredient_id,
            stock_location_id=location.id,
        )
        if available_quantity < required_quantity:
            ingredient = ingredients_by_id[ingredient_id]
            raise ValueError(f"Insufficient stock for ingredient '{ingredient.name}'")

    movements: list[StockMovement] = []
    for ingredient_id, required_quantity in required_by_ingredient.items():
        movement = StockMovement(
            restaurant_id=order.restaurant_id,
            branch_id=order.branch_id,
            stock_location_id=location.id,
            ingredient_id=ingredient_id,
            movement_type=StockMovementType.ORDER_CONSUMPTION.value,
            quantity=-required_quantity,
            reference_type="order",
            reference_id=order.id,
            created_by=changed_by.id,
        )
        db.add(movement)
        movements.append(movement)

    db.flush()
    db.add(
        AuditLog(
            restaurant_id=order.restaurant_id,
            user_id=changed_by.id,
            action="ORDER_STOCK_CONSUMED",
            entity_type="order",
            entity_id=order.id,
            old_values=None,
            new_values={
                "stock_location_id": str(location.id),
                "movements": [
                    {
                        "ingredient_id": str(movement.ingredient_id),
                        "movement_id": str(movement.id),
                        "quantity": str(movement.quantity),
                    }
                    for movement in movements
                ],
            },
        )
    )
    return movements
