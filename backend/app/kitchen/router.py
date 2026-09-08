"""Kitchen API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.database import get_db
from app.core.dependencies import ensure_restaurant_access, require_branch_access, require_kitchen
from app.kitchen import service
from app.kitchen.schemas import KitchenBoardResponse
from app.orders.schemas import OrderResponse

router = APIRouter(
    prefix="/restaurants/{restaurant_id}/branches/{branch_id}/kitchen", tags=["Kitchen"]
)


@router.get("/board", response_model=KitchenBoardResponse)
def get_board(
    restaurant_id: UUID,
    branch_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_kitchen),
    branch_user: User = Depends(require_branch_access),
) -> KitchenBoardResponse:
    ensure_restaurant_access(current_user, restaurant_id)
    if branch_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Branch access validation failed")
    return service.get_kitchen_board(db, restaurant_id, branch_id)


@router.post("/orders/{order_id}/start", response_model=OrderResponse)
def start_preparing(
    restaurant_id: UUID,
    branch_id: UUID,
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_kitchen),
    branch_user: User = Depends(require_branch_access),
):
    ensure_restaurant_access(current_user, restaurant_id)
    if branch_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Branch access validation failed")
    try:
        return service.start_preparing(db, restaurant_id, branch_id, order_id, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/orders/{order_id}/ready", response_model=OrderResponse)
def mark_ready(
    restaurant_id: UUID,
    branch_id: UUID,
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_kitchen),
    branch_user: User = Depends(require_branch_access),
):
    ensure_restaurant_access(current_user, restaurant_id)
    if branch_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Branch access validation failed")
    try:
        return service.mark_ready(db, restaurant_id, branch_id, order_id, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
