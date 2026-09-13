from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.orders import service as order_service
from app.orders.schemas import CashierOrderCreate, OrderLineCreate
from app.tenants.schemas import BranchCreate
from app.tenants.service import create_branch

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
    name: str = "Edge Case Meal",
    price: str = "55.00",
    is_available: bool = True,
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
            "is_available": is_available,
        },
    )
    assert item_response.status_code == 201, item_response.text
    return item_response.json()


def create_cashier_order(
    client: TestClient,
    restaurant_id: str,
    branch_id: str,
    headers: dict[str, str],
    menu_item_id: str,
    *,
    quantity: int = 1,
    payment_method: str = "CASH",
) -> dict[str, str]:
    order_response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/cashier",
        headers=headers,
        json={
            "customer_id": None,
            "items": [{"menu_item_id": menu_item_id, "quantity": quantity}],
            "payment_method": payment_method,
        },
    )
    assert order_response.status_code == 201, order_response.text
    return order_response.json()


def test_cash_payment_rejects_wrong_amount_and_duplicate_confirmation(
    api_client: TestClient,
    seeded_restaurant: dict[str, object],
):
    restaurant_id = str(seeded_restaurant["restaurant"].id)
    branch_id = str(seeded_restaurant["branch"].id)
    owner_headers = login(api_client, "owner@example.com", "ownerpassword")
    item = create_menu_item(api_client, restaurant_id, owner_headers, price="55.00")
    order = create_cashier_order(
        api_client,
        restaurant_id,
        branch_id,
        owner_headers,
        item["id"],
        quantity=2,
    )

    wrong_amount_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/orders/{order['id']}/payments/cash/confirm",
        headers=owner_headers,
        json={"amount_received": "109.99"},
    )
    assert wrong_amount_response.status_code == 400
    assert wrong_amount_response.json()["detail"] == "Amount received is less than order total"

    paid_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/orders/{order['id']}/payments/cash/confirm",
        headers=owner_headers,
        json={"amount_received": "110.00"},
    )
    assert paid_response.status_code == 201, paid_response.text

    duplicate_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/orders/{order['id']}/payments/cash/confirm",
        headers=owner_headers,
        json={"amount_received": "110.00"},
    )
    assert duplicate_response.status_code == 400
    assert duplicate_response.json()["detail"] == "Order is already paid"


def test_kitchen_cannot_start_unpaid_order(
    api_client: TestClient,
    seeded_restaurant: dict[str, object],
):
    restaurant_id = str(seeded_restaurant["restaurant"].id)
    branch_id = str(seeded_restaurant["branch"].id)
    owner_headers = login(api_client, "owner@example.com", "ownerpassword")
    item = create_menu_item(api_client, restaurant_id, owner_headers)
    order = create_cashier_order(api_client, restaurant_id, branch_id, owner_headers, item["id"])

    start_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/kitchen/orders/{order['id']}/start",
        headers=owner_headers,
    )
    assert start_response.status_code == 400
    assert (
        start_response.json()["detail"]
        == "Cannot transition order from PENDING_PAYMENT to PREPARING"
    )


def test_cashier_order_cannot_be_collected_before_verified_payment(
    api_client: TestClient,
    seeded_restaurant: dict[str, object],
):
    restaurant_id = str(seeded_restaurant["restaurant"].id)
    branch_id = str(seeded_restaurant["branch"].id)
    owner_headers = login(api_client, "owner@example.com", "ownerpassword")
    item = create_menu_item(api_client, restaurant_id, owner_headers)
    order = create_cashier_order(api_client, restaurant_id, branch_id, owner_headers, item["id"])

    collect_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/{order['id']}/collect",
        headers=owner_headers,
    )

    assert collect_response.status_code == 400
    assert collect_response.json()["detail"] == "Only paid orders can be collected"


