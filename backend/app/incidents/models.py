"""Platform incident models."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.core.database import Base


class PlatformIncident(Base):
    __tablename__ = "platform_incidents"
    __table_args__ = (
        Index("ix_platform_incidents_status_created_at", "status", "created_at"),
        Index("ix_platform_incidents_source_category", "source", "category"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(
        UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=True, index=True
    )
    source = Column(String, nullable=False)
    category = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    status = Column(String, default="OPEN", nullable=False)
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    fingerprint = Column(String, nullable=True, index=True)
    context = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
