from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.auth.schemas import UserCreate
from app.auth.service import create_user
from app.orders.enums import OrderStatus, PaymentStatus
from app.orders.models import OrderStatusHistory
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
    *,
    name: str,
    price: str = "55.00",
) -> dict[str, str]:
    category_response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/menu/categories",
        headers=headers,
        json={"name": f"{name} Category", "display_order": 1},
    )
    assert category_response.status_code == 201, category_response.text
    category = category_response.json()

    item_response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/menu/items",
        headers=headers,
        json={
            "category_id": category["id"],
            "name": name,
            "description": None,
            "price": price,
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
    *,
    quantity: int = 2,
) -> dict[str, str]:
    order_response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/cashier",
        headers=headers,
        json={
            "customer_id": None,
            "items": [{"menu_item_id": item_id, "quantity": quantity}],
            "payment_method": "CASH",
        },
    )
    assert order_response.status_code == 201, order_response.text
    return order_response.json()


def confirm_cash_payment(
    client: TestClient,
    restaurant_id: str,
    headers: dict[str, str],
    order_id: str,
    *,
    amount_received: str = "110.00",
) -> dict[str, str]:
    payment_response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/orders/{order_id}/payments/cash/confirm",
        headers=headers,
        json={"amount_received": amount_received},
    )
    assert payment_response.status_code == 201, payment_response.text
    return payment_response.json()


def move_order_to_ready(
    client: TestClient,
    restaurant_id: str,
    branch_id: str,
    headers: dict[str, str],
    order_id: str,
) -> None:
    start_response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/kitchen/orders/{order_id}/start",
        headers=headers,
    )
    assert start_response.status_code == 200, start_response.text

    ready_response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/kitchen/orders/{order_id}/ready",
        headers=headers,
    )
    assert ready_response.status_code == 200, ready_response.text


def test_paid_collected_order_writes_status_history_payment_event_and_audit_log(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    restaurant = seeded_restaurant["restaurant"]
    branch = seeded_restaurant["branch"]
    owner = seeded_restaurant["owner"]
    restaurant_id = str(restaurant.id)
    branch_id = str(branch.id)
    headers = login(api_client, "owner@example.com", "ownerpassword")

    item = create_menu_item(api_client, restaurant_id, headers, name="Audited Meal")
    order = create_order(api_client, restaurant_id, branch_id, headers, item["id"])
    payment = confirm_cash_payment(api_client, restaurant_id, headers, order["id"])
    move_order_to_ready(api_client, restaurant_id, branch_id, headers, order["id"])

    collect_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/{order['id']}/collect",
        headers=headers,
    )
    assert collect_response.status_code == 200, collect_response.text

    order_id = UUID(order["id"])
    history = (
        db_session.query(OrderStatusHistory)
        .filter(OrderStatusHistory.order_id == order_id)
        .order_by(OrderStatusHistory.sequence)
        .all()
    )
    assert [(row.sequence, row.previous_status, row.new_status) for row in history] == [
        (1, None, OrderStatus.PENDING_PAYMENT.value),
        (2, OrderStatus.PENDING_PAYMENT.value, OrderStatus.CONFIRMED.value),
        (3, OrderStatus.CONFIRMED.value, OrderStatus.QUEUED.value),
        (4, OrderStatus.QUEUED.value, OrderStatus.PREPARING.value),
        (5, OrderStatus.PREPARING.value, OrderStatus.READY.value),
        (6, OrderStatus.READY.value, OrderStatus.COLLECTED.value),
    ]
    assert {row.changed_by for row in history} == {owner.id}

    payment_record = (
        db_session.query(Payment)
        .filter(Payment.id == UUID(payment["id"]), Payment.order_id == order_id)
        .one()
    )
    assert payment_record.status == PaymentStatus.PAID.value
    assert payment_record.reference == order["payment_reference"]

    payment_event = (
        db_session.query(PaymentEvent).filter(PaymentEvent.payment_id == payment_record.id).one()
    )
    assert payment_event.event_type == "CASH_CONFIRMED"
    assert payment_event.payload["amount_received"] == "110.00"
    assert payment_event.payload["order_total"] == "110.00"
    assert payment_event.payload["confirmed_by"] == str(owner.id)

    audit_actions = {
        row.action: row
        for row in db_session.query(AuditLog).filter(AuditLog.entity_id == order_id).all()
    }
    assert set(audit_actions) == {"CASH_PAYMENT_CONFIRMED", "ORDER_COLLECTED"}
    assert (
        audit_actions["CASH_PAYMENT_CONFIRMED"].old_values["payment_status"]
        == PaymentStatus.PENDING.value
    )
    assert (
        audit_actions["CASH_PAYMENT_CONFIRMED"].new_values["payment_status"]
        == PaymentStatus.PAID.value
    )
    assert (
        audit_actions["CASH_PAYMENT_CONFIRMED"].new_values["order_status"]
        == OrderStatus.QUEUED.value
    )
    assert (
        audit_actions["ORDER_COLLECTED"].new_values["order_status"] == OrderStatus.COLLECTED.value
    )

    audit_response = api_client.get(
        f"/api/v1/restaurants/{restaurant_id}/audit-logs/",
        headers=headers,
        params={"entity_type": "order", "branch_id": branch_id},
    )
    assert audit_response.status_code == 200, audit_response.text
    audit_payload = audit_response.json()
    assert {row["action"] for row in audit_payload} >= {
        "CASH_PAYMENT_CONFIRMED",
        "ORDER_COLLECTED",
    }
    assert all(row["user_email"] == "owner@example.com" for row in audit_payload)


