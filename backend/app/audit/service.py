"""Audit history query helpers."""

from datetime import UTC, date, datetime, time
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.auth.models import User
from app.orders.models import Order


def start_of_day(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UTC)


def end_of_day(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=UTC)


def list_audit_logs(
    db: Session,
    restaurant_id: UUID,
    *,
    action: str | None = None,
    entity_type: str | None = None,
    user_id: UUID | None = None,
    branch_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
) -> list[tuple[AuditLog, User | None]]:
    query = (
        db.query(AuditLog, User)
        .outerjoin(User, AuditLog.user_id == User.id)
        .filter(AuditLog.restaurant_id == restaurant_id)
    )

    if action:
        query = query.filter(AuditLog.action == action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if date_from:
        query = query.filter(AuditLog.created_at >= start_of_day(date_from))
    if date_to:
        query = query.filter(AuditLog.created_at <= end_of_day(date_to))
    if branch_id:
        query = query.outerjoin(
            Order,
            and_(AuditLog.entity_type == "order", AuditLog.entity_id == Order.id),
        ).filter(
            or_(
                Order.branch_id == branch_id,
                AuditLog.old_values["branch_id"].astext == str(branch_id),
                AuditLog.new_values["branch_id"].astext == str(branch_id),
            )
        )

    return query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit).all()
