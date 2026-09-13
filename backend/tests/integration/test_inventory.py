from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.auth.schemas import UserCreate
from app.auth.service import create_user
from app.inventory.enums import StockMovementType
from app.inventory.models import StockMovement
from app.orders.models import Order

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


def test_creating_recipe_order_rejects_insufficient_stock_without_consumption(
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

    order_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/cashier",
        headers=headers,
        json={
            "customer_id": None,
            "items": [{"menu_item_id": item["id"], "quantity": 2}],
            "payment_method": "CASH",
        },
    )
    assert order_response.status_code == 400
    assert order_response.json()["detail"] == "Insufficient stock for ingredient 'Chicken Portion'"

    assert db_session.query(Order).count() == 0
    assert (
        db_session.query(StockMovement).filter(StockMovement.reference_type == "order").count() == 0
    )


def test_stock_thresholds_surface_low_and_critical_alerts(
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
        quantity="4.000",
    )

    invalid_threshold_response = api_client.put(
        f"/api/v1/restaurants/{restaurant_id}/inventory/branches/{branch_id}/thresholds/{ingredient['id']}",
        headers=headers,
        json={"warning_quantity": "5.000", "critical_quantity": "6.000"},
    )
    assert invalid_threshold_response.status_code == 422

    threshold_response = api_client.put(
        f"/api/v1/restaurants/{restaurant_id}/inventory/branches/{branch_id}/thresholds/{ingredient['id']}",
        headers=headers,
        json={"warning_quantity": "5.000", "critical_quantity": "2.000"},
    )
    assert threshold_response.status_code == 200, threshold_response.text
    assert threshold_response.json()["ingredient_name"] == "Chicken Portion"

    low_alert_response = api_client.get(
        f"/api/v1/restaurants/{restaurant_id}/inventory/branches/{branch_id}/low-stock-alerts",
        headers=headers,
    )
    assert low_alert_response.status_code == 200, low_alert_response.text
    low_alert = low_alert_response.json()[0]
    assert low_alert["ingredient_id"] == ingredient["id"]
    assert low_alert["severity"] == "LOW"
    assert low_alert["quantity_on_hand"] == "4.000"

    wastage_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/inventory/branches/{branch_id}/movements",
        headers=headers,
        json={
            "stock_location_id": location["id"],
            "ingredient_id": ingredient["id"],
            "movement_type": StockMovementType.WASTAGE.value,
            "quantity": "-3.000",
        },
    )
    assert wastage_response.status_code == 201, wastage_response.text

    critical_alert_response = api_client.get(
        f"/api/v1/restaurants/{restaurant_id}/inventory/branches/{branch_id}/low-stock-alerts",
        headers=headers,
    )
    assert critical_alert_response.status_code == 200, critical_alert_response.text
    critical_alert = critical_alert_response.json()[0]
    assert critical_alert["severity"] == "CRITICAL"
    assert critical_alert["quantity_on_hand"] == "1.000"
    assert critical_alert["message"] == (
        "Chicken Portion is 1.000 portion. Check balances and place a stock order."
    )


