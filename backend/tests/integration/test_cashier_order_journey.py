from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_cashier_order_to_collected_daily_sale(
    api_client: TestClient,
    seeded_restaurant: dict[str, object],
):
    restaurant = seeded_restaurant["restaurant"]
    branch = seeded_restaurant["branch"]
    restaurant_id = str(restaurant.id)
    branch_id = str(branch.id)
    owner_headers = login(api_client, "owner@example.com", "ownerpassword")

    category_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/menu/categories",
        headers=owner_headers,
        json={"name": "Chicken", "display_order": 1},
    )
    assert category_response.status_code == 201, category_response.text
    category = category_response.json()

    item_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/menu/items",
        headers=owner_headers,
        json={
            "category_id": category["id"],
            "name": "Chicken and Chips",
            "description": "Quarter chicken with chips",
            "price": "55.00",
            "image_url": None,
            "is_available": True,
        },
    )
    assert item_response.status_code == 201, item_response.text
    item = item_response.json()

    order_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/cashier",
        headers=owner_headers,
        json={
            "customer_id": None,
            "items": [{"menu_item_id": item["id"], "quantity": 2}],
            "payment_method": "CASH",
        },
    )
    assert order_response.status_code == 201, order_response.text
    order = order_response.json()
    assert order["display_number"] == "#001"
    assert order["payment_reference"].startswith("CST-MMT-")
    assert order["total"] == "110.00"
    assert order["order_status"] == "PENDING_PAYMENT"
    assert order["payment_status"] == "PENDING"

    payment_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/orders/{order['id']}/payments/cash/confirm",
        headers=owner_headers,
        json={"amount_received": "110.00"},
    )
    assert payment_response.status_code == 201, payment_response.text
    payment = payment_response.json()
    assert payment["status"] == "PAID"
    assert payment["reference"] == order["payment_reference"]

    board_response = api_client.get(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/kitchen/board",
        headers=owner_headers,
    )
    assert board_response.status_code == 200, board_response.text
    board = board_response.json()
    assert order["id"] in {queued_order["id"] for queued_order in board["new"]}

    start_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/kitchen/orders/{order['id']}/start",
        headers=owner_headers,
    )
    assert start_response.status_code == 200, start_response.text
    assert start_response.json()["order_status"] == "PREPARING"

    ready_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/kitchen/orders/{order['id']}/ready",
        headers=owner_headers,
    )
    assert ready_response.status_code == 200, ready_response.text
    assert ready_response.json()["order_status"] == "READY"

    ready_orders_response = api_client.get(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/",
        headers=owner_headers,
        params={"business_date": date.today().isoformat(), "status": "READY"},
    )
    assert ready_orders_response.status_code == 200, ready_orders_response.text
    assert order["id"] in {ready_order["id"] for ready_order in ready_orders_response.json()}

    token_response = api_client.get(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/{order['id']}/status-token",
        headers=owner_headers,
    )
    assert token_response.status_code == 200, token_response.text
    customer_status_response = api_client.get(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/{order['id']}/customer-status",
        params={"token": token_response.json()["access_token"]},
    )
    assert customer_status_response.status_code == 200, customer_status_response.text
    assert customer_status_response.json()["display_number"] == order["display_number"]
    assert customer_status_response.json()["order_status"] == "READY"

    collect_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/{order['id']}/collect",
        headers=owner_headers,
    )
    assert collect_response.status_code == 200, collect_response.text
    assert collect_response.json()["order_status"] == "COLLECTED"

    report_response = api_client.get(
        f"/api/v1/restaurants/{restaurant_id}/reports/daily-sales",
        headers=owner_headers,
        params={"business_date": date.today().isoformat(), "branch_id": branch_id},
    )
    assert report_response.status_code == 200, report_response.text
    report = report_response.json()
    assert report["orders"] == 1
    assert report["collected_orders"] == 1
    assert report["revenue"] == "110.00"
    assert report["average_order_value"] == "110.00"
    assert report["top_items"] == [
        {
            "menu_item_id": item["id"],
            "name": "Chicken and Chips",
            "quantity": 2,
            "revenue": "110.00",
        }
    ]
    assert report["sales_by_payment"] == [{"provider": "CASH", "payments": 1, "revenue": "110.00"}]


def test_uncollected_order_is_not_counted_as_revenue(
    api_client: TestClient,
    seeded_restaurant: dict[str, object],
):
    restaurant = seeded_restaurant["restaurant"]
    branch = seeded_restaurant["branch"]
    restaurant_id = str(restaurant.id)
    branch_id = str(branch.id)
    owner_headers = login(api_client, "owner@example.com", "ownerpassword")

    category = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/menu/categories",
        headers=owner_headers,
        json={"name": "Sides", "display_order": 2},
    ).json()
    item = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/menu/items",
        headers=owner_headers,
        json={
            "category_id": category["id"],
            "name": "Chips",
            "description": None,
            "price": "20.00",
            "image_url": None,
            "is_available": True,
        },
    ).json()
    order = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/cashier",
        headers=owner_headers,
        json={
            "customer_id": None,
            "items": [{"menu_item_id": item["id"], "quantity": 1}],
            "payment_method": "CASH",
        },
    ).json()
    api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/orders/{order['id']}/payments/cash/confirm",
        headers=owner_headers,
        json={"amount_received": "20.00"},
    )
    api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/kitchen/orders/{order['id']}/start",
        headers=owner_headers,
    )
    api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/kitchen/orders/{order['id']}/ready",
        headers=owner_headers,
    )
    uncollected_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/{order['id']}/uncollected",
        headers=owner_headers,
    )
    assert uncollected_response.status_code == 200, uncollected_response.text

    report_response = api_client.get(
        f"/api/v1/restaurants/{restaurant_id}/reports/daily-sales",
        headers=owner_headers,
        params={"business_date": date.today().isoformat(), "branch_id": branch_id},
    )
    assert report_response.status_code == 200, report_response.text
    report = report_response.json()
    assert report["orders"] == 1
    assert report["uncollected_orders"] == 1
    assert Decimal(report["revenue"]) == Decimal("0.00")
    assert report["top_items"] == []
    assert report["sales_by_payment"] == []
