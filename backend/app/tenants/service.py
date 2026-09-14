"""Tenant service: business logic for restaurant and branch management."""

import secrets
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.auth.models import PasswordResetToken, Role, User
from app.auth.service import (
    PASSWORD_SETUP_TOKEN_HOURS,
    TOKEN_PURPOSE_INVITE,
    create_password_setup_token,
    hash_setup_token,
    user_audit_values,
)
from app.core.security import get_password_hash
from app.inventory import service as inventory_service
from app.orders.enums import OrderStatus, PaymentStatus
from app.orders.models import Order
from app.payments.models import Payment
from app.tenants.models import Branch, Restaurant, RestaurantSettings
from app.tenants.schemas import (
    BranchCreate,
    BranchUpdate,
    PlatformRestaurantSummary,
    RestaurantCreate,
    RestaurantOnboardingCreate,
    RestaurantSettingsUpdate,
    RestaurantSubscriptionUpdate,
)

TENANT_SETUP_PENDING = "SETUP_PENDING"
TENANT_ACTIVE = "ACTIVE"
TENANT_SUSPENDED = "SUSPENDED"
TENANT_LIFECYCLE_STATUSES = {TENANT_SETUP_PENDING, TENANT_ACTIVE, TENANT_SUSPENDED}
SUBSCRIPTION_TRIAL = "TRIAL"
SUBSCRIPTION_ACTIVE = "ACTIVE"
SUBSCRIPTION_OVERDUE = "OVERDUE"
SUBSCRIPTION_CANCELLED = "CANCELLED"
SUBSCRIPTION_STATUSES = {
    SUBSCRIPTION_TRIAL,
    SUBSCRIPTION_ACTIVE,
    SUBSCRIPTION_OVERDUE,
    SUBSCRIPTION_CANCELLED,
}


def money(value: Decimal | int | None) -> Decimal:
    return Decimal(value or 0).quantize(Decimal("0.01"))


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
    restaurant = Restaurant(
        name=data.name,
        code=unique_restaurant_code(db, preferred_code),
        status=TENANT_ACTIVE,
        is_active=True,
    )
    db.add(restaurant)
    db.flush()  # Get the ID before creating settings

    settings = RestaurantSettings(restaurant_id=restaurant.id)
    db.add(settings)
    db.commit()
    db.refresh(restaurant)
    return restaurant


