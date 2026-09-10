"""Tenant service: business logic for restaurant and branch management."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.auth.models import User
from app.tenants.models import Branch, Restaurant, RestaurantSettings
from app.tenants.schemas import (
    BranchCreate,
    BranchUpdate,
    RestaurantCreate,
    RestaurantSettingsUpdate,
)


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


def create_branch(
    db: Session,
    restaurant_id: UUID,
    data: BranchCreate,
    created_by: User | None = None,
) -> Branch:
    """Create a new branch under the given restaurant."""
    preferred_code = data.code or make_code_from_name(data.name, length=3)
    branch = Branch(
        restaurant_id=restaurant_id,
        code=unique_branch_code(db, restaurant_id, preferred_code),
        name=data.name,
        location=data.location,
    )
    db.add(branch)
    db.flush()
    if created_by is not None:
        db.add(
            AuditLog(
                restaurant_id=restaurant_id,
                user_id=created_by.id,
                action="BRANCH_CREATED",
                entity_type="branch",
                entity_id=branch.id,
                old_values=None,
                new_values={
                    "branch_id": str(branch.id),
                    "code": branch.code,
                    "name": branch.name,
                    "location": branch.location,
                    "is_active": branch.is_active,
                },
            )
        )
    db.commit()
    db.refresh(branch)
    return branch


def get_branch(db: Session, restaurant_id: UUID, branch_id: UUID) -> Branch | None:
    return (
        db.query(Branch)
        .filter(Branch.restaurant_id == restaurant_id, Branch.id == branch_id)
        .first()
    )


def list_branches(db: Session, restaurant_id: UUID, include_inactive: bool = False) -> list[Branch]:
    query = db.query(Branch).filter(Branch.restaurant_id == restaurant_id)
    if not include_inactive:
        query = query.filter(Branch.is_active.is_(True))
    return query.order_by(Branch.name.asc()).all()


def count_active_branches(
    db: Session, restaurant_id: UUID, exclude_branch_id: UUID | None = None
) -> int:
    query = db.query(Branch).filter(
        Branch.restaurant_id == restaurant_id,
        Branch.is_active.is_(True),
    )
    if exclude_branch_id:
        query = query.filter(Branch.id != exclude_branch_id)
    return query.count()


def list_accessible_branches(
    db: Session,
    restaurant_id: UUID,
    user: User,
    *,
    include_inactive: bool = False,
) -> list[Branch]:
    role_name = user.role.name if user.role else None
    if role_name in {"ADMIN", "OWNER", "MANAGER"}:
        return list_branches(db, restaurant_id, include_inactive=include_inactive)

    assigned_branch_ids = [branch.id for branch in user.branches]
    if not assigned_branch_ids:
        return []

    return (
        db.query(Branch)
        .filter(
            Branch.restaurant_id == restaurant_id,
            Branch.id.in_(assigned_branch_ids),
            Branch.is_active.is_(True),
        )
        .order_by(Branch.name.asc())
        .all()
    )


def update_branch(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    data: BranchUpdate,
    changed_by: User | None = None,
) -> Branch | None:
    branch = get_branch(db, restaurant_id, branch_id)
    if not branch:
        return None

    changes = data.model_dump(exclude_unset=True)
    old_values = {
        "branch_id": str(branch.id),
        "code": branch.code,
        "name": branch.name,
        "location": branch.location,
        "is_active": branch.is_active,
    }

    if "code" in changes and data.code is not None:
        candidate_code = normalize_code(data.code)
        existing_branch = (
            db.query(Branch)
            .filter(
                Branch.restaurant_id == restaurant_id,
                Branch.code == candidate_code,
                Branch.id != branch_id,
            )
            .first()
        )
        if existing_branch:
            raise ValueError("Branch code already exists")
        branch.code = candidate_code

    if "name" in changes and data.name is not None:
        branch.name = data.name

    if "location" in changes:
        branch.location = data.location

    if "is_active" in changes and data.is_active is not None:
        if branch.is_active and data.is_active is False:
            remaining_active_branches = count_active_branches(
                db, restaurant_id, exclude_branch_id=branch_id
            )
            if remaining_active_branches == 0:
                raise ValueError("At least one active branch is required")
        branch.is_active = data.is_active

    if changes and changed_by is not None:
        db.add(
            AuditLog(
                restaurant_id=restaurant_id,
                user_id=changed_by.id,
                action="BRANCH_UPDATED",
                entity_type="branch",
                entity_id=branch.id,
                old_values=old_values,
                new_values={
                    "branch_id": str(branch.id),
                    "code": branch.code,
                    "name": branch.name,
                    "location": branch.location,
                    "is_active": branch.is_active,
                },
            )
        )

    db.commit()
    db.refresh(branch)
    return branch


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
