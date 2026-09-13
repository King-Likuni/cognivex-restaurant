from datetime import date

from app.customers.models import Customer
from app.menu.schemas import MenuCategoryCreate, MenuItemCreate
from app.menu.service import create_category, create_item
from app.orders.enums import OrderStatus, PaymentStatus


def login(client, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_public_menu_item(db_session, restaurant_id):
    category = create_category(
        db_session,
        restaurant_id,
        MenuCategoryCreate(name="Public Order Test", display_order=1),
    )
    return create_item(
        db_session,
        restaurant_id,
        MenuItemCreate(
            category_id=category.id,
            name="Public Test Meal",
            description="Customer ordering fixture",
            price="55.00",
            image_url=None,
            is_available=True,
        ),
    )


def test_public_menu_and_qr_order_flow(api_client, db_session, seeded_restaurant):
    restaurant = seeded_restaurant["restaurant"]
    branch = seeded_restaurant["branch"]
    item = create_public_menu_item(db_session, restaurant.id)

    menu_response = api_client.get(
        f"/api/v1/public/restaurants/{restaurant.id}/branches/{branch.id}/menu"
    )
    assert menu_response.status_code == 200, menu_response.text
    menu = menu_response.json()
    assert menu["restaurant_name"] == restaurant.name
    assert menu["branch_name"] == branch.name
    assert menu["categories"][0]["items"][0]["name"] == item.name

    order_response = api_client.post(
        f"/api/v1/public/restaurants/{restaurant.id}/branches/{branch.id}/orders",
        json={
            "customer_name": "Public Customer",
            "customer_phone_number": "+26771112222",
            "channel": "QR",
            "payment_provider": "ORANGE_MONEY",
            "items": [{"menu_item_id": str(item.id), "quantity": 2}],
        },
    )
    assert order_response.status_code == 201, order_response.text
    payload = order_response.json()
    assert payload["order"]["channel"] == "QR"
    assert payload["order"]["order_status"] == OrderStatus.QUEUED.value
    assert payload["order"]["payment_status"] == PaymentStatus.PENDING.value
    assert payload["order"]["total"] == "110.00"
    assert payload["order"]["payment_provider"] == "ORANGE_MONEY"
    assert payload["payment"]["provider"] == "ORANGE_MONEY"
    assert payload["payment"]["status"] == "PENDING"
    assert payload["status_token"]["access_token"]
    assert payload["status_url_path"].startswith(
        f"/customer/restaurants/{restaurant.id}/branches/{branch.id}/orders/"
    )

    customer = (
        db_session.query(Customer)
        .filter(
            Customer.restaurant_id == restaurant.id,
            Customer.phone_number == "+26771112222",
        )
        .one()
    )
    assert customer.name == "Public Customer"
    assert customer.total_orders == 1

    owner_headers = login(api_client, "owner@example.com", "ownerpassword")
    customer_orders_response = api_client.get(
        f"/api/v1/restaurants/{restaurant.id}/branches/{branch.id}/orders/",
        headers=owner_headers,
        params={"business_date": date.today().isoformat(), "status": OrderStatus.QUEUED.value},
    )
    assert customer_orders_response.status_code == 200, customer_orders_response.text
    assert payload["order"]["id"] in {
        order["id"]
        for order in customer_orders_response.json()
        if order["channel"] in {"QR", "WHATSAPP"}
    }
    all_orders_response = api_client.get(
        f"/api/v1/restaurants/{restaurant.id}/branches/{branch.id}/orders/",
        headers=owner_headers,
        params={"business_date": date.today().isoformat()},
    )
    assert all_orders_response.status_code == 200, all_orders_response.text
    assert payload["order"]["id"] in {order["id"] for order in all_orders_response.json()}

    kitchen_board_response = api_client.get(
        f"/api/v1/restaurants/{restaurant.id}/branches/{branch.id}/kitchen/board",
        headers=owner_headers,
    )
    assert kitchen_board_response.status_code == 200, kitchen_board_response.text
    assert payload["order"]["id"] in {order["id"] for order in kitchen_board_response.json()["new"]}

    status_response = api_client.get(
        (
            f"/api/v1/restaurants/{restaurant.id}/branches/{branch.id}/orders/"
            f"{payload['order']['id']}/customer-status"
        ),
        params={"token": payload["status_token"]["access_token"]},
    )
    assert status_response.status_code == 200, status_response.text
    customer_status = status_response.json()
    assert customer_status["display_number"] == payload["order"]["display_number"]
    assert customer_status["payment_reference"] == payload["order"]["payment_reference"]
    assert customer_status["stage_label"] == "Queued"
    assert customer_status["payment_reference_required"] is False
    assert customer_status["message"] == (
        "Your order is moving through the kitchen. Keep your payment proof ready for collection."
    )


def test_public_whatsapp_channel_order_flow(api_client, db_session, seeded_restaurant):
    restaurant = seeded_restaurant["restaurant"]
    branch = seeded_restaurant["branch"]
    item = create_public_menu_item(db_session, restaurant.id)

    order_response = api_client.post(
        f"/api/v1/public/restaurants/{restaurant.id}/branches/{branch.id}/orders",
        json={
            "customer_name": "WhatsApp Customer",
            "customer_phone_number": "+26773334444",
            "channel": "WHATSAPP",
            "payment_provider": "ORANGE_MONEY",
            "items": [{"menu_item_id": str(item.id), "quantity": 1}],
        },
    )
    assert order_response.status_code == 201, order_response.text
    payload = order_response.json()
    assert payload["order"]["channel"] == "WHATSAPP"
    assert payload["order"]["order_status"] == OrderStatus.QUEUED.value
    assert payload["payment"]["status"] == "PENDING"


def test_public_order_can_be_prepared_before_transfer_confirmation(
    api_client,
    db_session,
    seeded_restaurant,
):
    restaurant = seeded_restaurant["restaurant"]
    branch = seeded_restaurant["branch"]
    item = create_public_menu_item(db_session, restaurant.id)
    owner_headers = login(api_client, "owner@example.com", "ownerpassword")

    order_response = api_client.post(
        f"/api/v1/public/restaurants/{restaurant.id}/branches/{branch.id}/orders",
        json={
            "customer_name": "Collection Point Customer",
            "customer_phone_number": "+26774445555",
            "channel": "QR",
            "payment_provider": "ORANGE_MONEY",
            "items": [{"menu_item_id": str(item.id), "quantity": 1}],
        },
    )
    assert order_response.status_code == 201, order_response.text
    payload = order_response.json()
    order = payload["order"]

    early_confirm_response = api_client.post(
        f"/api/v1/restaurants/{restaurant.id}/orders/{order['id']}/payments/mobile-transfer/confirm",
        headers=owner_headers,
        json={
            "amount_received": "55.00",
            "payment_reference_used": order["payment_reference"],
        },
    )
    assert early_confirm_response.status_code == 400
    assert early_confirm_response.json()["detail"] == (
        "Mobile transfer can only be confirmed when the order is ready for collection"
    )

    start_response = api_client.post(
        f"/api/v1/restaurants/{restaurant.id}/branches/{branch.id}/kitchen/orders/{order['id']}/start",
        headers=owner_headers,
    )
    assert start_response.status_code == 200, start_response.text
    ready_response = api_client.post(
        f"/api/v1/restaurants/{restaurant.id}/branches/{branch.id}/kitchen/orders/{order['id']}/ready",
        headers=owner_headers,
    )
    assert ready_response.status_code == 200, ready_response.text
    assert ready_response.json()["payment_status"] == PaymentStatus.PENDING.value

    ready_status_response = api_client.get(
        (
            f"/api/v1/restaurants/{restaurant.id}/branches/{branch.id}/orders/"
            f"{order['id']}/customer-status"
        ),
        params={"token": payload["status_token"]["access_token"]},
    )
    assert ready_status_response.status_code == 200, ready_status_response.text
    ready_status = ready_status_response.json()
    assert ready_status["order_status"] == OrderStatus.READY.value
    assert ready_status["payment_reference"] == order["payment_reference"]
    assert ready_status["payment_reference_required"] is True
    assert ready_status["collection_instruction"] == (
        "Give the cashier your order number and payment reference from your phone."
    )

    unpaid_collect_response = api_client.post(
        f"/api/v1/restaurants/{restaurant.id}/branches/{branch.id}/orders/{order['id']}/collect",
        headers=owner_headers,
    )
    assert unpaid_collect_response.status_code == 400
    assert unpaid_collect_response.json()["detail"] == "Only paid orders can be collected"

    confirm_response = api_client.post(
        f"/api/v1/restaurants/{restaurant.id}/orders/{order['id']}/payments/mobile-transfer/confirm",
        headers=owner_headers,
        json={
            "amount_received": "55.00",
            "payment_reference_used": order["payment_reference"],
        },
    )
    assert confirm_response.status_code == 201, confirm_response.text

    paid_collect_response = api_client.post(
        f"/api/v1/restaurants/{restaurant.id}/branches/{branch.id}/orders/{order['id']}/collect",
        headers=owner_headers,
    )
    assert paid_collect_response.status_code == 200, paid_collect_response.text
    assert paid_collect_response.json()["order_status"] == OrderStatus.COLLECTED.value


def test_public_customer_can_choose_pay2cell(api_client, db_session, seeded_restaurant):
    restaurant = seeded_restaurant["restaurant"]
    branch = seeded_restaurant["branch"]
    item = create_public_menu_item(db_session, restaurant.id)

    order_response = api_client.post(
        f"/api/v1/public/restaurants/{restaurant.id}/branches/{branch.id}/orders",
        json={
            "customer_name": "Pay2Cell Customer",
            "customer_phone_number": "+26776667777",
            "channel": "QR",
            "payment_provider": "PAY2CELL",
            "items": [{"menu_item_id": str(item.id), "quantity": 1}],
        },
    )
    assert order_response.status_code == 201, order_response.text
    payload = order_response.json()
    assert payload["order"]["payment_provider"] == "PAY2CELL"
    assert payload["payment"]["provider"] == "PAY2CELL"
    assert payload["payment"]["reference"] == payload["order"]["payment_reference"]


def test_public_customer_order_rejects_cash_payment(api_client, db_session, seeded_restaurant):
    restaurant = seeded_restaurant["restaurant"]
    branch = seeded_restaurant["branch"]
    item = create_public_menu_item(db_session, restaurant.id)

    order_response = api_client.post(
        f"/api/v1/public/restaurants/{restaurant.id}/branches/{branch.id}/orders",
        json={
            "customer_name": "Cash Customer",
            "customer_phone_number": "+26775556666",
            "channel": "QR",
            "payment_provider": "CASH",
            "items": [{"menu_item_id": str(item.id), "quantity": 1}],
        },
    )
    assert order_response.status_code == 400
    assert order_response.json()["detail"] == "Customer orders require a remote payment provider"
