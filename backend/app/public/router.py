"""Unauthenticated customer ordering API routes."""

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token
from app.menu import service as menu_service
from app.orders import service as order_service
from app.orders.router import ORDER_STATUS_TOKEN_EXPIRE_SECONDS
from app.orders.schemas import (
    OrderStatusTokenResponse,
    PublicCustomerOrderCreate,
    PublicCustomerOrderResponse,
    PublicMenuCategoryResponse,
    PublicMenuItemResponse,
    PublicMenuResponse,
)
from app.payments import service as payment_service
from app.payments.providers import get_payment_provider
from app.tenants.models import RestaurantSettings

router = APIRouter(
    prefix="/public/restaurants/{restaurant_id}/branches/{branch_id}",
    tags=["Public Ordering"],
)


def create_order_status_token(
    restaurant_id: UUID,
    branch_id: UUID,
    order_id: UUID,
) -> OrderStatusTokenResponse:
    token = create_access_token(
        subject=order_id,
        extra_claims={
            "purpose": "order_status",
            "restaurant_id": str(restaurant_id),
            "branch_id": str(branch_id),
        },
        expires_delta=timedelta(seconds=ORDER_STATUS_TOKEN_EXPIRE_SECONDS),
    )
    return OrderStatusTokenResponse(
        order_id=order_id,
        access_token=token,
        expires_in_seconds=ORDER_STATUS_TOKEN_EXPIRE_SECONDS,
    )


@router.get("/menu", response_model=PublicMenuResponse)
def get_public_menu(
    restaurant_id: UUID,
    branch_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        restaurant, branch = order_service.get_active_restaurant_and_branch(
            db, restaurant_id, branch_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    settings = (
        db.query(RestaurantSettings)
        .filter(RestaurantSettings.restaurant_id == restaurant_id)
        .first()
    )
    currency = settings.currency if settings else "BWP"
    categories = menu_service.list_categories(db, restaurant_id)
    items = menu_service.list_items(db, restaurant_id)
    items_by_category = {
        category.id: [item for item in items if item.category_id == category.id]
        for category in categories
    }

    return PublicMenuResponse(
        restaurant_id=restaurant.id,
        restaurant_name=restaurant.name,
        branch_id=branch.id,
        branch_name=branch.name,
        currency=currency,
        categories=[
            PublicMenuCategoryResponse(
                id=category.id,
                name=category.name,
                display_order=category.display_order,
                items=[
                    PublicMenuItemResponse(
                        id=item.id,
                        category_id=item.category_id,
                        name=item.name,
                        description=item.description,
                        price=item.price,
                        image_url=item.image_url,
                        is_available=item.is_available,
                    )
                    for item in items_by_category[category.id]
                ],
            )
            for category in categories
        ],
    )


@router.post(
    "/orders",
    response_model=PublicCustomerOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_public_customer_order(
    restaurant_id: UUID,
    branch_id: UUID,
    data: PublicCustomerOrderCreate,
    db: Session = Depends(get_db),
):
    provider_name = payment_service.normalize_provider(data.payment_provider)
    if provider_name == "CASH":
        raise HTTPException(
            status_code=400,
            detail="Customer orders require a remote payment provider",
        )
    try:
        get_payment_provider(provider_name)
        order = order_service.create_customer_order(db, restaurant_id, branch_id, data)
        payment = payment_service.initiate_payment(
            db=db,
            restaurant_id=restaurant_id,
            order_id=order.id,
            provider_name=provider_name,
            customer_phone_number=data.customer_phone_number,
            initiated_by=None,
        )
        order = order_service.queue_customer_order_for_preparation(db, order)
        status_token = create_order_status_token(restaurant_id, branch_id, order.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PublicCustomerOrderResponse(
        order=order,
        payment=payment,
        status_token=status_token,
        status_url_path=(
            f"/customer/restaurants/{restaurant_id}/branches/{branch_id}"
            f"/orders/{order.id}/status?token={status_token.access_token}"
        ),
    )
