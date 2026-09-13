from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.schemas import UserCreate
from app.auth.service import create_user
from app.tenants.schemas import BranchCreate, RestaurantCreate
from app.tenants.service import create_branch, create_restaurant

pytestmark = pytest.mark.integration


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_second_restaurant(db_session: Session) -> dict[str, object]:
    restaurant = create_restaurant(
        db_session,
        RestaurantCreate(name="Burger Barn Test", code="BBT"),
    )
    branch = create_branch(
        db_session,
        restaurant.id,
        BranchCreate(name="Station Test", code="STN", location="Gaborone"),
    )
    owner = create_user(
        db_session,
        UserCreate(
            email="owner2@example.com",
            password="ownerpassword",
            first_name="Second",
            last_name="Owner",
            role_name="OWNER",
            restaurant_id=restaurant.id,
        ),
    )
    cashier = create_user(
        db_session,
        UserCreate(
            email="cashier2@example.com",
            password="cashierpassword",
            first_name="Second",
            last_name="Cashier",
            role_name="CASHIER",
            restaurant_id=restaurant.id,
            branch_ids=[branch.id],
        ),
    )
    return {"restaurant": restaurant, "branch": branch, "owner": owner, "cashier": cashier}


def create_menu_item(
    client: TestClient,
    restaurant_id: str,
    headers: dict[str, str],
    *,
    item_name: str = "Isolation Meal",
) -> dict[str, str]:
    category_response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/menu/categories",
        headers=headers,
        json={"name": "Isolation Category", "display_order": 1},
    )
    assert category_response.status_code == 201, category_response.text
    category = category_response.json()
    item_response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/menu/items",
        headers=headers,
        json={
            "category_id": category["id"],
            "name": item_name,
            "description": None,
            "price": "50.00",
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
) -> dict[str, str]:
    item = create_menu_item(client, restaurant_id, headers)
    order_response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/branches/{branch_id}/orders/cashier",
        headers=headers,
        json={
            "customer_id": None,
            "items": [{"menu_item_id": item["id"], "quantity": 1}],
            "payment_method": "CASH",
        },
    )
    assert order_response.status_code == 201, order_response.text
    order = order_response.json()
    payment_response = client.post(
        f"/api/v1/restaurants/{restaurant_id}/orders/{order['id']}/payments/cash/confirm",
        headers=headers,
        json={"amount_received": "50.00"},
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
    return ready_response.json()


def test_owner_cannot_read_or_write_another_restaurant(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    other = create_second_restaurant(db_session)
    first_restaurant_id = str(seeded_restaurant["restaurant"].id)
    other_restaurant_id = str(other["restaurant"].id)
    first_owner_headers = login(api_client, "owner@example.com", "ownerpassword")

    get_response = api_client.get(
        f"/api/v1/restaurants/{other_restaurant_id}",
        headers=first_owner_headers,
    )
    assert get_response.status_code == 403

    branches_response = api_client.get(
        f"/api/v1/restaurants/{other_restaurant_id}/branches",
        headers=first_owner_headers,
    )
    assert branches_response.status_code == 403

    category_response = api_client.post(
        f"/api/v1/restaurants/{other_restaurant_id}/menu/categories",
        headers=first_owner_headers,
        json={"name": "Should Fail", "display_order": 1},
    )
    assert category_response.status_code == 403

    own_restaurant_response = api_client.get(
        f"/api/v1/restaurants/{first_restaurant_id}",
        headers=first_owner_headers,
    )
    assert own_restaurant_response.status_code == 200


def test_cross_tenant_branch_and_order_operations_are_blocked(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    other = create_second_restaurant(db_session)
    first_restaurant_id = str(seeded_restaurant["restaurant"].id)
    first_branch_id = str(seeded_restaurant["branch"].id)
    other_restaurant_id = str(other["restaurant"].id)
    other_branch_id = str(other["branch"].id)
    first_owner_headers = login(api_client, "owner@example.com", "ownerpassword")
    other_owner_headers = login(api_client, "owner2@example.com", "ownerpassword")

    item = create_menu_item(api_client, first_restaurant_id, first_owner_headers)

    create_cross_order_response = api_client.post(
        f"/api/v1/restaurants/{first_restaurant_id}/branches/{first_branch_id}/orders/cashier",
        headers=other_owner_headers,
        json={
            "customer_id": None,
            "items": [{"menu_item_id": item["id"], "quantity": 1}],
            "payment_method": "CASH",
        },
    )
    assert create_cross_order_response.status_code == 403

    mismatched_branch_response = api_client.post(
        f"/api/v1/restaurants/{first_restaurant_id}/branches/{other_branch_id}/orders/cashier",
        headers=first_owner_headers,
        json={
            "customer_id": None,
            "items": [{"menu_item_id": item["id"], "quantity": 1}],
            "payment_method": "CASH",
        },
    )
    assert mismatched_branch_response.status_code == 403

    other_order = create_ready_order(
        api_client,
        other_restaurant_id,
        other_branch_id,
        other_owner_headers,
    )
    cross_collect_response = api_client.post(
        f"/api/v1/restaurants/{other_restaurant_id}/branches/{other_branch_id}/orders/{other_order['id']}/collect",
        headers=first_owner_headers,
    )
    assert cross_collect_response.status_code == 403


def test_cashier_branch_list_only_includes_assigned_branches(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    restaurant = seeded_restaurant["restaurant"]
    assigned_branch = seeded_restaurant["branch"]
    other_branch = create_branch(
        db_session,
        restaurant.id,
        BranchCreate(name="Airport Test", code="APT", location="Gaborone"),
    )
    create_user(
        db_session,
        UserCreate(
            email="cashier@example.com",
            password="cashierpassword",
            first_name="Branch",
            last_name="Cashier",
            role_name="CASHIER",
            restaurant_id=restaurant.id,
            branch_ids=[assigned_branch.id],
        ),
    )
    cashier_headers = login(api_client, "cashier@example.com", "cashierpassword")

    response = api_client.get(
        f"/api/v1/restaurants/{restaurant.id}/branches",
        headers=cashier_headers,
    )

    assert response.status_code == 200, response.text
    branch_ids = {branch["id"] for branch in response.json()}
    assert branch_ids == {str(assigned_branch.id)}
    assert str(other_branch.id) not in branch_ids

    owner_headers = login(api_client, "owner@example.com", "ownerpassword")
    item = create_menu_item(api_client, str(restaurant.id), owner_headers)
    allowed_order_response = api_client.post(
        f"/api/v1/restaurants/{restaurant.id}/branches/{assigned_branch.id}/orders/cashier",
        headers=cashier_headers,
        json={
            "customer_id": None,
            "items": [{"menu_item_id": item["id"], "quantity": 1}],
            "payment_method": "CASH",
        },
    )
    assert allowed_order_response.status_code == 201, allowed_order_response.text

    forbidden_order_response = api_client.post(
        f"/api/v1/restaurants/{restaurant.id}/branches/{other_branch.id}/orders/cashier",
        headers=cashier_headers,
        json={
            "customer_id": None,
            "items": [{"menu_item_id": item["id"], "quantity": 1}],
            "payment_method": "CASH",
        },
    )
    assert forbidden_order_response.status_code == 403


def test_owner_can_deactivate_placeholder_branch(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    restaurant = seeded_restaurant["restaurant"]
    create_branch(
        db_session,
        restaurant.id,
        BranchCreate(name="string", code="BAD", location="placeholder"),
    )
    owner_headers = login(api_client, "owner@example.com", "ownerpassword")

    all_branches_response = api_client.get(
        f"/api/v1/restaurants/{restaurant.id}/branches",
        headers=owner_headers,
        params={"include_inactive": "true"},
    )
    assert all_branches_response.status_code == 200, all_branches_response.text
    placeholder_branch = next(
        branch for branch in all_branches_response.json() if branch["name"] == "string"
    )

    update_response = api_client.patch(
        f"/api/v1/restaurants/{restaurant.id}/branches/{placeholder_branch['id']}",
        headers=owner_headers,
        json={"name": "Legacy Placeholder", "code": "LEGACY", "is_active": False},
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["name"] == "Legacy Placeholder"
    assert update_response.json()["code"] == "LEGACY"
    assert update_response.json()["is_active"] is False

    active_branches_response = api_client.get(
        f"/api/v1/restaurants/{restaurant.id}/branches",
        headers=owner_headers,
    )
    assert active_branches_response.status_code == 200
    active_branch_ids = {branch["id"] for branch in active_branches_response.json()}
    assert placeholder_branch["id"] not in active_branch_ids

    audit_response = api_client.get(
        f"/api/v1/restaurants/{restaurant.id}/audit-logs/",
        headers=owner_headers,
        params={"action": "BRANCH_UPDATED", "entity_type": "branch"},
    )
    assert audit_response.status_code == 200, audit_response.text
    assert any(row["entity_id"] == placeholder_branch["id"] for row in audit_response.json())


def test_only_owner_or_admin_can_manage_inactive_branches(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    restaurant = seeded_restaurant["restaurant"]
    branch = seeded_restaurant["branch"]
    manager = create_user(
        db_session,
        UserCreate(
            email="branch-manager@example.com",
            password="managerpassword",
            first_name="Branch",
            last_name="Manager",
            role_name="MANAGER",
            restaurant_id=restaurant.id,
            branch_ids=[branch.id],
        ),
    )
    assert manager.id
    manager_headers = login(api_client, "branch-manager@example.com", "managerpassword")

    inactive_list_response = api_client.get(
        f"/api/v1/restaurants/{restaurant.id}/branches",
        headers=manager_headers,
        params={"include_inactive": "true"},
    )
    assert inactive_list_response.status_code == 403

    update_response = api_client.patch(
        f"/api/v1/restaurants/{restaurant.id}/branches/{branch.id}",
        headers=manager_headers,
        json={"location": "Updated by manager"},
    )
    assert update_response.status_code == 403


def test_cannot_deactivate_last_active_branch(
    api_client: TestClient,
    seeded_restaurant: dict[str, object],
):
    restaurant = seeded_restaurant["restaurant"]
    branch = seeded_restaurant["branch"]
    owner_headers = login(api_client, "owner@example.com", "ownerpassword")

    response = api_client.patch(
        f"/api/v1/restaurants/{restaurant.id}/branches/{branch.id}",
        headers=owner_headers,
        json={"is_active": False},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "At least one active branch is required"


def test_cross_tenant_payment_kitchen_and_report_access_are_blocked(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    other = create_second_restaurant(db_session)
    first_owner_headers = login(api_client, "owner@example.com", "ownerpassword")
    other_owner_headers = login(api_client, "owner2@example.com", "ownerpassword")
    first_restaurant_id = str(seeded_restaurant["restaurant"].id)
    other_restaurant_id = str(other["restaurant"].id)
    other_branch_id = str(other["branch"].id)

    item = create_menu_item(api_client, other_restaurant_id, other_owner_headers)
    order_response = api_client.post(
        f"/api/v1/restaurants/{other_restaurant_id}/branches/{other_branch_id}/orders/cashier",
        headers=other_owner_headers,
        json={
            "customer_id": None,
            "items": [{"menu_item_id": item["id"], "quantity": 1}],
            "payment_method": "CASH",
        },
    )
    assert order_response.status_code == 201, order_response.text
    order = order_response.json()

    payment_response = api_client.post(
        f"/api/v1/restaurants/{other_restaurant_id}/orders/{order['id']}/payments/cash/confirm",
        headers=first_owner_headers,
        json={"amount_received": "50.00"},
    )
    assert payment_response.status_code == 403

    kitchen_response = api_client.get(
        f"/api/v1/restaurants/{other_restaurant_id}/branches/{other_branch_id}/kitchen/board",
        headers=first_owner_headers,
    )
    assert kitchen_response.status_code == 403

    report_response = api_client.get(
        f"/api/v1/restaurants/{other_restaurant_id}/reports/daily-sales",
        headers=first_owner_headers,
        params={"business_date": date.today().isoformat()},
    )
    assert report_response.status_code == 403

    hidden_order_payment_response = api_client.post(
        f"/api/v1/restaurants/{first_restaurant_id}/orders/{order['id']}/payments/cash/confirm",
        headers=first_owner_headers,
        json={"amount_received": "50.00"},
    )
    assert hidden_order_payment_response.status_code == 400


def test_admin_can_cross_restaurant_boundary_for_platform_operations(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    other = create_second_restaurant(db_session)
    admin_headers = login(api_client, "admin@example.com", "adminpassword")
    other_restaurant_id = str(other["restaurant"].id)

    list_response = api_client.get("/api/v1/restaurants/", headers=admin_headers)
    assert list_response.status_code == 200
    names = {restaurant["name"] for restaurant in list_response.json()}
    assert {"Chicken Spot Test", "Burger Barn Test"}.issubset(names)

    get_response = api_client.get(
        f"/api/v1/restaurants/{other_restaurant_id}",
        headers=admin_headers,
    )
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Burger Barn Test"

    branch_response = api_client.patch(
        f"/api/v1/restaurants/{other_restaurant_id}/branches/{other['branch'].id}",
        headers=admin_headers,
        json={"location": "Admin Updated"},
    )
    assert branch_response.status_code == 200, branch_response.text
    assert branch_response.json()["location"] == "Admin Updated"


def test_admin_can_create_first_restaurant_owner(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    admin_headers = login(api_client, "admin@example.com", "adminpassword")
    restaurant_id = str(seeded_restaurant["restaurant"].id)

    response = api_client.post(
        "/api/v1/auth/users",
        headers=admin_headers,
        json={
            "email": "new-owner@example.com",
            "password": "new-owner-password",
            "first_name": "New",
            "last_name": "Owner",
            "role_name": "OWNER",
            "restaurant_id": restaurant_id,
            "branch_ids": [],
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["role_name"] == "OWNER"
    assert payload["restaurant_id"] == restaurant_id


def test_owner_cannot_create_user_for_another_restaurant(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    other = create_second_restaurant(db_session)
    first_owner_headers = login(api_client, "owner@example.com", "ownerpassword")

    response = api_client.post(
        "/api/v1/auth/users",
        headers=first_owner_headers,
        json={
            "email": "cross-tenant-manager@example.com",
            "password": "manager-password",
            "first_name": "Cross",
            "last_name": "Tenant",
            "role_name": "MANAGER",
            "restaurant_id": str(other["restaurant"].id),
            "branch_ids": [],
        },
    )

    assert response.status_code == 403


def test_manager_cannot_create_staff_users(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    restaurant = seeded_restaurant["restaurant"]
    branch = seeded_restaurant["branch"]
    create_user(
        db_session,
        UserCreate(
            email="staff-manager@example.com",
            password="managerpassword",
            first_name="Staff",
            last_name="Manager",
            role_name="MANAGER",
            restaurant_id=restaurant.id,
            branch_ids=[branch.id],
        ),
    )
    manager_headers = login(api_client, "staff-manager@example.com", "managerpassword")

    response = api_client.post(
        "/api/v1/auth/users",
        headers=manager_headers,
        json={
            "email": "manager-created-cashier@example.com",
            "password": "cashierpassword",
            "first_name": "Manager",
            "last_name": "Cashier",
            "role_name": "CASHIER",
            "restaurant_id": str(restaurant.id),
            "branch_ids": [str(branch.id)],
        },
    )

    assert response.status_code == 403


def test_owner_can_manage_restaurant_staff(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    restaurant = seeded_restaurant["restaurant"]
    branch = seeded_restaurant["branch"]
    second_branch = create_branch(
        db_session,
        restaurant.id,
        BranchCreate(name="University Test", code="UB", location="Gaborone"),
    )
    owner_headers = login(api_client, "owner@example.com", "ownerpassword")

    create_response = api_client.post(
        "/api/v1/auth/users",
        headers=owner_headers,
        json={
            "email": "managed-cashier@example.com",
            "password": "cashierpassword",
            "first_name": "Managed",
            "last_name": "Cashier",
            "role_name": "CASHIER",
            "restaurant_id": str(restaurant.id),
            "branch_ids": [str(branch.id)],
        },
    )
    assert create_response.status_code == 201, create_response.text
    cashier = create_response.json()
    assert cashier["branch_ids"] == [str(branch.id)]
    assert cashier["branch_assignments"] == [
        {"id": str(branch.id), "code": branch.code, "name": branch.name}
    ]
    assert cashier["created_at"] is not None

    list_response = api_client.get(
        "/api/v1/auth/users",
        headers=owner_headers,
        params={"restaurant_id": str(restaurant.id)},
    )
    assert list_response.status_code == 200, list_response.text
    assert {user["email"] for user in list_response.json()} >= {
        "owner@example.com",
        "managed-cashier@example.com",
    }

    update_response = api_client.patch(
        f"/api/v1/auth/users/{cashier['id']}",
        headers=owner_headers,
        json={
            "role_name": "KITCHEN",
            "branch_ids": [str(second_branch.id)],
            "is_active": False,
        },
    )
    assert update_response.status_code == 200, update_response.text
    updated_cashier = update_response.json()
    assert updated_cashier["role_name"] == "KITCHEN"
    assert updated_cashier["branch_ids"] == [str(second_branch.id)]
    assert updated_cashier["is_active"] is False

    audit_response = api_client.get(
        f"/api/v1/restaurants/{restaurant.id}/audit-logs/",
        headers=owner_headers,
        params={"entity_type": "user", "user_id": str(seeded_restaurant["owner"].id)},
    )
    assert audit_response.status_code == 200, audit_response.text
    assert {"STAFF_CREATED", "STAFF_UPDATED"}.issubset(
        {row["action"] for row in audit_response.json()}
    )

    login_response = api_client.post(
        "/api/v1/auth/login",
        data={"username": "managed-cashier@example.com", "password": "cashierpassword"},
    )
    assert login_response.status_code == 401


def test_owner_can_invite_staff_to_set_their_password(
    api_client: TestClient,
    seeded_restaurant: dict[str, object],
):
    restaurant = seeded_restaurant["restaurant"]
    branch = seeded_restaurant["branch"]
    owner_headers = login(api_client, "owner@example.com", "ownerpassword")

    invite_response = api_client.post(
        "/api/v1/auth/users/invite",
        headers=owner_headers,
        json={
            "email": "invited-cashier@example.com",
            "first_name": "Invited",
            "last_name": "Cashier",
            "role_name": "CASHIER",
            "restaurant_id": str(restaurant.id),
            "branch_ids": [str(branch.id)],
        },
    )
    assert invite_response.status_code == 201, invite_response.text
    invite = invite_response.json()
    assert invite["user"]["email"] == "invited-cashier@example.com"
    assert invite["invite"]["setup_url_path"].startswith("/password-setup?token=")
    token = invite["invite"]["token"]

    preview_response = api_client.get(f"/api/v1/auth/password-setup/{token}")
    assert preview_response.status_code == 200, preview_response.text
    assert preview_response.json()["email"] == "invited-cashier@example.com"

    confirm_response = api_client.post(
        "/api/v1/auth/password-setup/confirm",
        json={"token": token, "password": "newcashierpassword"},
    )
    assert confirm_response.status_code == 200, confirm_response.text

    login_response = api_client.post(
        "/api/v1/auth/login",
        data={"username": "invited-cashier@example.com", "password": "newcashierpassword"},
    )
    assert login_response.status_code == 200, login_response.text

    reuse_response = api_client.post(
        "/api/v1/auth/password-setup/confirm",
        json={"token": token, "password": "secondpassword"},
    )
    assert reuse_response.status_code == 404


def test_new_password_setup_link_invalidates_previous_link(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    restaurant = seeded_restaurant["restaurant"]
    branch = seeded_restaurant["branch"]
    user = create_user(
        db_session,
        UserCreate(
            email="reset-cashier@example.com",
            password="cashierpassword",
            first_name="Reset",
            last_name="Cashier",
            role_name="CASHIER",
            restaurant_id=restaurant.id,
            branch_ids=[branch.id],
        ),
    )
    owner_headers = login(api_client, "owner@example.com", "ownerpassword")

    first_reset_response = api_client.post(
        f"/api/v1/auth/users/{user.id}/password-reset",
        headers=owner_headers,
    )
    assert first_reset_response.status_code == 200, first_reset_response.text
    first_token = first_reset_response.json()["token"]

    second_reset_response = api_client.post(
        f"/api/v1/auth/users/{user.id}/password-reset",
        headers=owner_headers,
    )
    assert second_reset_response.status_code == 200, second_reset_response.text
    second_token = second_reset_response.json()["token"]
    assert second_token != first_token

    first_preview_response = api_client.get(f"/api/v1/auth/password-setup/{first_token}")
    assert first_preview_response.status_code == 404

    second_confirm_response = api_client.post(
        "/api/v1/auth/password-setup/confirm",
        json={"token": second_token, "password": "resetcashierpassword"},
    )
    assert second_confirm_response.status_code == 200, second_confirm_response.text

    login_response = api_client.post(
        "/api/v1/auth/login",
        data={"username": "reset-cashier@example.com", "password": "resetcashierpassword"},
    )
    assert login_response.status_code == 200, login_response.text


def test_owner_cannot_manage_staff_for_another_restaurant(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    other = create_second_restaurant(db_session)
    owner_headers = login(api_client, "owner@example.com", "ownerpassword")

    list_response = api_client.get(
        "/api/v1/auth/users",
        headers=owner_headers,
        params={"restaurant_id": str(other["restaurant"].id)},
    )
    assert list_response.status_code == 403

    update_response = api_client.patch(
        f"/api/v1/auth/users/{other['cashier'].id}",
        headers=owner_headers,
        json={"is_active": False},
    )
    assert update_response.status_code == 403


def test_owner_cannot_deactivate_last_active_owner(
    api_client: TestClient,
    seeded_restaurant: dict[str, object],
):
    owner = seeded_restaurant["owner"]
    owner_headers = login(api_client, "owner@example.com", "ownerpassword")

    response = api_client.patch(
        f"/api/v1/auth/users/{owner.id}",
        headers=owner_headers,
        json={"is_active": False},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "You cannot deactivate your own account"


def test_admin_cannot_remove_last_active_restaurant_owner(
    api_client: TestClient,
    seeded_restaurant: dict[str, object],
):
    owner = seeded_restaurant["owner"]
    admin_headers = login(api_client, "admin@example.com", "adminpassword")

    deactivate_response = api_client.patch(
        f"/api/v1/auth/users/{owner.id}",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert deactivate_response.status_code == 400
    assert deactivate_response.json()["detail"] == "At least one active owner is required"

    demote_response = api_client.patch(
        f"/api/v1/auth/users/{owner.id}",
        headers=admin_headers,
        json={"role_name": "MANAGER"},
    )
    assert demote_response.status_code == 400
    assert demote_response.json()["detail"] == "At least one active owner is required"
