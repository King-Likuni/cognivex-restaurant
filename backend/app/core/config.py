import json
from typing import Annotated, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Cognivex Restaurant Platform"
    VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "test", "staging", "production"] = "development"
    API_V1_STR: str = "/api/v1"

    # Postgres
    POSTGRES_SERVER: str = "127.0.0.1"
    POSTGRES_USER: str = "cognivex"
    POSTGRES_PASSWORD: str = "change-me"
    POSTGRES_DB: str = "cognivex_restaurant"
    POSTGRES_PORT: str = "5435"
    DATABASE_URL: str | None = None
    SQLALCHEMY_DATABASE_URI_OVERRIDE: str | None = None

    # Redis
    REDIS_URL: str = "redis://127.0.0.1:6379/0"

    # Browser clients allowed to call the API.
    BACKEND_CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        if self.SQLALCHEMY_DATABASE_URI_OVERRIDE:
            return self.SQLALCHEMY_DATABASE_URI_OVERRIDE
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # JWT Security
    SECRET_KEY: str = "replace-this-with-a-long-random-local-secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    PAYMENT_WEBHOOK_SECRET: str = "replace-this-payment-webhook-secret"
    WHATSAPP_WEBHOOK_VERIFY_TOKEN: str = "replace-this-whatsapp-verify-token"
    WHATSAPP_WEBHOOK_APP_SECRET: str = "replace-this-whatsapp-app-secret"
    INITIAL_ADMIN_EMAIL: str = "admin@cognivex.com"
    INITIAL_ADMIN_PASSWORD: str = "adminpassword"
    INITIAL_OWNER_EMAIL: str = "owner@chickenspot.com"
    INITIAL_OWNER_PASSWORD: str = "ownerpassword"
    ENABLE_SAMPLE_DATA: bool = True

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                parsed = json.loads(stripped)
                if not isinstance(parsed, list):
                    raise ValueError("BACKEND_CORS_ORIGINS must be a list of origins")
                return [str(origin).strip() for origin in parsed if str(origin).strip()]
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def reject_placeholder_production_secrets(self) -> "Settings":
        if self.ENVIRONMENT in {"staging", "production"}:

            def is_weak_secret(value: str, *, min_length: int = 32) -> bool:
                normalized = value.lower()
                return (
                    len(value) < min_length
                    or "change" in normalized
                    or "replace" in normalized
                    or "placeholder" in normalized
                )

            weak_secrets = {
                "replace-this-payment-webhook-secret",
                "replace-this-with-a-long-random-local-secret",
                "replace-this-whatsapp-app-secret",
                "replace-this-whatsapp-verify-token",
                "SUPER_SECRET_KEY_REPLACE_IN_PROD",
            }
            if self.SECRET_KEY in weak_secrets or is_weak_secret(self.SECRET_KEY):
                raise ValueError("SECRET_KEY must be a strong staging/production secret")
            if self.PAYMENT_WEBHOOK_SECRET in weak_secrets or is_weak_secret(
                self.PAYMENT_WEBHOOK_SECRET
            ):
                raise ValueError(
                    "PAYMENT_WEBHOOK_SECRET must be a strong staging/production secret"
                )
            if self.WHATSAPP_WEBHOOK_APP_SECRET in weak_secrets or is_weak_secret(
                self.WHATSAPP_WEBHOOK_APP_SECRET
            ):
                raise ValueError(
                    "WHATSAPP_WEBHOOK_APP_SECRET must be a strong staging/production secret"
                )
            if self.WHATSAPP_WEBHOOK_VERIFY_TOKEN in weak_secrets or is_weak_secret(
                self.WHATSAPP_WEBHOOK_VERIFY_TOKEN,
                min_length=16,
            ):
                raise ValueError(
                    "WHATSAPP_WEBHOOK_VERIFY_TOKEN must be changed in staging/production"
                )
            if not self.DATABASE_URL and self.POSTGRES_PASSWORD in {"change-me", "password123"}:
                raise ValueError("POSTGRES_PASSWORD must be changed in staging/production")
            if "*" in self.BACKEND_CORS_ORIGINS:
                raise ValueError("Wildcard CORS origins are not allowed in staging/production")
            if self.INITIAL_ADMIN_PASSWORD == "adminpassword" or is_weak_secret(
                self.INITIAL_ADMIN_PASSWORD,
                min_length=12,
            ):
                raise ValueError("INITIAL_ADMIN_PASSWORD must be changed in staging/production")
            if self.ENABLE_SAMPLE_DATA and self.INITIAL_OWNER_PASSWORD == "ownerpassword":
                raise ValueError(
                    "Sample data in staging/production requires non-default seed passwords"
                )
        return self

    model_config = SettingsConfigDict(case_sensitive=True, env_file=(".env", "../.env"))


settings = Settings()
