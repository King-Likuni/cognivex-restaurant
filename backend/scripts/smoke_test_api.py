"""Smoke test the local Cognivex API through HTTP.

This script assumes:
- PostgreSQL migrations have been applied.
- `python -m app.initial_data` has been run.
- Uvicorn is running locally.
"""

from __future__ import annotations

import argparse
import hmac
import json
import sys
import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha256
from typing import Any

import httpx


@dataclass(frozen=True)
class AuthSession:
    email: str
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


def request(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    expected_status: int | tuple[int, ...] = 200,
    **kwargs: Any,
) -> httpx.Response:
    response = client.request(method, path, headers=headers, **kwargs)
    expected = (expected_status,) if isinstance(expected_status, int) else expected_status
    if response.status_code not in expected:
        print(f"\n{method} {path} failed")
        print(f"Expected: {expected}")
        print(f"Actual:   {response.status_code}")
        print(response.text)
        raise SystemExit(1)
    return response


def login(client: httpx.Client, email: str, password: str) -> AuthSession:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    if response.status_code == 422:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
    if response.status_code != 200:
        print("\nPOST /api/v1/auth/login failed")
        print("Expected: (200,)")
        print(f"Actual:   {response.status_code}")
        print(response.text)
        raise SystemExit(1)
    payload = response.json()
    token = payload["access_token"]
    print(f"OK login: {email}")
    return AuthSession(email=email, token=token)


def first_named(items: list[dict[str, Any]], name: str, resource: str) -> dict[str, Any]:
    for item in items:
        if item.get("name") == name:
            return item
    print(f"\nCould not find {resource} named '{name}'.")
    print(f"Available {resource}s: {items}")
    raise SystemExit(1)


def sign_payment_webhook(payload: dict[str, Any], secret: str) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), body, sha256).hexdigest()
    return body, {
        "Content-Type": "application/json",
        "X-Cognivex-Signature": f"sha256={digest}",
    }


