import json
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.webhooks import build_hmac_signature
from app.orders.enums import OrderStatus, PaymentStatus
from app.orders.models import Order, OrderStatusHistory
from app.payments.models import Payment, PaymentEvent

pytestmark = pytest.mark.integration


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_menu_item(
    client: TestClient,
    restaurant_id: str,
    headers: dict[str, str],
) -> dict[str, str]:
    category_response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/menu/categories",
        headers=headers,
        json={"name": "Webhook Payments", "display_order": 1},
    )
    assert category_response.status_code == 201, category_response.text
    category = category_response.json()

    item_response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/menu/items",
        headers=headers,
        json={
            "category_id": category["id"],
            "name": "Webhook Meal",
            "description": None,
            "price": "55.00",
            "image_url": None,
            "is_available": True,
        },
    )
    assert item_response.status_code == 201, item_response.text
    return item_response.json()


def create_order(
    client: TestClient,
    restaurant_id: str,
    branch_id: str,
    headers: dict[str, str],
    item_id: str,
) -> dict[str, str]:
    response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/cashier",
        headers=headers,
        json={
            "customer_id": None,
            "items": [{"menu_item_id": item_id, "quantity": 1}],
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def signed_webhook_headers(payload: dict[str, object]) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return body, {
        "Content-Type": "application/json",
        "X-Cognivex-Signature": build_hmac_signature(body, settings.PAYMENT_WEBHOOK_SECRET),
    }


def test_remote_payment_initiation_and_paid_webhook_are_idempotent(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    restaurant_id = str(seeded_restaurant["restaurant"].id)
    branch_id = str(seeded_restaurant["branch"].id)
    headers = login(api_client, "owner@example.com", "ownerpassword")
    item = create_menu_item(api_client, restaurant_id, headers)
    order = create_order(api_client, restaurant_id, branch_id, headers, item["id"])

    initiate_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/orders/{order['id']}/payments",
        headers=headers,
        json={"provider": "ORANGE_MONEY", "customer_phone_number": "+26770000000"},
    )
    assert initiate_response.status_code == 201, initiate_response.text
    payment = initiate_response.json()
    assert payment["provider"] == "ORANGE_MONEY"
    assert payment["status"] == PaymentStatus.PENDING.value
    assert payment["reference"] == order["payment_reference"]

    callback_payload = {
        "provider_event_id": "om-event-001",
        "reference": payment["reference"],
        "status": PaymentStatus.PAID.value,
        "amount": "55.00",
        "currency": "BWP",
        "provider_transaction_id": "om-txn-001",
    }
    body, signed_headers = signed_webhook_headers(callback_payload)
    webhook_response = api_client.post(
        "/api/v1/webhooks/payments/ORANGE_MONEY",
        content=body,
        headers=signed_headers,
    )
    assert webhook_response.status_code == 200, webhook_response.text
    webhook_result = webhook_response.json()
    assert webhook_result["status"] == PaymentStatus.PAID.value
    assert webhook_result["event_type"] == "ORANGE_MONEY_PAID"
    assert webhook_result["idempotent"] is False

    replay_response = api_client.post(
        "/api/v1/webhooks/payments/ORANGE_MONEY",
        content=body,
        headers=signed_headers,
    )
    assert replay_response.status_code == 200, replay_response.text
    assert replay_response.json()["idempotent"] is True

    payment_record = db_session.query(Payment).filter(Payment.id == UUID(payment["id"])).one()
    assert payment_record.status == PaymentStatus.PAID.value
    assert payment_record.provider_transaction_id == "om-txn-001"

    order_record = db_session.query(Order).filter(Order.id == UUID(order["id"])).one()
    assert order_record.payment_status == PaymentStatus.PAID.value
    assert order_record.order_status == OrderStatus.QUEUED.value

    history = (
        db_session.query(OrderStatusHistory)
        .filter(OrderStatusHistory.order_id == UUID(order["id"]))
        .order_by(OrderStatusHistory.sequence)
        .all()
    )
    assert [row.new_status for row in history] == [
        OrderStatus.PENDING_PAYMENT.value,
        OrderStatus.CONFIRMED.value,
        OrderStatus.QUEUED.value,
    ]

    events = (
        db_session.query(PaymentEvent)
        .filter(PaymentEvent.payment_id == UUID(payment["id"]))
        .order_by(PaymentEvent.created_at)
        .all()
    )
    assert [event.event_type for event in events] == [
        "PAYMENT_INITIATED",
        "ORANGE_MONEY_PAID",
    ]


def test_mobile_transfer_payment_can_be_manually_confirmed(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    restaurant_id = str(seeded_restaurant["restaurant"].id)
    branch_id = str(seeded_restaurant["branch"].id)
    headers = login(api_client, "owner@example.com", "ownerpassword")
    item = create_menu_item(api_client, restaurant_id, headers)
    order = create_order(api_client, restaurant_id, branch_id, headers, item["id"])

    initiate_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/orders/{order['id']}/payments",
        headers=headers,
        json={"provider": "ORANGE_MONEY", "customer_phone_number": "+26770000000"},
    )
    assert initiate_response.status_code == 201, initiate_response.text
    payment = initiate_response.json()
    assert payment["status"] == PaymentStatus.PENDING.value

    confirm_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/orders/{order['id']}/payments/mobile-transfer/confirm",
        headers=headers,
        json={
            "amount_received": "55.00",
            "provider_transaction_id": "manual-om-txn-001",
        },
    )
    assert confirm_response.status_code == 201, confirm_response.text
    confirmed_payment = confirm_response.json()
    assert confirmed_payment["provider"] == "ORANGE_MONEY"
    assert confirmed_payment["status"] == PaymentStatus.PAID.value
    assert confirmed_payment["provider_transaction_id"] == "manual-om-txn-001"

    order_record = db_session.query(Order).filter(Order.id == UUID(order["id"])).one()
    assert order_record.payment_status == PaymentStatus.PAID.value
    assert order_record.order_status == OrderStatus.QUEUED.value

    events = (
        db_session.query(PaymentEvent)
        .filter(PaymentEvent.payment_id == UUID(payment["id"]))
        .order_by(PaymentEvent.created_at)
        .all()
    )
    assert [event.event_type for event in events] == [
        "PAYMENT_INITIATED",
        "ORANGE_MONEY_MANUAL_CONFIRMED",
    ]


