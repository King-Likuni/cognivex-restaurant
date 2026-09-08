"""Kitchen service layer."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.models import User
from app.orders.enums import OrderStatus
from app.orders.models import Order
from app.orders.service import get_order, list_branch_orders, transition_order


def get_kitchen_board(db: Session, restaurant_id: UUID, branch_id: UUID) -> dict[str, list[Order]]:
    return {
        "new": list_branch_orders(
            db,
            restaurant_id,
            branch_id,
            status=OrderStatus.QUEUED.value,
        ),
        "preparing": list_branch_orders(
            db,
            restaurant_id,
            branch_id,
            status=OrderStatus.PREPARING.value,
        ),
        "ready": list_branch_orders(
            db,
            restaurant_id,
            branch_id,
            status=OrderStatus.READY.value,
        ),
    }


def start_preparing(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    order_id: UUID,
    changed_by: User,
) -> Order:
    order = get_order(db, restaurant_id, branch_id, order_id)
    if order is None:
        raise ValueError("Order not found")
    return transition_order(db, order, OrderStatus.PREPARING, changed_by)


def mark_ready(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    order_id: UUID,
    changed_by: User,
) -> Order:
    order = get_order(db, restaurant_id, branch_id, order_id)
    if order is None:
        raise ValueError("Order not found")
    return transition_order(db, order, OrderStatus.READY, changed_by)
