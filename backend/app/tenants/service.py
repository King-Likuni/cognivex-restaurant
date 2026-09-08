"""Tenant service: business logic for restaurant and branch management."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.tenants.models import Branch, Restaurant, RestaurantSettings
from app.tenants.schemas import BranchCreate, RestaurantCreate, RestaurantSettingsUpdate


def normalize_code(value: str) -> str:
    code = "".join(char for char in value.upper() if char.isalnum())
    if not code:
        raise ValueError("Code must contain at least one letter or number")
    return code[:12]


def make_code_from_name(name: str, length: int = 4) -> str:
    words = [word for word in name.replace("-", " ").split() if word]
    if len(words) > 1:
        candidate = "".join(word[0] for word in words)
    else:
        candidate = name
    return normalize_code(candidate)[:length]


def unique_restaurant_code(db: Session, preferred: str) -> str:
    base = normalize_code(preferred)
    candidate = base
    counter = 1
    while db.query(Restaurant).filter(Restaurant.code == candidate).first():
        counter += 1
        suffix = str(counter)
        candidate = f"{base[: 12 - len(suffix)]}{suffix}"
    return candidate


def unique_branch_code(db: Session, restaurant_id: UUID, preferred: str) -> str:
    base = normalize_code(preferred)
    candidate = base
    counter = 1
    while (
        db.query(Branch)
        .filter(Branch.restaurant_id == restaurant_id, Branch.code == candidate)
        .first()
    ):
        counter += 1
        suffix = str(counter)
        candidate = f"{base[: 12 - len(suffix)]}{suffix}"
    return candidate


def create_restaurant(db: Session, data: RestaurantCreate) -> Restaurant:
    """Create a new restaurant and initialize its default settings."""
    preferred_code = data.code or make_code_from_name(data.name, length=4)
    restaurant = Restaurant(name=data.name, code=unique_restaurant_code(db, preferred_code))
    db.add(restaurant)
    db.flush()  # Get the ID before creating settings

    settings = RestaurantSettings(restaurant_id=restaurant.id)
    db.add(settings)
    db.commit()
    db.refresh(restaurant)
    return restaurant


def get_restaurant(db: Session, restaurant_id: UUID) -> Restaurant | None:
    return db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()


def list_restaurants(db: Session) -> list[Restaurant]:
    return db.query(Restaurant).filter(Restaurant.is_active.is_(True)).all()


def create_branch(db: Session, restaurant_id: UUID, data: BranchCreate) -> Branch:
    """Create a new branch under the given restaurant."""
    preferred_code = data.code or make_code_from_name(data.name, length=3)
    branch = Branch(
        restaurant_id=restaurant_id,
        code=unique_branch_code(db, restaurant_id, preferred_code),
        name=data.name,
        location=data.location,
    )
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return branch


def list_branches(db: Session, restaurant_id: UUID) -> list[Branch]:
    return (
        db.query(Branch)
        .filter(Branch.restaurant_id == restaurant_id, Branch.is_active.is_(True))
        .all()
    )


def get_restaurant_settings(db: Session, restaurant_id: UUID) -> RestaurantSettings | None:
    return (
        db.query(RestaurantSettings)
        .filter(RestaurantSettings.restaurant_id == restaurant_id)
        .first()
    )


def update_restaurant_settings(
    db: Session, restaurant_id: UUID, data: RestaurantSettingsUpdate
) -> RestaurantSettings:
    settings = get_restaurant_settings(db, restaurant_id)
    if not settings:
        settings = RestaurantSettings(restaurant_id=restaurant_id)
        db.add(settings)

    settings.currency = data.currency
    settings.max_unpaid_amount = data.max_unpaid_amount
    settings.max_uncollected_orders = data.max_uncollected_orders
    settings.remote_cash_enabled = data.remote_cash_enabled
    db.commit()
    db.refresh(settings)
    return settings
