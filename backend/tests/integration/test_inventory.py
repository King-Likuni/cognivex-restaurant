from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.inventory.enums import StockMovementType
from app.inventory.models import StockMovement
from app.orders.enums import OrderStatus
from app.orders.models import Order, OrderStatusHistory

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
    name: str = "Inventory Meal",
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


def create_ready_order(
    client: TestClient,
    restaurant_id: str,
    branch_id: str,
    headers: dict[str, str],
    item_id: str,
    *,
    quantity: int = 2,
    total: str = "110.00",
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
    order = order_response.json()

    payment_response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/orders/{order['id']}/payments/cash/confirm",
        headers=headers,
        json={"amount_received": total},
    )
    assert payment_response.status_code == 201, payment_response.text

    start_response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/kitchen/orders/{order['id']}/start",
        headers=headers,
    )
    assert start_response.status_code == 200, start_response.text
    ready_response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/kitchen/orders/{order['id']}/ready",
        headers=headers,
    )
    assert ready_response.status_code == 200, ready_response.text
    return order


def create_ingredient_location_and_stock(
    client: TestClient,
    restaurant_id: str,
    branch_id: str,
    headers: dict[str, str],
    *,
    quantity: str,
) -> tuple[dict[str, str], dict[str, str]]:
    ingredient_response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/inventory/ingredients",
        headers=headers,
        json={"name": "Chicken Portion", "unit": "portion"},
    )
    assert ingredient_response.status_code == 201, ingredient_response.text
    ingredient = ingredient_response.json()

    location_response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/inventory/branches/{branch_id}/locations",
        headers=headers,
        json={"name": "Kitchen"},
    )
    assert location_response.status_code == 201, location_response.text
    location = location_response.json()

    movement_response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/inventory/branches/{branch_id}/movements",
        headers=headers,
        json={
            "stock_location_id": location["id"],
            "ingredient_id": ingredient["id"],
            "movement_type": StockMovementType.RECEIVED.value,
            "quantity": quantity,
        },
    )
    assert movement_response.status_code == 201, movement_response.text
    return ingredient, location


def test_inventory_movements_are_append_only_and_balances_are_summed(
    api_client: TestClient,
    seeded_restaurant: dict[str, object],
):
    restaurant_id = str(seeded_restaurant["restaurant"].id)
    branch_id = str(seeded_restaurant["branch"].id)
    headers = login(api_client, "owner@example.com", "ownerpassword")

    ingredient, location = create_ingredient_location_and_stock(
        api_client,
        restaurant_id,
        branch_id,
        headers,
        quantity="10.000",
    )
    wastage_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/inventory/branches/{branch_id}/movements",
        headers=headers,
        json={
            "stock_location_id": location["id"],
            "ingredient_id": ingredient["id"],
            "movement_type": StockMovementType.WASTAGE.value,
            "quantity": "-1.500",
        },
    )
    assert wastage_response.status_code == 201, wastage_response.text

    balance_response = api_client.get(
        f"/api/v1/restaurants/{restaurant_id}/inventory/branches/{branch_id}/balances",
        headers=headers,
        params={"stock_location_id": location["id"]},
    )
    assert balance_response.status_code == 200, balance_response.text
    balance = balance_response.json()[0]
    assert balance["ingredient_id"] == ingredient["id"]
    assert Decimal(balance["quantity_on_hand"]) == Decimal("8.500")

    movements_response = api_client.get(
        f"/api/v1/restaurants/{restaurant_id}/inventory/branches/{branch_id}/movements",
        headers=headers,
        params={"ingredient_id": ingredient["id"]},
    )
    assert movements_response.status_code == 200, movements_response.text
    assert [row["movement_type"] for row in movements_response.json()] == [
        StockMovementType.RECEIVED.value,
        StockMovementType.WASTAGE.value,
    ]


def test_collecting_order_consumes_recipe_stock_and_writes_audit_log(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    restaurant_id = str(seeded_restaurant["restaurant"].id)
    branch_id = str(seeded_restaurant["branch"].id)
    headers = login(api_client, "owner@example.com", "ownerpassword")
    ingredient, location = create_ingredient_location_and_stock(
        api_client,
        restaurant_id,
        branch_id,
        headers,
        quantity="10.000",
    )
    item = create_menu_item(api_client, restaurant_id, headers)

    recipe_response = api_client.put(
        f"/api/v1/restaurants/{restaurant_id}/inventory/menu-items/{item['id']}/recipe-items",
        headers=headers,
        json={"ingredient_id": ingredient["id"], "quantity": "1.250"},
    )
    assert recipe_response.status_code == 200, recipe_response.text
    assert recipe_response.json()["ingredient_name"] == "Chicken Portion"

    order = create_ready_order(api_client, restaurant_id, branch_id, headers, item["id"])
    collect_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/{order['id']}/collect",
        headers=headers,
    )
    assert collect_response.status_code == 200, collect_response.text

    balance_response = api_client.get(
        f"/api/v1/restaurants/{restaurant_id}/inventory/branches/{branch_id}/balances",
        headers=headers,
        params={"stock_location_id": location["id"]},
    )
    assert balance_response.status_code == 200, balance_response.text
    assert Decimal(balance_response.json()[0]["quantity_on_hand"]) == Decimal("7.500")

    movements = (
        db_session.query(StockMovement)
        .filter(
            StockMovement.reference_type == "order",
            StockMovement.reference_id == UUID(order["id"]),
        )
        .all()
    )
    assert len(movements) == 1
    assert movements[0].movement_type == StockMovementType.ORDER_CONSUMPTION.value
    assert movements[0].quantity == Decimal("-2.500")

    audit_log = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.entity_id == UUID(order["id"]),
            AuditLog.action == "ORDER_STOCK_CONSUMED",
        )
        .one()
    )
    assert audit_log.new_values["stock_location_id"] == location["id"]
    assert audit_log.new_values["movements"][0]["quantity"] == "-2.500"


def test_collecting_recipe_order_rejects_insufficient_stock_without_consumption(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    restaurant_id = str(seeded_restaurant["restaurant"].id)
    branch_id = str(seeded_restaurant["branch"].id)
    headers = login(api_client, "owner@example.com", "ownerpassword")
    ingredient, _location = create_ingredient_location_and_stock(
        api_client,
        restaurant_id,
        branch_id,
        headers,
        quantity="1.000",
    )
    item = create_menu_item(api_client, restaurant_id, headers)

    recipe_response = api_client.put(
        f"/api/v1/restaurants/{restaurant_id}/inventory/menu-items/{item['id']}/recipe-items",
        headers=headers,
        json={"ingredient_id": ingredient["id"], "quantity": "1.250"},
    )
    assert recipe_response.status_code == 200, recipe_response.text

    order = create_ready_order(api_client, restaurant_id, branch_id, headers, item["id"])
    collect_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/{order['id']}/collect",
        headers=headers,
    )
    assert collect_response.status_code == 400
    assert (
        collect_response.json()["detail"] == "Insufficient stock for ingredient 'Chicken Portion'"
    )

    persisted_order = db_session.query(Order).filter(Order.id == UUID(order["id"])).one()
    assert persisted_order.order_status == OrderStatus.READY.value
    assert (
        db_session.query(StockMovement)
        .filter(
            StockMovement.reference_type == "order",
            StockMovement.reference_id == UUID(order["id"]),
        )
        .count()
        == 0
    )
    history = (
        db_session.query(OrderStatusHistory)
        .filter(OrderStatusHistory.order_id == UUID(order["id"]))
        .order_by(OrderStatusHistory.sequence)
        .all()
    )
    assert history[-1].new_status == OrderStatus.READY.value