def wait_for_health(client: httpx.Client, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = client.get("/health", timeout=3.0)
            if response.status_code == 200:
                return response.json()
            last_error = RuntimeError(f"Unexpected /health status {response.status_code}")
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            last_error = exc
        time.sleep(1)

    print(f"\nAPI did not become healthy within {timeout_seconds:.0f} seconds.")
    if last_error is not None:
        print(f"Last health error: {last_error}")
    raise SystemExit(1)


def run_smoke_test(args: argparse.Namespace) -> None:
    unique_suffix = str(int(time.time()))

    with httpx.Client(base_url=args.base_url, timeout=args.timeout) as client:
        health = wait_for_health(client, args.health_timeout)
        print(f"OK health: {health}")

        admin = login(client, args.admin_email, args.admin_password)
        restaurants = request(
            client,
            "GET",
            "/api/v1/restaurants/",
            headers=admin.headers,
        ).json()
        restaurant = first_named(restaurants, args.restaurant_name, "restaurant")
        restaurant_id = restaurant["id"]
        print(f"OK restaurant: {restaurant['name']} ({restaurant_id})")

        branches = request(
            client,
            "GET",
            f"/api/v1/restaurants/{restaurant_id}/branches",
            headers=admin.headers,
        ).json()
        branch = first_named(branches, args.branch_name, "branch")
        branch_id = branch["id"]
        print(f"OK branch: {branch['name']} ({branch_id})")

        owner = login(client, args.owner_email, args.owner_password)

        category_name = f"Smoke Test Chicken {unique_suffix}"
        category = request(
            client,
            "POST",
            f"/api/v1/restaurants/{restaurant_id}/menu/categories",
            headers=owner.headers,
            json={"name": category_name, "display_order": 99},
            expected_status=201,
        ).json()
        print(f"OK category created: {category['name']} ({category['id']})")

        item_name = f"Smoke Test Meal {unique_suffix}"
        item = request(
            client,
            "POST",
            f"/api/v1/restaurants/{restaurant_id}/menu/items",
            headers=owner.headers,
            json={
                "category_id": category["id"],
                "name": item_name,
                "description": "Created by API smoke test",
                "price": "55.00",
                "image_url": None,
                "is_available": True,
            },
            expected_status=201,
        ).json()
        print(f"OK menu item created: {item['name']} ({item['id']})")

        ingredient = request(
            client,
            "POST",
            f"/api/v1/restaurants/{restaurant_id}/inventory/ingredients",
            headers=owner.headers,
            json={"name": f"Smoke Test Portion {unique_suffix}", "unit": "portion"},
            expected_status=201,
        ).json()
        print(f"OK ingredient created: {ingredient['name']} ({ingredient['id']})")

        kitchen_location_response = request(
            client,
            "POST",
            f"/api/v1/restaurants/{restaurant_id}/inventory/branches/{branch_id}/locations",
            headers=owner.headers,
            json={"name": "Kitchen"},
            expected_status=(201, 400),
        )
        if kitchen_location_response.status_code == 201:
            kitchen_location = kitchen_location_response.json()
        else:
            locations = request(
                client,
                "GET",
                f"/api/v1/restaurants/{restaurant_id}/inventory/branches/{branch_id}/locations",
                headers=owner.headers,
            ).json()
            kitchen_location = first_named(locations, "Kitchen", "stock location")
        print(f"OK stock location: {kitchen_location['name']} ({kitchen_location['id']})")

        opening_stock = request(
            client,
            "POST",
            f"/api/v1/restaurants/{restaurant_id}/inventory/branches/{branch_id}/movements",
            headers=owner.headers,
            json={
                "stock_location_id": kitchen_location["id"],
                "ingredient_id": ingredient["id"],
                "movement_type": "RECEIVED",
                "quantity": "10.000",
            },
            expected_status=201,
        ).json()
        print(f"OK stock received: {opening_stock['quantity']} {ingredient['unit']}")

        recipe_item = request(
            client,
            "PUT",
            f"/api/v1/restaurants/{restaurant_id}/inventory/menu-items/{item['id']}/recipe-items",
            headers=owner.headers,
            json={"ingredient_id": ingredient["id"], "quantity": "1.250"},
        ).json()
        print(
            "OK recipe linked: "
            f"{recipe_item['quantity']} {recipe_item['unit']} {recipe_item['ingredient_name']}"
        )

        public_menu = request(
            client,
            "GET",
            f"/api/v1/public/restaurants/{restaurant_id}/branches/{branch_id}/menu",
        ).json()
        public_item_ids = {
            public_item["id"]
            for category in public_menu["categories"]
            for public_item in category["items"]
        }
        if item["id"] not in public_item_ids:
            print("\nPublic QR menu did not include the smoke-test menu item.")
            print(public_menu)
            raise SystemExit(1)
        print("OK public QR menu: smoke-test item is visible")

        qr_order_payload = request(
            client,
            "POST",
            f"/api/v1/public/restaurants/{restaurant_id}/branches/{branch_id}/orders",
            json={
                "customer_name": "Smoke QR Customer",
                "customer_phone_number": "+26771112222",
                "channel": "QR",
                "payment_provider": "ORANGE_MONEY",
                "items": [{"menu_item_id": item["id"], "quantity": 1}],
            },
            expected_status=201,
        ).json()
        qr_order = qr_order_payload["order"]
        qr_payment = qr_order_payload["payment"]
        if qr_order["channel"] != "QR" or qr_payment["status"] != "PENDING":
            print("\nPublic QR order did not return the expected pending payment state.")
            print(qr_order_payload)
            raise SystemExit(1)
        print(
            f"OK public QR order created: {qr_order['display_number']} "
            f"payment={qr_payment['status']}"
        )

        qr_webhook_body, qr_webhook_headers = sign_payment_webhook(
            {
                "provider_event_id": f"smoke-qr-provider-event-{unique_suffix}",
                "reference": qr_payment["reference"],
                "status": "PAID",
                "amount": qr_payment["amount"],
                "currency": qr_payment["currency"],
                "provider_transaction_id": f"smoke-qr-provider-txn-{unique_suffix}",
            },
            args.payment_webhook_secret,
        )
        request(
            client,
            "POST",
            "/api/v1/webhooks/payments/ORANGE_MONEY",
            headers=qr_webhook_headers,
            content=qr_webhook_body,
        )
        qr_status = request(
            client,
            "GET",
            (
                f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/"
                f"{qr_order['id']}/customer-status"
            ),
            params={"token": qr_order_payload["status_token"]["access_token"]},
        ).json()
        if qr_status["order_status"] != "QUEUED":
            print("\nPublic QR order did not move to the kitchen queue after payment.")
            print(qr_status)
            raise SystemExit(1)
        print(f"OK public QR status after payment: {qr_status['order_status']}")

        whatsapp_order_payload = request(
            client,
            "POST",
            f"/api/v1/public/restaurants/{restaurant_id}/branches/{branch_id}/orders",
            json={
                "customer_name": "Smoke WhatsApp Customer",
                "customer_phone_number": "+26773334444",
                "channel": "WHATSAPP",
                "payment_provider": "ORANGE_MONEY",
                "items": [{"menu_item_id": item["id"], "quantity": 1}],
            },
            expected_status=201,
        ).json()
        if whatsapp_order_payload["order"]["channel"] != "WHATSAPP":
            print("\nPublic WhatsApp-channel order did not preserve the channel.")
            print(whatsapp_order_payload)
            raise SystemExit(1)
        print(
            "OK public WhatsApp order accepted: "
            f"{whatsapp_order_payload['order']['display_number']}"
        )

        report_before_order = request(
            client,
            "GET",
            f"/api/v1/restaurants/{restaurant_id}/reports/daily-sales",
            headers=owner.headers,
            params={"business_date": date.today().isoformat(), "branch_id": branch_id},
        ).json()
        revenue_before_order = Decimal(report_before_order["revenue"])
        collected_before_order = int(report_before_order["collected_orders"])

        order = request(
            client,
            "POST",
            f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/cashier",
            headers=owner.headers,
            json={
                "customer_id": None,
                "items": [{"menu_item_id": item["id"], "quantity": 2}],
                "payment_method": "CASH",
            },
            expected_status=201,
        ).json()
        print(f"OK cashier order created: {order['display_number']}")
        print(f"OK payment reference: {order['payment_reference']}")
        print(f"OK total: {order['currency']} {order['total']}")
        print(f"OK statuses: order={order['order_status']} payment={order['payment_status']}")

        payment = request(
            client,
            "POST",
            f"/api/v1/restaurants/{restaurant_id}/orders/{order['id']}/payments/cash/confirm",
            headers=owner.headers,
            json={"amount_received": order["total"]},
            expected_status=201,
        ).json()
        print(f"OK cash payment confirmed: {payment['status']} ({payment['reference']})")

        board = request(
            client,
            "GET",
            f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/kitchen/board",
            headers=owner.headers,
        ).json()
        queued_ids = {queued_order["id"] for queued_order in board["new"]}
        if order["id"] not in queued_ids:
            print("\nCreated order was not visible on the kitchen board.")
            print(board)
            raise SystemExit(1)
        print("OK kitchen board: order is queued")

        preparing_order = request(
            client,
            "POST",
            f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/kitchen/orders/{order['id']}/start",
            headers=owner.headers,
        ).json()
        print(f"OK kitchen start: {preparing_order['order_status']}")

        ready_order = request(
            client,
            "POST",
            f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/kitchen/orders/{order['id']}/ready",
            headers=owner.headers,
        ).json()
        print(f"OK kitchen ready: {ready_order['order_status']}")

        collected_order = request(
            client,
            "POST",
            f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/{order['id']}/collect",
            headers=owner.headers,
        ).json()
        print(f"OK order collected: {collected_order['order_status']}")

        balances = request(
            client,
            "GET",
            f"/api/v1/restaurants/{restaurant_id}/inventory/branches/{branch_id}/balances",
            headers=owner.headers,
            params={"stock_location_id": kitchen_location["id"]},
        ).json()
        ingredient_balance = next(
            balance for balance in balances if balance["ingredient_id"] == ingredient["id"]
        )
        if Decimal(ingredient_balance["quantity_on_hand"]) != Decimal("7.500"):
            print("\nInventory balance did not reflect order consumption.")
            print(ingredient_balance)
            raise SystemExit(1)
        print(f"OK inventory consumed: balance={ingredient_balance['quantity_on_hand']}")

        report = request(
            client,
            "GET",
            f"/api/v1/restaurants/{restaurant_id}/reports/daily-sales",
            headers=owner.headers,
            params={"business_date": date.today().isoformat(), "branch_id": branch_id},
        ).json()
        expected_revenue = revenue_before_order + Decimal(order["total"])
        if Decimal(report["revenue"]) < expected_revenue:
            print("\nDaily sales report did not include the collected order revenue.")
            print(report)
            raise SystemExit(1)
        if int(report["collected_orders"]) < collected_before_order + 1:
            print("\nDaily sales report did not include the collected order count.")
            print(report)
            raise SystemExit(1)
        print(
            f"OK daily sales report: revenue={report['revenue']} collected={report['collected_orders']}"
        )

        remote_order = request(
            client,
            "POST",
            f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/cashier",
            headers=owner.headers,
            json={
                "customer_id": None,
                "items": [{"menu_item_id": item["id"], "quantity": 1}],
                "payment_method": "CASH",
            },
            expected_status=201,
        ).json()
        remote_payment = request(
            client,
            "POST",
            f"/api/v1/restaurants/{restaurant_id}/orders/{remote_order['id']}/payments",
            headers=owner.headers,
            json={"provider": "ORANGE_MONEY", "customer_phone_number": "+26770000000"},
            expected_status=201,
        ).json()
        print(
            f"OK remote payment initiated: {remote_payment['provider']} {remote_payment['status']}"
        )

        webhook_body, webhook_headers = sign_payment_webhook(
            {
                "provider_event_id": f"smoke-provider-event-{unique_suffix}",
                "reference": remote_payment["reference"],
                "status": "PAID",
                "amount": remote_payment["amount"],
                "currency": remote_payment["currency"],
                "provider_transaction_id": f"smoke-provider-txn-{unique_suffix}",
            },
            args.payment_webhook_secret,
        )
        webhook_result = request(
            client,
            "POST",
            "/api/v1/webhooks/payments/ORANGE_MONEY",
            headers=webhook_headers,
            content=webhook_body,
        ).json()
        print(
            "OK remote payment webhook: "
            f"{webhook_result['status']} idempotent={webhook_result['idempotent']}"
        )

        remote_preparing = request(
            client,
            "POST",
            f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/kitchen/orders/{remote_order['id']}/start",
            headers=owner.headers,
        ).json()
        remote_ready = request(
            client,
            "POST",
            f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/kitchen/orders/{remote_order['id']}/ready",
            headers=owner.headers,
        ).json()
        remote_uncollected = request(
            client,
            "POST",
            f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/{remote_order['id']}/uncollected",
            headers=owner.headers,
        ).json()
        print(
            "OK remote payment order flow: "
            f"{remote_preparing['order_status']} -> {remote_ready['order_status']} -> "
            f"{remote_uncollected['order_status']}"
        )

    print("\nSmoke test passed.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local API smoke test.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--health-timeout", type=float, default=60.0)
    parser.add_argument("--admin-email", default="admin@cognivex.com")
    parser.add_argument("--admin-password", default="adminpassword")
    parser.add_argument("--owner-email", default="owner@chickenspot.com")
    parser.add_argument("--owner-password", default="ownerpassword")
    parser.add_argument("--restaurant-name", default="Chicken Spot")
    parser.add_argument("--branch-name", default="Main Mall")
    parser.add_argument("--payment-webhook-secret", default="replace-this-payment-webhook-secret")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        run_smoke_test(parse_args())
    except httpx.ConnectError:
        print("Could not connect to the API. Start Uvicorn first: uvicorn app.main:app --reload")
        sys.exit(1)
