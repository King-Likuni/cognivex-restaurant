"""Auth service: business logic for user management and authentication."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.models import Role, User
from app.auth.schemas import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password
from app.tenants.models import Branch, Restaurant


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Verify email/password and return the User, or None if invalid."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_user(db: Session, user_in: UserCreate) -> User:
    """Create a new user with a hashed password.

    Raises ValueError if the email is already registered or the role is invalid.
    """
    # Check for duplicate email
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise ValueError(f"Email {user_in.email} is already registered")

    role = validate_role(db, user_in.role_name)
    role_name = role.name

    if role_name == "ADMIN" and user_in.restaurant_id is not None:
        raise ValueError("Platform admins must not be assigned to a restaurant")

    if role_name != "ADMIN" and user_in.restaurant_id is None:
        raise ValueError("Restaurant users must be assigned to a restaurant")

    if user_in.restaurant_id is not None:
        validate_restaurant(db, user_in.restaurant_id)

    branches = validate_branches(db, user_in.restaurant_id, user_in.branch_ids)

    user = User(
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        role_id=role.id,
        restaurant_id=user_in.restaurant_id,
    )
    user.branches = branches
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def validate_role(db: Session, role_name: str) -> Role:
    normalized_role_name = role_name.upper()
    role = db.query(Role).filter(Role.name == normalized_role_name).first()
    if not role:
        raise ValueError(f"Role '{role_name}' does not exist")
    return role


def validate_restaurant(db: Session, restaurant_id: UUID) -> Restaurant:
    restaurant = (
        db.query(Restaurant)
        .filter(Restaurant.id == restaurant_id, Restaurant.is_active.is_(True))
        .first()
    )
    if not restaurant:
        raise ValueError("Restaurant does not exist or is inactive")
    return restaurant


def validate_branches(
    db: Session,
    restaurant_id: UUID | None,
    branch_ids: list[UUID],
) -> list[Branch]:
    if not branch_ids:
        return []
    branches = (
        db.query(Branch)
        .filter(
            Branch.id.in_(branch_ids),
            Branch.restaurant_id == restaurant_id,
            Branch.is_active.is_(True),
        )
        .all()
    )
    if len(branches) != len(set(branch_ids)):
        raise ValueError("One or more branches do not belong to this restaurant")
    return branches


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    """Fetch a user by their UUID."""
    return db.query(User).filter(User.id == user_id).first()


def list_users(db: Session, restaurant_id: UUID | None = None) -> list[User]:
    query = db.query(User).join(Role, User.role_id == Role.id)
    if restaurant_id is not None:
        query = query.filter(User.restaurant_id == restaurant_id)
    return query.order_by(Role.name.asc(), User.email.asc()).all()


def count_active_restaurant_owners(
    db: Session,
    restaurant_id: UUID,
    exclude_user_id: UUID | None = None,
) -> int:
    query = (
        db.query(User)
        .join(Role, User.role_id == Role.id)
        .filter(
            User.restaurant_id == restaurant_id,
            User.is_active.is_(True),
            Role.name == "OWNER",
        )
    )
    if exclude_user_id:
        query = query.filter(User.id != exclude_user_id)
    return query.count()


def update_user(db: Session, user: User, user_in: UserUpdate) -> User:
    changes = user_in.model_dump(exclude_unset=True)

    if "role_name" in changes and user_in.role_name is not None:
        role = validate_role(db, user_in.role_name)
        if role.name == "ADMIN" and user.restaurant_id is not None:
            raise ValueError("Restaurant users cannot be changed into platform admins")
        user.role = role

    if "first_name" in changes and user_in.first_name is not None:
        user.first_name = user_in.first_name

    if "last_name" in changes and user_in.last_name is not None:
        user.last_name = user_in.last_name

    if "is_active" in changes and user_in.is_active is not None:
        user.is_active = user_in.is_active

    if "branch_ids" in changes and user_in.branch_ids is not None:
        user.branches = validate_branches(db, user.restaurant_id, user_in.branch_ids)

    db.commit()
    db.refresh(user)
    return user


def seed_roles(db: Session) -> None:
    """Ensure the default roles exist in the database."""
    default_roles = ["ADMIN", "OWNER", "MANAGER", "CASHIER", "KITCHEN"]
    for role_name in default_roles:
        exists = db.query(Role).filter(Role.name == role_name).first()
        if not exists:
            db.add(Role(name=role_name))
    db.commit()
