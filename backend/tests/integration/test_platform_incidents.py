import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.schemas import PlatformUserInviteCreate
from app.auth.service import create_platform_user_invite, set_password_with_token

pytestmark = pytest.mark.integration


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_frontend_errors_are_visible_to_platform_roles_and_resolved_by_admin(
    api_client: TestClient,
    db_session: Session,
    seeded_restaurant: dict[str, object],
):
    admin_headers = login(api_client, "admin@example.com", "adminpassword")
    owner_headers = login(api_client, "owner@example.com", "ownerpassword")
    support_user, _reset_token, raw_token = create_platform_user_invite(
        db_session,
        PlatformUserInviteCreate(
            email="incident-support@example.com",
            first_name="Incident",
            last_name="Support",
            role_name="SUPPORT",
        ),
        created_by=seeded_restaurant["admin"].id,
    )
    assert set_password_with_token(db_session, raw_token, "supportpassword") is not None
    support_headers = login(api_client, support_user.email, "supportpassword")

    report_response = api_client.post(
        "/api/v1/platform/incidents/frontend-errors",
        json={
            "message": "Platform health render failed",
            "stack": "Error: Platform health render failed",
            "component_stack": "PlatformAdminView",
            "path": "/",
            "url": "https://cognivex-restaurant.vercel.app/",
            "user_email": "admin@example.com",
            "user_role": "ADMIN",
        },
    )
    assert report_response.status_code == 202, report_response.text
    incident = report_response.json()
    assert incident["category"] == "FRONTEND_ERROR"
    assert incident["status"] == "OPEN"

    forbidden_summary = api_client.get("/api/v1/platform/incidents/summary", headers=owner_headers)
    assert forbidden_summary.status_code == 403

    summary_response = api_client.get(
        "/api/v1/platform/incidents/summary",
        headers=support_headers,
    )
    assert summary_response.status_code == 200, summary_response.text
    summary = summary_response.json()
    assert summary["system"]["database"] == "ok"
    assert summary["frontend_errors_last_24h"] >= 1
    assert summary["open_incidents"] >= 1
    assert any(row["id"] == incident["id"] for row in summary["recent_incidents"])

    support_resolve_response = api_client.patch(
        f"/api/v1/platform/incidents/{incident['id']}/resolve",
        headers=support_headers,
    )
    assert support_resolve_response.status_code == 403

    resolve_response = api_client.patch(
        f"/api/v1/platform/incidents/{incident['id']}/resolve",
        headers=admin_headers,
    )
    assert resolve_response.status_code == 200, resolve_response.text
    assert resolve_response.json()["status"] == "RESOLVED"
