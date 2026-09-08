"""Payment API routes."""

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import ensure_restaurant_access, require_cashier
from app.core.webhooks import verify_hmac_signature
from app.payments import service
from app.payments.schemas import (
    CashPaymentConfirmRequest,
    PaymentInitiateRequest,
    PaymentResponse,
    PaymentWebhookResponse,
)

router = APIRouter(prefix="/restaurants/{restaurant_id}/orders", tags=["Payments"])
webhook_router = APIRouter(prefix="/webhooks/payments", tags=["Payment Webhooks"])


@router.post(
    "/{order_id}/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED
)
def initiate_payment(
    restaurant_id: UUID,
    order_id: UUID,
    data: PaymentInitiateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_cashier),
):
    ensure_restaurant_access(current_user, restaurant_id)
    try:
        return service.initiate_payment(
            db=db,
            restaurant_id=restaurant_id,
            order_id=order_id,
            provider_name=data.provider,
            customer_phone_number=data.customer_phone_number,
            initiated_by=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{order_id}/payments/cash/confirm",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def confirm_cash_payment(
    restaurant_id: UUID,
    order_id: UUID,
    data: CashPaymentConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_cashier),
):
    ensure_restaurant_access(current_user, restaurant_id)
    try:
        return service.confirm_cash_payment(
            db=db,
            restaurant_id=restaurant_id,
            order_id=order_id,
            amount_received=data.amount_received,
            confirmed_by=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@webhook_router.post("/{provider}", response_model=PaymentWebhookResponse)
async def process_payment_webhook(
    provider: str,
    request: Request,
    x_cognivex_signature: Annotated[
        str | None,
        Header(alias="X-Cognivex-Signature"),
    ] = None,
    db: Session = Depends(get_db),
):
    raw_body = await request.body()
    if not verify_hmac_signature(raw_body, x_cognivex_signature, settings.PAYMENT_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    try:
        payment, event, idempotent = service.process_payment_webhook(db, provider, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PaymentWebhookResponse(
        payment_id=payment.id,
        reference=payment.reference,
        provider=payment.provider,
        status=payment.status,
        event_type=event.event_type,
        idempotent=idempotent,
    )