def create_restaurant_onboarding(
    db: Session,
    data: RestaurantOnboardingCreate,
    *,
    created_by: User,
) -> tuple[Restaurant, Branch, User, PasswordResetToken, str]:
    """Create a restaurant, first branch, owner user, and setup token atomically."""
    existing_owner = db.query(User).filter(User.email == data.owner_email).first()
    if existing_owner:
        raise ValueError(f"Email {data.owner_email} is already registered")

    owner_role = db.query(Role).filter(Role.name == "OWNER").first()
    if owner_role is None:
        raise ValueError("OWNER role is not configured")

    try:
        preferred_restaurant_code = data.restaurant_code or make_code_from_name(
            data.restaurant_name,
            length=4,
        )
        restaurant = Restaurant(
            name=data.restaurant_name,
            code=unique_restaurant_code(db, preferred_restaurant_code),
            status=TENANT_SETUP_PENDING,
            subscription_status=SUBSCRIPTION_TRIAL,
            subscription_started_at=datetime.now(UTC),
            is_active=True,
        )
        db.add(restaurant)
        db.flush()

        settings = RestaurantSettings(restaurant_id=restaurant.id)
        db.add(settings)

        preferred_branch_code = data.branch_code or make_code_from_name(data.branch_name, length=3)
        branch = Branch(
            restaurant_id=restaurant.id,
            code=unique_branch_code(db, restaurant.id, preferred_branch_code),
            name=data.branch_name,
            location=data.branch_location,
        )
        db.add(branch)
        db.flush()

        temporary_password = secrets.token_urlsafe(24)
        owner = User(
            email=data.owner_email,
            password_hash=get_password_hash(temporary_password),
            first_name=data.owner_first_name,
            last_name=data.owner_last_name,
            role=owner_role,
            restaurant_id=restaurant.id,
        )
        owner.branches = [branch]
        db.add(owner)
        db.flush()

        raw_token = secrets.token_urlsafe(32)
        reset_token = PasswordResetToken(
            user_id=owner.id,
            token_hash=hash_setup_token(raw_token),
            purpose=TOKEN_PURPOSE_INVITE,
            expires_at=datetime.now(UTC) + timedelta(hours=PASSWORD_SETUP_TOKEN_HOURS),
            created_by=created_by.id,
        )
        db.add(reset_token)

        db.add(
            AuditLog(
                restaurant_id=restaurant.id,
                user_id=created_by.id,
                action="RESTAURANT_ONBOARDED",
                entity_type="restaurant",
                entity_id=restaurant.id,
                old_values=None,
                new_values={
                    "restaurant_id": str(restaurant.id),
                    "code": restaurant.code,
                    "name": restaurant.name,
                    "owner_email": owner.email,
                },
            )
        )
        db.add(
            AuditLog(
                restaurant_id=restaurant.id,
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
        db.add(
            AuditLog(
                restaurant_id=restaurant.id,
                user_id=created_by.id,
                action="OWNER_INVITED",
                entity_type="user",
                entity_id=owner.id,
                old_values=None,
                new_values=user_audit_values(owner),
            )
        )

        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(restaurant)
    db.refresh(branch)
    db.refresh(owner)
    db.refresh(reset_token)
    return restaurant, branch, owner, reset_token, raw_token


def get_restaurant(db: Session, restaurant_id: UUID) -> Restaurant | None:
    return db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()


def list_restaurants(db: Session) -> list[Restaurant]:
    return db.query(Restaurant).order_by(Restaurant.created_at.desc(), Restaurant.name.asc()).all()


def platform_restaurant_summary(db: Session, restaurant: Restaurant) -> PlatformRestaurantSummary:
    today = date.today()
    owner = (
        db.query(User)
        .join(Role)
        .filter(
            User.restaurant_id == restaurant.id,
            Role.name == "OWNER",
            User.is_active.is_(True),
        )
        .order_by(User.created_at.asc())
        .first()
    )
    branch_count = db.query(Branch).filter(Branch.restaurant_id == restaurant.id).count()
    owner_name = None
    if owner is not None:
        owner_name = f"{owner.first_name or ''} {owner.last_name or ''}".strip() or owner.email

    owner_setup_token = None
    if owner is not None:
        owner_setup_token = (
            db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.user_id == owner.id,
                PasswordResetToken.purpose == TOKEN_PURPOSE_INVITE,
                PasswordResetToken.used_at.is_(None),
            )
            .order_by(PasswordResetToken.expires_at.desc())
            .first()
        )

    active_user_count = (
        db.query(User).filter(User.restaurant_id == restaurant.id, User.is_active.is_(True)).count()
    )
    today_orders_query = db.query(Order).filter(
        Order.restaurant_id == restaurant.id,
        Order.business_date == today,
    )
    today_order_count = today_orders_query.count()
    today_revenue = money(
        db.query(func.coalesce(func.sum(Order.total), 0))
        .filter(
            Order.restaurant_id == restaurant.id,
            Order.business_date == today,
            Order.payment_status == PaymentStatus.PAID.value,
            Order.order_status == OrderStatus.COLLECTED.value,
        )
        .scalar()
    )
    pending_payment_count = today_orders_query.filter(
        Order.payment_status == PaymentStatus.PENDING.value,
        Order.order_status.notin_(
            [
                OrderStatus.CANCELLED.value,
                OrderStatus.PAYMENT_EXPIRED.value,
                OrderStatus.COLLECTED.value,
            ]
        ),
    ).count()
    failed_payment_count = (
        db.query(Payment)
        .join(Order, Order.id == Payment.order_id)
        .filter(
            Payment.restaurant_id == restaurant.id,
            Order.business_date == today,
            Payment.status.in_([PaymentStatus.FAILED.value, PaymentStatus.EXPIRED.value]),
        )
        .count()
    )
    last_order_at = (
        db.query(func.max(Order.created_at)).filter(Order.restaurant_id == restaurant.id).scalar()
    )
    low_stock_alert_count = 0
    critical_stock_alert_count = 0
    for branch in list_branches(db, restaurant.id, include_inactive=False):
        for _, _, severity, _ in inventory_service.list_low_stock_alerts(
            db,
            restaurant.id,
            branch.id,
        ):
            if severity == "CRITICAL":
                critical_stock_alert_count += 1
            else:
                low_stock_alert_count += 1

    return PlatformRestaurantSummary(
        id=restaurant.id,
        code=restaurant.code,
        name=restaurant.name,
        status=restaurant.status,
        subscription_status=restaurant.subscription_status,
        subscription_started_at=restaurant.subscription_started_at,
        subscription_renews_at=restaurant.subscription_renews_at,
        suspension_reason=restaurant.suspension_reason,
        is_active=restaurant.is_active,
        branch_count=branch_count,
        active_user_count=active_user_count,
        owner_email=owner.email if owner else None,
        owner_name=owner_name,
        owner_setup_expires_at=owner_setup_token.expires_at if owner_setup_token else None,
        owner_setup_expired=(
            owner_setup_token is not None and owner_setup_token.expires_at <= datetime.now(UTC)
        ),
        today_order_count=today_order_count,
        today_revenue=today_revenue,
        pending_payment_count=pending_payment_count,
        failed_payment_count=failed_payment_count,
        low_stock_alert_count=low_stock_alert_count,
        critical_stock_alert_count=critical_stock_alert_count,
        last_order_at=last_order_at,
        created_at=restaurant.created_at,
    )


def list_platform_restaurants(db: Session) -> list[PlatformRestaurantSummary]:
    restaurants = (
        db.query(Restaurant).order_by(Restaurant.created_at.desc(), Restaurant.name.asc()).all()
    )
    return [platform_restaurant_summary(db, restaurant) for restaurant in restaurants]


def update_restaurant_lifecycle(
    db: Session,
    restaurant_id: UUID,
    status: str,
    *,
    changed_by: User,
    suspension_reason: str | None = None,
) -> Restaurant | None:
    restaurant = get_restaurant(db, restaurant_id)
    if restaurant is None:
        return None

    normalized_status = status.strip().upper()
    if normalized_status not in {TENANT_ACTIVE, TENANT_SUSPENDED}:
        raise ValueError("Restaurant status must be ACTIVE or SUSPENDED")

    previous_values = {
        "status": restaurant.status,
        "is_active": restaurant.is_active,
        "suspension_reason": restaurant.suspension_reason,
    }
    restaurant.status = normalized_status
    restaurant.is_active = normalized_status != TENANT_SUSPENDED
    restaurant.suspension_reason = (
        suspension_reason.strip()
        if normalized_status == TENANT_SUSPENDED and suspension_reason
        else None
    )
    db.add(
        AuditLog(
            restaurant_id=restaurant.id,
            user_id=changed_by.id,
            action="RESTAURANT_LIFECYCLE_UPDATED",
            entity_type="restaurant",
            entity_id=restaurant.id,
            old_values=previous_values,
            new_values={
                "status": restaurant.status,
                "is_active": restaurant.is_active,
                "suspension_reason": restaurant.suspension_reason,
            },
        )
    )
    db.commit()
    db.refresh(restaurant)
    return restaurant


def update_restaurant_subscription(
    db: Session,
    restaurant_id: UUID,
    data: RestaurantSubscriptionUpdate,
    *,
    changed_by: User,
) -> Restaurant | None:
    restaurant = get_restaurant(db, restaurant_id)
    if restaurant is None:
        return None

    normalized_status = data.subscription_status.strip().upper()
    if normalized_status not in SUBSCRIPTION_STATUSES:
        raise ValueError("Subscription status is not valid")

    old_values = {
        "subscription_status": restaurant.subscription_status,
        "subscription_started_at": restaurant.subscription_started_at.isoformat()
        if restaurant.subscription_started_at
        else None,
        "subscription_renews_at": restaurant.subscription_renews_at.isoformat()
        if restaurant.subscription_renews_at
        else None,
    }
    restaurant.subscription_status = normalized_status
    restaurant.subscription_started_at = data.subscription_started_at
    restaurant.subscription_renews_at = data.subscription_renews_at
    db.add(
        AuditLog(
            restaurant_id=restaurant.id,
            user_id=changed_by.id,
            action="RESTAURANT_SUBSCRIPTION_UPDATED",
            entity_type="restaurant",
            entity_id=restaurant.id,
            old_values=old_values,
            new_values={
                "subscription_status": restaurant.subscription_status,
                "subscription_started_at": restaurant.subscription_started_at.isoformat()
                if restaurant.subscription_started_at
                else None,
                "subscription_renews_at": restaurant.subscription_renews_at.isoformat()
                if restaurant.subscription_renews_at
                else None,
            },
        )
    )
    db.commit()
    db.refresh(restaurant)
    return restaurant


def create_owner_setup_link(
    db: Session,
    restaurant_id: UUID,
    *,
    created_by: User,
) -> tuple[PasswordResetToken, str] | None:
    owner = (
        db.query(User)
        .join(Role)
        .filter(
            User.restaurant_id == restaurant_id,
            Role.name == "OWNER",
            User.is_active.is_(True),
        )
        .order_by(User.created_at.asc())
        .first()
    )
    if owner is None:
        return None
    return create_password_setup_token(
        db,
        owner,
        created_by=created_by.id,
        purpose=TOKEN_PURPOSE_INVITE,
    )


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
