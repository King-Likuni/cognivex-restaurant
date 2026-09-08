import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

pytestmark = pytest.mark.integration


def login(client: TestClient, email: str, password: str) -> tuple[dict[str, str], str]:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, token


def create_menu_item(
    client: TestClient,
    restaurant_id: str,
    headers: dict[str, str],
) -> dict[str, str]:
    category_response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/menu/categories",
        headers=headers,
        json={"name": "Realtime Category", "display_order": 1},
    )
    assert category_response.status_code == 201, category_response.text
    category = category_response.json()

    item_response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/menu/items",
        headers=headers,
        json={
            "category_id": category["id"],
            "name": "Realtime Meal",
            "description": None,
            "price": "55.00",
            "image_url": None,
            "is_available": True,
        },
    )
    assert item_response.status_code == 201, item_response.text
    return item_response.json()


def create_cashier_order(
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


def confirm_cash_payment(
    client: TestClient,
    restaurant_id: str,
    headers: dict[str, str],
    order_id: str,
) -> None:
    response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/orders/{order_id}/payments/cash/confirm",
        headers=headers,
        json={"amount_received": "55.00"},
    )
    assert response.status_code == 201, response.text


def test_staff_kitchen_socket_receives_branch_order_events(
    api_client: TestClient,
    seeded_restaurant: dict[str, object],
):
    restaurant_id = str(seeded_restaurant["restaurant"].id)
    branch_id = str(seeded_restaurant["branch"].id)
    headers, token = login(api_client, "owner@example.com", "ownerpassword")
    item = create_menu_item(api_client, restaurant_id, headers)

    with api_client.websocket_connect(
        f"/ws/restaurants/{restaurant_id}/branches/{branch_id}/kitchen?token={token}"
    ) as websocket:
        connected = websocket.receive_json()
        assert connected["type"] == "CONNECTED"

        order = create_cashier_order(api_client, restaurant_id, branch_id, headers, item["id"])
        created_event = websocket.receive_json()
        assert created_event["type"] == "ORDER_CREATED"
        assert created_event["order_id"] == order["id"]
        assert created_event["order_status"] == "PENDING_PAYMENT"

        confirm_cash_payment(api_client, restaurant_id, headers, order["id"])
        payment_event = websocket.receive_json()
        assert payment_event["type"] == "ORDER_PAYMENT_CONFIRMED"
        assert payment_event["order_id"] == order["id"]
        assert payment_event["order_status"] == "QUEUED"
        assert payment_event["payment_status"] == "PAID"


def test_customer_order_status_socket_requires_order_status_token(
    api_client: TestClient,
    seeded_restaurant: dict[str, object],
):
    restaurant_id = str(seeded_restaurant["restaurant"].id)
    branch_id = str(seeded_restaurant["branch"].id)
    headers, _staff_token = login(api_client, "owner@example.com", "ownerpassword")
    item = create_menu_item(api_client, restaurant_id, headers)
    order = create_cashier_order(api_client, restaurant_id, branch_id, headers, item["id"])

    with pytest.raises(WebSocketDisconnect):
        with api_client.websocket_connect(f"/ws/orders/{order['id']}/status"):
            pass

    token_response = api_client.get(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/{order['id']}/status-token",
        headers=headers,
    )
    assert token_response.status_code == 200, token_response.text
    order_status_token = token_response.json()["access_token"]

    with api_client.websocket_connect(
        f"/ws/orders/{order['id']}/status?token={order_status_token}"
    ) as websocket:
        connected = websocket.receive_json()
        assert connected["type"] == "CONNECTED"

        confirm_cash_payment(api_client, restaurant_id, headers, order["id"])
        event = websocket.receive_json()
        assert event["type"] == "ORDER_PAYMENT_CONFIRMED"
        assert event["order_id"] == order["id"]
        assert event["order_status"] == "QUEUED"