def test_payment_webhook_rejects_invalid_signature(
    api_client: TestClient,
    seeded_restaurant: dict[str, object],
):
    payload = {
        "provider_event_id": "om-event-invalid",
        "reference": "CS-MM-260904-999",
        "status": PaymentStatus.PAID.value,
        "amount": "55.00",
        "currency": "BWP",
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    response = api_client.post(
        "/api/v1/webhooks/payments/ORANGE_MONEY",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Cognivex-Signature": "sha256=wrong",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid webhook signature"


def test_payment_webhook_rejects_amount_mismatch(
    api_client: TestClient,
    seeded_restaurant: dict[str, object],
):
    restaurant_id = str(seeded_restaurant["restaurant"].id)
    branch_id = str(seeded_restaurant["branch"].id)
    headers = login(api_client, "owner@example.com", "ownerpassword")
    item = create_menu_item(api_client, restaurant_id, headers)
    order = create_order(api_client, restaurant_id, branch_id, headers, item["id"])
    payment = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/orders/{order['id']}/payments",
        headers=headers,
        json={"provider": "FNB"},
    ).json()

    body, signed_headers = signed_webhook_headers(
        {
            "provider_event_id": "fnb-event-001",
            "reference": payment["reference"],
            "status": PaymentStatus.PAID.value,
            "amount": "54.99",
            "currency": "BWP",
            "provider_transaction_id": "fnb-txn-001",
        }
    )
    response = api_client.post(
        "/api/v1/webhooks/payments/FNB",
        content=body,
        headers=signed_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Webhook amount does not match payment"