def test_uncollected_order_writes_terminal_status_history_and_audit_log(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    restaurant = seeded_restaurant["restaurant"]
    branch = seeded_restaurant["branch"]
    restaurant_id = str(restaurant.id)
    branch_id = str(branch.id)
    headers = login(api_client, "owner@example.com", "ownerpassword")

    item = create_menu_item(
        api_client,
        restaurant_id,
        headers,
        name="Uncollected Audited Meal",
        price="20.00",
    )
    order = create_order(
        api_client,
        restaurant_id,
        branch_id,
        headers,
        item["id"],
        quantity=1,
    )
    confirm_cash_payment(
        api_client,
        restaurant_id,
        headers,
        order["id"],
        amount_received="20.00",
    )
    move_order_to_ready(api_client, restaurant_id, branch_id, headers, order["id"])

    uncollected_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/{order['id']}/uncollected",
        headers=headers,
    )
    assert uncollected_response.status_code == 200, uncollected_response.text

    order_id = UUID(order["id"])
    history = (
        db_session.query(OrderStatusHistory)
        .filter(OrderStatusHistory.order_id == order_id)
        .order_by(OrderStatusHistory.sequence)
        .all()
    )
    assert history[-1].sequence == 6
    assert history[-1].previous_status == OrderStatus.READY.value
    assert history[-1].new_status == OrderStatus.UNCOLLECTED.value

    audit_log = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.entity_id == order_id,
            AuditLog.action == "ORDER_MARKED_UNCOLLECTED",
        )
        .one()
    )
    assert audit_log.old_values["order_status"] == OrderStatus.READY.value
    assert audit_log.new_values["order_status"] == OrderStatus.UNCOLLECTED.value


def test_audit_logs_are_owner_admin_only(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    restaurant = seeded_restaurant["restaurant"]
    branch = seeded_restaurant["branch"]
    create_user(
        db_session,
        UserCreate(
            email="audit-cashier@example.com",
            password="cashierpassword",
            first_name="Audit",
            last_name="Cashier",
            role_name="CASHIER",
            restaurant_id=restaurant.id,
            branch_ids=[branch.id],
        ),
    )
    cashier_headers = login(api_client, "audit-cashier@example.com", "cashierpassword")

    response = api_client.get(
        f"/api/v1/restaurants/{restaurant.id}/audit-logs/",
        headers=cashier_headers,
    )

    assert response.status_code == 403
