from datetime import date

from app.customers.models import Customer
from app.menu.schemas import MenuCategoryCreate, MenuItemCreate
from app.menu.service import create_category, create_item


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
    assert payload["order"]["total"] == "110.00"
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
        params={"business_date": date.today().isoformat(), "status": "PENDING_PAYMENT"},
    )
    assert customer_orders_response.status_code == 200, customer_orders_response.text
    assert payload["order"]["id"] in {
        order["id"]
        for order in customer_orders_response.json()
        if order["channel"] in {"QR", "WHATSAPP"}
    }

    status_response = api_client.get(
        (
            f"/api/v1/restaurants/{restaurant.id}/branches/{branch.id}/orders/"
            f"{payload['order']['id']}/customer-status"
        ),
        params={"token": payload["status_token"]["access_token"]},
    )
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["display_number"] == payload["order"]["display_number"]


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
    assert payload["payment"]["status"] == "PENDING"


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
