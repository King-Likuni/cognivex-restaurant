"""Platform incident API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin, require_platform_reader
from app.incidents import service
from app.incidents.schemas import (
    FrontendErrorReport,
    PlatformIncidentResponse,
    PlatformIncidentSummary,
)

router = APIRouter(prefix="/platform/incidents", tags=["Platform Incidents"])


@router.post(
    "/frontend-errors",
    response_model=PlatformIncidentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def report_frontend_error(
    report: FrontendErrorReport,
    user_agent: Annotated[str | None, Header(alias="User-Agent")] = None,
    db: Session = Depends(get_db),
):
    """Record a frontend crash report without requiring an active session."""
    return service.record_frontend_error(db, report, user_agent=user_agent)


@router.get("/summary", response_model=PlatformIncidentSummary)
def get_incident_summary(
    db: Session = Depends(get_db),
    _current_user=Depends(require_platform_reader),
):
    """Return platform health, risk, and recent incident summary."""
    return service.incident_summary(db)


@router.get("/", response_model=list[PlatformIncidentResponse])
def list_incidents(
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = None,
    source: str | None = None,
    category: str | None = None,
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    _current_user=Depends(require_platform_reader),
):
    """List recent platform incidents for platform operators."""
    return service.list_incidents(
        db,
        status=status_filter,
        severity=severity,
        source=source,
        category=category,
        limit=limit,
    )


@router.patch("/{incident_id}/resolve", response_model=PlatformIncidentResponse)
def resolve_incident(
    incident_id: UUID,
    db: Session = Depends(get_db),
    _current_user=Depends(require_admin),
):
    """Resolve an incident. Platform admins only."""
    incident = service.resolve_incident(db, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident
