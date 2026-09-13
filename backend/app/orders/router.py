"""Order workflow API routes."""

from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.database import get_db
from app.core.dependencies import ensure_restaurant_access, require_branch_access, require_cashier
from app.core.security import create_access_token, decode_access_token
from app.orders import service
from app.orders.customer_status import (
    get_collection_instruction,
    get_customer_stage_label,
    get_customer_status_message,
    get_customer_status_updated_at,
    payment_proof_required,
)
from app.orders.enums import OrderStatus
from app.orders.schemas import (
    CashierOrderCreate,
    CustomerOrderStatusResponse,
    OrderResponse,
    OrderStatusTokenResponse,
)

router = APIRouter(
    prefix="/restaurants/{restaurant_id}/branches/{branch_id}/orders", tags=["Orders"]
)

ORDER_STATUS_TOKEN_EXPIRE_SECONDS = 60 * 60 * 4


@router.post("/cashier", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_cashier_order(
    restaurant_id: UUID,
    branch_id: UUID,
    data: CashierOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_cashier),
    branch_user: User = Depends(require_branch_access),
):
    ensure_restaurant_access(current_user, restaurant_id)
    if branch_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Branch access validation failed")
    try:
        return service.create_cashier_order(db, restaurant_id, branch_id, data, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/", response_model=list[OrderResponse])
def list_orders(
    restaurant_id: UUID,
    branch_id: UUID,
    business_date: date | None = None,
    status: OrderStatus | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_cashier),
    branch_user: User = Depends(require_branch_access),
):
    ensure_restaurant_access(current_user, restaurant_id)
    if branch_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Branch access validation failed")
    return service.list_branch_orders(
        db,
        restaurant_id,
        branch_id,
        business_date=business_date or service.get_business_date(),
        status=status.value if status is not None else None,
    )


@router.get("/{order_id}/status-token", response_model=OrderStatusTokenResponse)
def create_order_status_token(
    restaurant_id: UUID,
    branch_id: UUID,
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_cashier),
    branch_user: User = Depends(require_branch_access),
):
    ensure_restaurant_access(current_user, restaurant_id)
    if branch_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Branch access validation failed")
    order = service.get_order(db, restaurant_id, branch_id, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    token = create_access_token(
        subject=order.id,
        extra_claims={
            "purpose": "order_status",
            "restaurant_id": str(restaurant_id),
            "branch_id": str(branch_id),
        },
        expires_delta=timedelta(seconds=ORDER_STATUS_TOKEN_EXPIRE_SECONDS),
    )
    return OrderStatusTokenResponse(
        order_id=order.id,
        access_token=token,
        expires_in_seconds=ORDER_STATUS_TOKEN_EXPIRE_SECONDS,
    )


@router.get("/{order_id}/customer-status", response_model=CustomerOrderStatusResponse)
def get_customer_order_status(
    restaurant_id: UUID,
    branch_id: UUID,
    order_id: UUID,
    token: str,
    db: Session = Depends(get_db),
):
    payload = decode_access_token(token)
    if (
        payload is None
        or payload.get("purpose") != "order_status"
        or payload.get("sub") != str(order_id)
    ):
        raise HTTPException(status_code=401, detail="Invalid order status token")
    order = service.get_order(db, restaurant_id, branch_id, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return CustomerOrderStatusResponse(
        order_id=order.id,
        display_number=order.display_number,
        payment_reference=order.payment_reference,
        payment_provider=order.payment_provider,
        payment_status=order.payment_status,
        order_status=order.order_status,
        stage_label=get_customer_stage_label(order),
        message=get_customer_status_message(order),
        collection_instruction=get_collection_instruction(order),
        payment_reference_required=payment_proof_required(order),
        updated_at=get_customer_status_updated_at(order),
    )


@router.post("/{order_id}/collect", response_model=OrderResponse)
def collect_order(
    restaurant_id: UUID,
    branch_id: UUID,
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_cashier),
    branch_user: User = Depends(require_branch_access),
):
    ensure_restaurant_access(current_user, restaurant_id)
    if branch_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Branch access validation failed")
    try:
        return service.collect_order(db, restaurant_id, branch_id, order_id, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{order_id}/uncollected", response_model=OrderResponse)
def mark_uncollected(
    restaurant_id: UUID,
    branch_id: UUID,
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_cashier),
    branch_user: User = Depends(require_branch_access),
):
    ensure_restaurant_access(current_user, restaurant_id)
    if branch_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Branch access validation failed")
    try:
        return service.mark_uncollected(db, restaurant_id, branch_id, order_id, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    restaurant_id: UUID,
    branch_id: UUID,
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_cashier),
    branch_user: User = Depends(require_branch_access),
):
    ensure_restaurant_access(current_user, restaurant_id)
    if branch_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Branch access validation failed")
    try:
        return service.cancel_order(db, restaurant_id, branch_id, order_id, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
