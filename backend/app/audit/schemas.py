"""Pydantic schemas for audit history."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: UUID
    restaurant_id: UUID | None
    user_id: UUID | None
    user_email: str | None
    user_name: str | None
    action: str
    entity_type: str
    entity_id: UUID
    old_values: dict | None
    new_values: dict | None
    created_at: datetime | None

    model_config = {"from_attributes": True}
