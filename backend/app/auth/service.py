"""Auth service: business logic for user management and authentication."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.auth.models import PasswordResetToken, Role, User
from app.auth.schemas import StaffInviteCreate, UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password
from app.tenants.models import Branch, Restaurant

PASSWORD_SETUP_TOKEN_HOURS = 48
TOKEN_PURPOSE_INVITE = "INVITE"
TOKEN_PURPOSE_RESET = "RESET"


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Verify email/password and return the User, or None if invalid."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def hash_setup_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    return datetime.now(UTC)


def as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def user_audit_values(user: User) -> dict:
    return {
        "user_id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role_name": user.role.name if user.role else None,
        "restaurant_id": str(user.restaurant_id) if user.restaurant_id else None,
        "branch_ids": [str(branch.id) for branch in user.branches],
        "is_active": user.is_active,
    }


def create_user(
    db: Session,
    user_in: UserCreate,
    *,
    created_by: UUID | None = None,
    audit_action: str = "STAFF_CREATED",
) -> User:
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
    db.flush()
    if created_by is not None and user.restaurant_id is not None:
        db.add(
            AuditLog(
                restaurant_id=user.restaurant_id,
                user_id=created_by,
                action=audit_action,
                entity_type="user",
                entity_id=user.id,
                old_values=None,
                new_values=user_audit_values(user),
            )
        )
    db.commit()
    db.refresh(user)
    return user


def create_user_invite(
    db: Session,
    user_in: StaffInviteCreate,
    created_by: UUID | None,
) -> tuple[User, PasswordResetToken, str]:
    temporary_password = secrets.token_urlsafe(24)
    user = create_user(
        db,
        UserCreate(
            email=user_in.email,
            password=temporary_password,
            first_name=user_in.first_name,
            last_name=user_in.last_name,
            role_name=user_in.role_name,
            restaurant_id=user_in.restaurant_id,
            branch_ids=user_in.branch_ids,
        ),
        created_by=created_by,
        audit_action="STAFF_INVITED",
    )
    reset_token, raw_token = create_password_setup_token(
        db,
        user,
        created_by=created_by,
        purpose=TOKEN_PURPOSE_INVITE,
    )
    return user, reset_token, raw_token


def create_password_setup_token(
    db: Session,
    user: User,
    *,
    created_by: UUID | None,
    purpose: str = TOKEN_PURPOSE_RESET,
) -> tuple[PasswordResetToken, str]:
    now = utc_now()
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({"used_at": now})

    raw_token = secrets.token_urlsafe(32)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_setup_token(raw_token),
        purpose=purpose,
        expires_at=now + timedelta(hours=PASSWORD_SETUP_TOKEN_HOURS),
        created_by=created_by,
    )
    db.add(reset_token)
    if created_by is not None and user.restaurant_id is not None:
        db.add(
            AuditLog(
                restaurant_id=user.restaurant_id,
                user_id=created_by,
                action="PASSWORD_SETUP_LINK_CREATED",
                entity_type="user",
                entity_id=user.id,
                old_values=None,
                new_values={
                    "user_id": str(user.id),
                    "email": user.email,
                    "purpose": purpose,
                    "expires_at": reset_token.expires_at.isoformat(),
                },
            )
        )
    db.commit()
    db.refresh(reset_token)
    return reset_token, raw_token


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


def update_user(
    db: Session,
    user: User,
    user_in: UserUpdate,
    *,
    changed_by: UUID | None = None,
) -> User:
    changes = user_in.model_dump(exclude_unset=True)
    old_values = user_audit_values(user)

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

    if changes and changed_by is not None and user.restaurant_id is not None:
        db.add(
            AuditLog(
                restaurant_id=user.restaurant_id,
                user_id=changed_by,
                action="STAFF_UPDATED",
                entity_type="user",
                entity_id=user.id,
                old_values=old_values,
                new_values=user_audit_values(user),
            )
        )

    db.commit()
    db.refresh(user)
    return user


def get_valid_password_setup_token(db: Session, raw_token: str) -> PasswordResetToken | None:
    reset_token = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == hash_setup_token(raw_token))
        .first()
    )
    if not reset_token or reset_token.used_at is not None:
        return None
    if as_aware_utc(reset_token.expires_at) <= utc_now():
        return None
    if not reset_token.user or not reset_token.user.is_active:
        return None
    return reset_token


def set_password_with_token(db: Session, raw_token: str, password: str) -> User | None:
    reset_token = get_valid_password_setup_token(db, raw_token)
    if reset_token is None:
        return None
    reset_token.user.password_hash = get_password_hash(password)
    reset_token.used_at = utc_now()
    db.commit()
    db.refresh(reset_token.user)
    return reset_token.user


def seed_roles(db: Session) -> None:
    """Ensure the default roles exist in the database."""
    default_roles = ["ADMIN", "OWNER", "MANAGER", "CASHIER", "KITCHEN"]
    for role_name in default_roles:
        exists = db.query(Role).filter(Role.name == role_name).first()
        if not exists:
            db.add(Role(name=role_name))
    db.commit()
