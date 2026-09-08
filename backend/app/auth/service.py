"""Auth service: business logic for user management and authentication."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.models import Role, User
from app.auth.schemas import UserCreate
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

    role_name = user_in.role_name.upper()
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise ValueError(f"Role '{user_in.role_name}' does not exist")

    if role_name == "ADMIN" and user_in.restaurant_id is not None:
        raise ValueError("Platform admins must not be assigned to a restaurant")

    if role_name != "ADMIN" and user_in.restaurant_id is None:
        raise ValueError("Restaurant users must be assigned to a restaurant")

    if user_in.restaurant_id is not None:
        restaurant = (
            db.query(Restaurant)
            .filter(Restaurant.id == user_in.restaurant_id, Restaurant.is_active.is_(True))
            .first()
        )
        if not restaurant:
            raise ValueError("Restaurant does not exist or is inactive")

    branches: list[Branch] = []
    if user_in.branch_ids:
        branches = (
            db.query(Branch)
            .filter(
                Branch.id.in_(user_in.branch_ids),
                Branch.restaurant_id == user_in.restaurant_id,
                Branch.is_active.is_(True),
            )
            .all()
        )
        if len(branches) != len(set(user_in.branch_ids)):
            raise ValueError("One or more branches do not belong to this restaurant")

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


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    """Fetch a user by their UUID."""
    return db.query(User).filter(User.id == user_id).first()


def seed_roles(db: Session) -> None:
    """Ensure the default roles exist in the database."""
    default_roles = ["ADMIN", "OWNER", "MANAGER", "CASHIER", "KITCHEN"]
    for role_name in default_roles:
        exists = db.query(Role).filter(Role.name == role_name).first()
        if not exists:
            db.add(Role(name=role_name))
    db.commit()
