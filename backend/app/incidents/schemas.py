"""Pydantic schemas for platform incident monitoring."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FrontendErrorReport(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    stack: str | None = Field(default=None, max_length=4000)
    component_stack: str | None = Field(default=None, max_length=4000)
    path: str = Field(..., min_length=1, max_length=500)
    url: str | None = Field(default=None, max_length=1000)
    user_email: str | None = Field(default=None, max_length=320)
    user_role: str | None = Field(default=None, max_length=50)


class PlatformIncidentResponse(BaseModel):
    id: UUID
    restaurant_id: UUID | None
    source: str
    category: str
    severity: str
    status: str
    title: str
    message: str
    fingerprint: str | None
    context: dict | None
    created_at: datetime | None
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class PlatformHealthSummary(BaseModel):
    status: str
    database: str
    version: str
    environment: str


class TenantRiskSummary(BaseModel):
    restaurant_id: UUID
    restaurant_name: str
    severity: str
    signals: list[str]


class PlatformIncidentSummary(BaseModel):
    system: PlatformHealthSummary
    open_incidents: int
    critical_incidents: int
    incidents_last_24h: int
    frontend_errors_last_24h: int
    webhook_failures_last_24h: int
    failed_payments_today: int
    pending_payments_today: int
    tenant_risks: list[TenantRiskSummary]
    recent_incidents: list[PlatformIncidentResponse]
