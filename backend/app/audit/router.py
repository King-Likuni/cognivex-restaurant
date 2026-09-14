"""Audit API router."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.audit import service
from app.audit.schemas import AuditLogResponse
from app.auth.models import User
from app.core.database import get_db
from app.core.dependencies import RoleChecker, ensure_restaurant_access, require_admin

router = APIRouter(prefix="/restaurants/{restaurant_id}/audit-logs", tags=["Audit"])
platform_router = APIRouter(prefix="/platform/audit-logs", tags=["Platform Audit"])
require_audit_reader = RoleChecker(["ADMIN", "OWNER"])


def ensure_audit_access(current_user: User, restaurant_id: UUID) -> None:
    role_name = current_user.role.name if current_user.role else None
    if role_name == "ADMIN":
        return
    if role_name == "OWNER":
        ensure_restaurant_access(current_user, restaurant_id)
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only restaurant owners or platform admins can view audit logs",
    )


def serialize_audit_row(row: tuple) -> AuditLogResponse:
    audit_log, user = row
    user_name = None
    if user is not None:
        user_name = (
            " ".join(part for part in [user.first_name, user.last_name] if part) or user.email
        )
    return AuditLogResponse(
        id=audit_log.id,
        restaurant_id=audit_log.restaurant_id,
        user_id=audit_log.user_id,
        user_email=user.email if user else None,
        user_name=user_name,
        action=audit_log.action,
        entity_type=audit_log.entity_type,
        entity_id=audit_log.entity_id,
        old_values=audit_log.old_values,
        new_values=audit_log.new_values,
        created_at=audit_log.created_at,
    )


@router.get("/", response_model=list[AuditLogResponse])
def list_audit_logs(
    restaurant_id: UUID,
    action: str | None = None,
    entity_type: str | None = None,
    user_id: UUID | None = None,
    branch_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_audit_reader),
):
    """List read-only audit history for a restaurant."""
    ensure_audit_access(current_user, restaurant_id)
    rows = service.list_audit_logs(
        db,
        restaurant_id,
        action=action,
        entity_type=entity_type,
        user_id=user_id,
        branch_id=branch_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return [serialize_audit_row(row) for row in rows]


@platform_router.get("/", response_model=list[AuditLogResponse])
def list_platform_audit_logs(
    action: str | None = None,
    entity_type: str | None = None,
    user_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List platform-wide audit history. Platform admins only."""
    rows = service.list_platform_audit_logs(
        db,
        action=action,
        entity_type=entity_type,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return [serialize_audit_row(row) for row in rows]
