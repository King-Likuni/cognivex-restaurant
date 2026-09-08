"""WebSocket routes for realtime order updates."""

from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.database import get_db
from app.core.security import decode_access_token
from app.orders.models import Order
from app.realtime.events import branch_channel, event_bus, order_channel
from app.tenants.models import Branch

router = APIRouter(prefix="/ws", tags=["Realtime"])


def role_name(user: User) -> str | None:
    return user.role.name if user.role else None


def get_user_from_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    payload = decode_access_token(token)
    if payload is None or payload.get("purpose", "access") != "access":
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    return db.query(User).filter(User.id == UUID(user_id), User.is_active.is_(True)).first()


def can_access_branch(
    db: Session,
    user: User,
    restaurant_id: UUID,
    branch_id: UUID,
    allowed_roles: set[str],
) -> bool:
    user_role = role_name(user)
    if user_role not in allowed_roles:
        return False
    if user_role == "ADMIN":
        return True
    if user.restaurant_id != restaurant_id:
        return False
    branch = (
        db.query(Branch)
        .filter(
            Branch.id == branch_id,
            Branch.restaurant_id == restaurant_id,
            Branch.is_active.is_(True),
        )
        .first()
    )
    if branch is None:
        return False
    if user_role in {"OWNER", "MANAGER"}:
        return True
    return branch_id in {assigned_branch.id for assigned_branch in user.branches}


async def stream_channel(websocket: WebSocket, channel: str) -> None:
    await websocket.accept()
    subscriber = event_bus.subscribe(channel)
    try:
        await websocket.send_json({"type": "CONNECTED", "channel": channel})
        while True:
            event = await subscriber.queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        event_bus.unsubscribe(subscriber)


@router.websocket("/restaurants/{restaurant_id}/branches/{branch_id}/kitchen")
async def kitchen_updates(
    websocket: WebSocket,
    restaurant_id: UUID,
    branch_id: UUID,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> None:
    user = get_user_from_token(db, token)
    if user is None or not can_access_branch(
        db,
        user,
        restaurant_id,
        branch_id,
        {"ADMIN", "OWNER", "MANAGER", "KITCHEN"},
    ):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await stream_channel(websocket, branch_channel(restaurant_id, branch_id, "kitchen"))


@router.websocket("/restaurants/{restaurant_id}/branches/{branch_id}/cashier")
async def cashier_updates(
    websocket: WebSocket,
    restaurant_id: UUID,
    branch_id: UUID,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> None:
    user = get_user_from_token(db, token)
    if user is None or not can_access_branch(
        db,
        user,
        restaurant_id,
        branch_id,
        {"ADMIN", "OWNER", "MANAGER", "CASHIER"},
    ):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await stream_channel(websocket, branch_channel(restaurant_id, branch_id, "cashier"))


@router.websocket("/orders/{order_id}/status")
async def customer_order_status(
    websocket: WebSocket,
    order_id: UUID,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> None:
    payload = decode_access_token(token) if token else None
    if (
        payload is None
        or payload.get("purpose") != "order_status"
        or payload.get("sub") != str(order_id)
    ):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await stream_channel(websocket, order_channel(order_id))
