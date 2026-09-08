"""Integration test fixtures."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.auth.schemas import UserCreate
from app.auth.service import create_user, seed_roles
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.tenants.schemas import BranchCreate, RestaurantCreate
from app.tenants.service import create_branch, create_restaurant


@pytest.fixture(scope="session")
def integration_database_url() -> str:
    return os.getenv("TEST_DATABASE_URL", settings.SQLALCHEMY_DATABASE_URI)


@pytest.fixture(scope="session")
def integration_schema(integration_database_url: str) -> Generator[str, None, None]:
    schema = f"test_{uuid.uuid4().hex}"
    admin_engine = create_engine(integration_database_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL test database is not available: {exc}")

    try:
        yield schema
    finally:
        if not schema.startswith("test_"):
            raise RuntimeError(f"Refusing to drop unsafe schema name: {schema}")
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture()
def db_session(
    integration_database_url: str,
    integration_schema: str,
) -> Generator[Session, None, None]:
    base_engine = create_engine(integration_database_url)
    engine = base_engine.execution_options(schema_translate_map={None: integration_schema})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        base_engine.dispose()


@pytest.fixture()
def api_client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def seeded_restaurant(db_session: Session) -> dict[str, object]:
    seed_roles(db_session)
    admin = create_user(
        db_session,
        UserCreate(
            email="admin@example.com",
            password="adminpassword",
            first_name="Platform",
            last_name="Admin",
            role_name="ADMIN",
        ),
    )
    restaurant = create_restaurant(
        db_session,
        RestaurantCreate(name="Chicken Spot Test", code="CST"),
    )
    branch = create_branch(
        db_session,
        restaurant.id,
        BranchCreate(name="Main Mall Test", code="MMT", location="Gaborone"),
    )
    owner = create_user(
        db_session,
        UserCreate(
            email="owner@example.com",
            password="ownerpassword",
            first_name="Restaurant",
            last_name="Owner",
            role_name="OWNER",
            restaurant_id=restaurant.id,
        ),
    )
    return {
        "admin": admin,
        "owner": owner,
        "restaurant": restaurant,
        "branch": branch,
    }