def test_kitchen_can_read_low_stock_alerts_but_not_configure_thresholds(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    restaurant = seeded_restaurant["restaurant"]
    branch = seeded_restaurant["branch"]
    restaurant_id = str(restaurant.id)
    branch_id = str(branch.id)
    owner_headers = login(api_client, "owner@example.com", "ownerpassword")
    ingredient, _location = create_ingredient_location_and_stock(
        api_client,
        restaurant_id,
        branch_id,
        owner_headers,
        quantity="1.000",
    )
    threshold_response = api_client.put(
        f"/api/v1/restaurants/{restaurant_id}/inventory/branches/{branch_id}/thresholds/{ingredient['id']}",
        headers=owner_headers,
        json={"warning_quantity": "5.000", "critical_quantity": "2.000"},
    )
    assert threshold_response.status_code == 200, threshold_response.text

    create_user(
        db_session,
        UserCreate(
            email="kitchen@example.com",
            password="kitchenpassword",
            first_name="Kitchen",
            last_name="Staff",
            role_name="KITCHEN",
            restaurant_id=restaurant.id,
            branch_ids=[branch.id],
        ),
    )
    kitchen_headers = login(api_client, "kitchen@example.com", "kitchenpassword")

    alert_response = api_client.get(
        f"/api/v1/restaurants/{restaurant_id}/inventory/branches/{branch_id}/low-stock-alerts",
        headers=kitchen_headers,
    )
    assert alert_response.status_code == 200, alert_response.text
    assert alert_response.json()[0]["severity"] == "CRITICAL"

    forbidden_response = api_client.put(
        f"/api/v1/restaurants/{restaurant_id}/inventory/branches/{branch_id}/thresholds/{ingredient['id']}",
        headers=kitchen_headers,
        json={"warning_quantity": "10.000", "critical_quantity": "3.000"},
    )
    assert forbidden_response.status_code == 403


def test_branch_menu_marks_low_and_critical_stock_items(
    api_client: TestClient,
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
        quantity="4.000",
    )
    item = create_menu_item(api_client, restaurant_id, headers)

    recipe_response = api_client.put(
        f"/api/v1/restaurants/{restaurant_id}/inventory/menu-items/{item['id']}/recipe-items",
        headers=headers,
        json={"ingredient_id": ingredient["id"], "quantity": "1.000"},
    )
    assert recipe_response.status_code == 200, recipe_response.text

    threshold_response = api_client.put(
        f"/api/v1/restaurants/{restaurant_id}/inventory/branches/{branch_id}/thresholds/{ingredient['id']}",
        headers=headers,
        json={"warning_quantity": "5.000", "critical_quantity": "2.000"},
    )
    assert threshold_response.status_code == 200, threshold_response.text

    low_menu_response = api_client.get(
        f"/api/v1/restaurants/{restaurant_id}/menu/branches/{branch_id}/items",
        headers=headers,
    )
    assert low_menu_response.status_code == 200, low_menu_response.text
    low_item = next(row for row in low_menu_response.json() if row["id"] == item["id"])
    assert low_item["is_available_for_sale"] is True
    assert low_item["stock_status"] == "LOW_STOCK"
    assert "can still be sold" in low_item["stock_message"]

    wastage_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/inventory/branches/{branch_id}/movements",
        headers=headers,
        json={
            "stock_location_id": _location["id"],
            "ingredient_id": ingredient["id"],
            "movement_type": StockMovementType.WASTAGE.value,
            "quantity": "-2.500",
        },
    )
    assert wastage_response.status_code == 201, wastage_response.text

    critical_menu_response = api_client.get(
        f"/api/v1/restaurants/{restaurant_id}/menu/branches/{branch_id}/items",
        headers=headers,
    )
    assert critical_menu_response.status_code == 200, critical_menu_response.text
    critical_item = next(row for row in critical_menu_response.json() if row["id"] == item["id"])
    assert critical_item["is_available_for_sale"] is False
    assert critical_item["stock_status"] == "CRITICAL_STOCK"

    cashier_order_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/cashier",
        headers=headers,
        json={
            "customer_id": None,
            "items": [{"menu_item_id": item["id"], "quantity": 1}],
            "payment_method": "CASH",
        },
    )
    assert cashier_order_response.status_code == 400
    assert cashier_order_response.json()["detail"] == (
        "Ingredient 'Chicken Portion' is at critical stock level"
    )

    public_menu_response = api_client.get(
        f"/api/v1/public/restaurants/{restaurant_id}/branches/{branch_id}/menu"
    )
    assert public_menu_response.status_code == 200, public_menu_response.text
    public_item = public_menu_response.json()["categories"][0]["items"][0]
    assert public_item["is_available_for_sale"] is False

    public_order_response = api_client.post(
        f"/api/v1/public/restaurants/{restaurant_id}/branches/{branch_id}/orders",
        json={
            "customer_name": "Stock Customer",
            "customer_phone_number": "+26770001111",
            "channel": "QR",
            "payment_provider": "ORANGE_MONEY",
            "items": [{"menu_item_id": item["id"], "quantity": 1}],
        },
    )
    assert public_order_response.status_code == 400
    assert public_order_response.json()["detail"] == (
        "Ingredient 'Chicken Portion' is at critical stock level"
    )
