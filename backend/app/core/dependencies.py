"""Reusable FastAPI dependencies for authentication and authorisation."""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.database import get_db
from app.core.security import decode_access_token
from app.tenants.models import Branch

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# --------------------------------------------------------------------------- #
# Current-user dependency
# --------------------------------------------------------------------------- #
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate the current user from the JWT bearer token.

    Raises 401 if the token is invalid, expired, or the user doesn't exist.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == UUID(user_id)).first()
    if user is None or not user.is_active:
        raise credentials_exception

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the current user is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


# --------------------------------------------------------------------------- #
# Role-based access control
# --------------------------------------------------------------------------- #
class RoleChecker:
    """Dependency that checks whether the current user has one of the allowed roles.

    Usage in a route::

        @router.get("/admin", dependencies=[Depends(RoleChecker(["OWNER", "MANAGER"]))])
        def admin_endpoint(): ...
    """

    def __init__(self, allowed_roles: list[str]) -> None:
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role is None or current_user.role.name not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user


# Convenience instances
shared_order_roles = ["OWNER", "MANAGER", "CASHIER", "KITCHEN"]
require_owner = RoleChecker(["OWNER"])
require_manager = RoleChecker(["OWNER", "MANAGER"])
require_cashier = RoleChecker(shared_order_roles)
require_kitchen = RoleChecker(shared_order_roles)
require_inventory = RoleChecker(["OWNER", "MANAGER", "INVENTORY"])
require_admin = RoleChecker(["ADMIN"])


def _role_name(user: User) -> str | None:
    return user.role.name if user.role else None


def ensure_restaurant_access(user: User, restaurant_id: UUID) -> None:
    """Raise 403 when a user attempts to cross tenant boundaries."""
    if _role_name(user) == "ADMIN":
        return
    if user.restaurant_id != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this restaurant",
        )


def require_restaurant_access(
    restaurant_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> User:
    ensure_restaurant_access(current_user, restaurant_id)
    return current_user


def require_restaurant_owner(
    restaurant_id: UUID,
    current_user: User = Depends(require_owner),
) -> User:
    ensure_restaurant_access(current_user, restaurant_id)
    return current_user


def require_branch_access(
    branch_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> User:
    """Ensure non-admin users are assigned to the requested branch."""
    if _role_name(current_user) == "ADMIN":
        return current_user
    branch = db.query(Branch).filter(Branch.id == branch_id, Branch.is_active.is_(True)).first()
    if branch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    ensure_restaurant_access(current_user, branch.restaurant_id)
    if _role_name(current_user) in {"OWNER", "MANAGER"}:
        return current_user
    branch_ids = {branch.id for branch in current_user.branches}
    if branch_id not in branch_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this branch",
        )
    return current_user
