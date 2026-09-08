import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_staging_rejects_placeholder_secrets():
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY="replace-this-with-a-long-random-local-secret",
            POSTGRES_PASSWORD="password123",
        )


def test_production_rejects_wildcard_cors():
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="x" * 32,
            POSTGRES_PASSWORD="strong-db-password",
            PAYMENT_WEBHOOK_SECRET="y" * 32,
            WHATSAPP_WEBHOOK_VERIFY_TOKEN="changed-token",
            WHATSAPP_WEBHOOK_APP_SECRET="z" * 32,
            BACKEND_CORS_ORIGINS=["*"],
        )


def test_development_allows_local_defaults():
    settings = Settings(ENVIRONMENT="development")

    assert settings.ENVIRONMENT == "development"


def test_database_url_takes_precedence_over_component_settings():
    settings = Settings(
        DATABASE_URL="postgresql://example:secret@db:5432/example",
        POSTGRES_SERVER="ignored",
    )

    assert settings.SQLALCHEMY_DATABASE_URI == "postgresql://example:secret@db:5432/example"


def test_cors_origins_accept_comma_separated_values():
    settings = Settings(BACKEND_CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3010")

    assert settings.BACKEND_CORS_ORIGINS == [
        "http://localhost:3000",
        "http://127.0.0.1:3010",
    ]


def test_cors_origins_accept_json_array_values():
    settings = Settings(BACKEND_CORS_ORIGINS='["http://localhost:3000","http://127.0.0.1:3010"]')

    assert settings.BACKEND_CORS_ORIGINS == [
        "http://localhost:3000",
        "http://127.0.0.1:3010",
    ]


def test_staging_rejects_sample_data_with_default_passwords():
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY="strong-secret-value-for-staging-123456",
            POSTGRES_PASSWORD="strong-db-password",
            PAYMENT_WEBHOOK_SECRET="strong-payment-webhook-secret-123456",
            WHATSAPP_WEBHOOK_VERIFY_TOKEN="strong-verify-token",
            WHATSAPP_WEBHOOK_APP_SECRET="strong-whatsapp-app-secret-123456",
            BACKEND_CORS_ORIGINS=["https://staging.example.com"],
            ENABLE_SAMPLE_DATA=True,
            INITIAL_ADMIN_PASSWORD="strong-admin-password",
            INITIAL_OWNER_PASSWORD="ownerpassword",
        )