def test_cashier_transfer_order_requires_matching_reference_before_collection(
    api_client: TestClient,
    seeded_restaurant: dict[str, object],
):
    restaurant_id = str(seeded_restaurant["restaurant"].id)
    branch_id = str(seeded_restaurant["branch"].id)
    owner_headers = login(api_client, "owner@example.com", "ownerpassword")
    item = create_menu_item(api_client, restaurant_id, owner_headers, name="Transfer Meal")
    order = create_cashier_order(
        api_client,
        restaurant_id,
        branch_id,
        owner_headers,
        item["id"],
        payment_method="PAY2CELL",
    )
    assert order["order_status"] == "QUEUED"
    assert order["payment_status"] == "PENDING"
    assert order["payment_provider"] == "PAY2CELL"

    start_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/kitchen/orders/{order['id']}/start",
        headers=owner_headers,
    )
    assert start_response.status_code == 200, start_response.text
    ready_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/kitchen/orders/{order['id']}/ready",
        headers=owner_headers,
    )
    assert ready_response.status_code == 200, ready_response.text

    early_collect_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/{order['id']}/collect",
        headers=owner_headers,
    )
    assert early_collect_response.status_code == 400
    assert early_collect_response.json()["detail"] == "Only paid orders can be collected"

    wrong_reference_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/orders/{order['id']}/payments/mobile-transfer/confirm",
        headers=owner_headers,
        json={"amount_received": "55.00", "payment_reference_used": "WRONG-REFERENCE"},
    )
    assert wrong_reference_response.status_code == 400
    assert (
        wrong_reference_response.json()["detail"] == "Payment reference does not match this order"
    )

    payment_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/orders/{order['id']}/payments/mobile-transfer/confirm",
        headers=owner_headers,
        json={
            "amount_received": "55.00",
            "payment_reference_used": order["payment_reference"],
        },
    )
    assert payment_response.status_code == 201, payment_response.text

    collect_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/{order['id']}/collect",
        headers=owner_headers,
    )
    assert collect_response.status_code == 200, collect_response.text
    assert collect_response.json()["order_status"] == "COLLECTED"


def test_sold_out_item_cannot_be_ordered(
    api_client: TestClient,
    seeded_restaurant: dict[str, object],
):
    restaurant_id = str(seeded_restaurant["restaurant"].id)
    branch_id = str(seeded_restaurant["branch"].id)
    owner_headers = login(api_client, "owner@example.com", "ownerpassword")
    item = create_menu_item(
        api_client,
        restaurant_id,
        owner_headers,
        name="Sold Out Meal",
        is_available=False,
    )

    order_response = api_client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/cashier",
        headers=owner_headers,
        json={
            "customer_id": None,
            "items": [{"menu_item_id": item["id"], "quantity": 1}],
            "payment_method": "CASH",
        },
    )
    assert order_response.status_code == 400
    assert order_response.json()["detail"] == "Menu item 'Sold Out Meal' is sold out"


def test_daily_numbering_increments_per_branch_and_resets_by_business_date(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    seeded_restaurant: dict[str, object],
):
    restaurant = seeded_restaurant["restaurant"]
    first_branch = seeded_restaurant["branch"]
    owner = seeded_restaurant["owner"]
    second_branch = create_branch(
        db_session,
        restaurant.id,
        BranchCreate(name="Airport Test", code="APT", location="Gaborone"),
    )

    owner_headers = {"unused": "direct service test"}
    del owner_headers

    from app.menu.schemas import MenuCategoryCreate, MenuItemCreate
    from app.menu.service import create_category, create_item

    category = create_category(
        db_session,
        restaurant.id,
        MenuCategoryCreate(name="Numbering", display_order=1),
    )
    item = create_item(
        db_session,
        restaurant.id,
        MenuItemCreate(
            category_id=category.id,
            name="Numbering Meal",
            description=None,
            price="10.00",
            image_url=None,
            is_available=True,
        ),
    )
    payload = CashierOrderCreate(
        customer_id=None,
        items=[OrderLineCreate(menu_item_id=item.id, quantity=1)],
        payment_method="CASH",
    )

    monkeypatch.setattr(order_service, "get_business_date", lambda: date(2026, 9, 4))
    first_order = order_service.create_cashier_order(
        db_session,
        restaurant.id,
        first_branch.id,
        payload,
        owner,
    )
    second_order = order_service.create_cashier_order(
        db_session,
        restaurant.id,
        first_branch.id,
        payload,
        owner,
    )
    other_branch_order = order_service.create_cashier_order(
        db_session,
        restaurant.id,
        second_branch.id,
        payload,
        owner,
    )

    monkeypatch.setattr(order_service, "get_business_date", lambda: date(2026, 9, 5))
    next_day_order = order_service.create_cashier_order(
        db_session,
        restaurant.id,
        first_branch.id,
        payload,
        owner,
    )

    assert first_order.display_number == "#001"
    assert second_order.display_number == "#002"
    assert other_branch_order.display_number == "#001"
    assert next_day_order.display_number == "#001"
    assert first_order.payment_reference.endswith("260904-001")
    assert next_day_order.payment_reference.endswith("260905-001")
