"""Menu service layer."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.menu.models import MenuCategory, MenuItem
from app.menu.schemas import (
    MenuCategoryCreate,
    MenuCategoryUpdate,
    MenuItemAvailabilityUpdate,
    MenuItemCreate,
    MenuItemUpdate,
)


def create_category(db: Session, restaurant_id: UUID, data: MenuCategoryCreate) -> MenuCategory:
    category = MenuCategory(
        restaurant_id=restaurant_id,
        name=data.name,
        display_order=data.display_order,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def list_categories(
    db: Session, restaurant_id: UUID, include_inactive: bool = False
) -> list[MenuCategory]:
    query = db.query(MenuCategory).filter(MenuCategory.restaurant_id == restaurant_id)
    if not include_inactive:
        query = query.filter(MenuCategory.is_active.is_(True))
    return query.order_by(MenuCategory.display_order, MenuCategory.name).all()


def get_category(db: Session, restaurant_id: UUID, category_id: UUID) -> MenuCategory | None:
    return (
        db.query(MenuCategory)
        .filter(MenuCategory.restaurant_id == restaurant_id, MenuCategory.id == category_id)
        .first()
    )


def update_category(
    db: Session,
    restaurant_id: UUID,
    category_id: UUID,
    data: MenuCategoryUpdate,
) -> MenuCategory | None:
    category = get_category(db, restaurant_id, category_id)
    if category is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return category


def create_item(db: Session, restaurant_id: UUID, data: MenuItemCreate) -> MenuItem:
    category = get_category(db, restaurant_id, data.category_id)
    if category is None or not category.is_active:
        raise ValueError("Category does not exist or is inactive")
    item = MenuItem(
        category_id=data.category_id,
        restaurant_id=restaurant_id,
        name=data.name,
        description=data.description,
        price=data.price,
        image_url=data.image_url,
        is_available=data.is_available,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_items(
    db: Session,
    restaurant_id: UUID,
    include_unavailable: bool = False,
) -> list[MenuItem]:
    query = db.query(MenuItem).filter(MenuItem.restaurant_id == restaurant_id)
    if not include_unavailable:
        query = query.filter(MenuItem.is_available.is_(True))
    return query.order_by(MenuItem.name).all()


def get_item(db: Session, restaurant_id: UUID, item_id: UUID) -> MenuItem | None:
    return (
        db.query(MenuItem)
        .filter(MenuItem.restaurant_id == restaurant_id, MenuItem.id == item_id)
        .first()
    )


def update_item(
    db: Session,
    restaurant_id: UUID,
    item_id: UUID,
    data: MenuItemUpdate,
) -> MenuItem | None:
    item = get_item(db, restaurant_id, item_id)
    if item is None:
        return None
    updates = data.model_dump(exclude_unset=True)
    category_id = updates.get("category_id")
    if category_id is not None:
        category = get_category(db, restaurant_id, category_id)
        if category is None or not category.is_active:
            raise ValueError("Category does not exist or is inactive")
    for field, value in updates.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def update_item_availability(
    db: Session,
    restaurant_id: UUID,
    item_id: UUID,
    data: MenuItemAvailabilityUpdate,
) -> MenuItem | None:
    item = get_item(db, restaurant_id, item_id)
    if item is None:
        return None
    item.is_available = data.is_available
    db.commit()
    db.refresh(item)
    return item
