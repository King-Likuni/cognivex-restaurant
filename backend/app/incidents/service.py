"""Service helpers for durable platform incident visibility."""

import hashlib
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.incidents.models import PlatformIncident
from app.incidents.schemas import FrontendErrorReport, PlatformHealthSummary, TenantRiskSummary
from app.orders.enums import PaymentStatus
from app.orders.models import Order
from app.payments.models import Payment
from app.tenants import service as tenant_service

INCIDENT_STATUS_OPEN = "OPEN"
INCIDENT_STATUS_RESOLVED = "RESOLVED"
SEVERITY_INFO = "INFO"
SEVERITY_WARNING = "WARNING"
SEVERITY_ERROR = "ERROR"
SEVERITY_CRITICAL = "CRITICAL"


def utc_now() -> datetime:
    return datetime.now(UTC)


def truncate(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value[:limit]


def build_fingerprint(*parts: object) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_incident(
    db: Session,
    *,
    source: str,
    category: str,
    severity: str,
    title: str,
    message: str,
    restaurant_id: UUID | None = None,
    context: dict | None = None,
    fingerprint: str | None = None,
) -> PlatformIncident:
    if fingerprint:
        recent_duplicate = (
            db.query(PlatformIncident)
            .filter(
                PlatformIncident.fingerprint == fingerprint,
                PlatformIncident.status == INCIDENT_STATUS_OPEN,
                PlatformIncident.created_at >= utc_now() - timedelta(minutes=10),
            )
            .order_by(PlatformIncident.created_at.desc())
            .first()
        )
        if recent_duplicate is not None:
            return recent_duplicate

    incident = PlatformIncident(
        restaurant_id=restaurant_id,
        source=source,
        category=category,
        severity=severity,
        status=INCIDENT_STATUS_OPEN,
        title=truncate(title, 250) or "Platform incident",
        message=truncate(message, 1000) or "No detail provided",
        fingerprint=fingerprint,
        context=context,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


def record_frontend_error(
    db: Session,
    report: FrontendErrorReport,
    *,
    user_agent: str | None,
) -> PlatformIncident:
    return create_incident(
        db,
        source="FRONTEND",
        category="FRONTEND_ERROR",
        severity=SEVERITY_ERROR,
        title="Frontend screen crash",
        message=report.message,
        context={
            "path": report.path,
            "url": report.url,
            "stack": truncate(report.stack, 4000),
            "component_stack": truncate(report.component_stack, 4000),
            "user_agent": truncate(user_agent, 500),
            "user_email": report.user_email,
            "user_role": report.user_role,
        },
        fingerprint=build_fingerprint("FRONTEND_ERROR", report.path, report.message),
    )


def record_payment_webhook_failure(
    db: Session,
    *,
    provider: str,
    reason: str,
    payload: dict | None = None,
    severity: str = SEVERITY_WARNING,
) -> PlatformIncident:
    reference = payload.get("reference") if payload else None
    return create_incident(
        db,
        source="PAYMENTS",
        category="PAYMENT_WEBHOOK",
        severity=severity,
        title="Payment webhook failed",
        message=reason,
        context={
            "provider": provider.upper(),
            "reference": reference,
            "payload_keys": sorted(payload.keys()) if payload else [],
            "status": payload.get("status") if payload else None,
            "amount": payload.get("amount") if payload else None,
            "currency": payload.get("currency") if payload else None,
        },
        fingerprint=build_fingerprint("PAYMENT_WEBHOOK", provider.upper(), reason, reference),
    )


def list_incidents(
    db: Session,
    *,
    status: str | None = None,
    severity: str | None = None,
    source: str | None = None,
    category: str | None = None,
    limit: int = 100,
) -> list[PlatformIncident]:
    query = db.query(PlatformIncident)
    if status:
        query = query.filter(PlatformIncident.status == status.upper())
    if severity:
        query = query.filter(PlatformIncident.severity == severity.upper())
    if source:
        query = query.filter(PlatformIncident.source == source.upper())
    if category:
        query = query.filter(PlatformIncident.category == category.upper())
    return (
        query.order_by(PlatformIncident.created_at.desc(), PlatformIncident.id.desc())
        .limit(limit)
        .all()
    )


def resolve_incident(db: Session, incident_id: UUID) -> PlatformIncident | None:
    incident = db.query(PlatformIncident).filter(PlatformIncident.id == incident_id).first()
    if incident is None:
        return None
    incident.status = INCIDENT_STATUS_RESOLVED
    incident.resolved_at = utc_now()
    db.commit()
    db.refresh(incident)
    return incident


def count_incidents(
    db: Session,
    *,
    created_since: datetime | None = None,
    category: str | None = None,
    status: str | None = None,
    severity: str | None = None,
) -> int:
    query = db.query(PlatformIncident)
    if created_since is not None:
        query = query.filter(PlatformIncident.created_at >= created_since)
    if category:
        query = query.filter(PlatformIncident.category == category)
    if status:
        query = query.filter(PlatformIncident.status == status)
    if severity:
        query = query.filter(PlatformIncident.severity == severity)
    return query.count()


def system_health(db: Session) -> PlatformHealthSummary:
    db.execute(text("SELECT 1"))
    return PlatformHealthSummary(
        status="ready",
        database="ok",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
    )


def tenant_risk_summaries(db: Session) -> list[TenantRiskSummary]:
    risks: list[TenantRiskSummary] = []
    for restaurant in tenant_service.list_platform_restaurants(db):
        signals: list[str] = []
        severity = SEVERITY_WARNING
        if restaurant.order_access_blocked:
            signals.append("Order access is blocked")
            severity = SEVERITY_CRITICAL
        if restaurant.failed_payment_count:
            signals.append(f"{restaurant.failed_payment_count} failed payments today")
        if restaurant.pending_payment_count:
            signals.append(f"{restaurant.pending_payment_count} pending payments today")
        if restaurant.critical_stock_alert_count:
            signals.append(f"{restaurant.critical_stock_alert_count} critical stock alerts")
            severity = SEVERITY_CRITICAL
        if restaurant.low_stock_alert_count:
            signals.append(f"{restaurant.low_stock_alert_count} low stock alerts")
        if signals:
            risks.append(
                TenantRiskSummary(
                    restaurant_id=restaurant.id,
                    restaurant_name=restaurant.name,
                    severity=severity,
                    signals=signals,
                )
            )
    return risks[:20]


def failed_payments_today(db: Session) -> int:
    return (
        db.query(Payment)
        .join(Order, Order.id == Payment.order_id)
        .filter(
            Order.business_date == date.today(),
            Payment.status.in_([PaymentStatus.FAILED.value, PaymentStatus.EXPIRED.value]),
        )
        .count()
    )


def pending_payments_today(db: Session) -> int:
    return (
        db.query(func.count(Order.id))
        .filter(
            Order.business_date == date.today(),
            Order.payment_status == PaymentStatus.PENDING.value,
        )
        .scalar()
        or 0
    )


def incident_summary(db: Session) -> dict:
    since = utc_now() - timedelta(hours=24)
    return {
        "system": system_health(db),
        "open_incidents": count_incidents(db, status=INCIDENT_STATUS_OPEN),
        "critical_incidents": count_incidents(
            db,
            status=INCIDENT_STATUS_OPEN,
            severity=SEVERITY_CRITICAL,
        ),
        "incidents_last_24h": count_incidents(db, created_since=since),
        "frontend_errors_last_24h": count_incidents(
            db,
            created_since=since,
            category="FRONTEND_ERROR",
        ),
        "webhook_failures_last_24h": count_incidents(
            db,
            created_since=since,
            category="PAYMENT_WEBHOOK",
        ),
        "failed_payments_today": failed_payments_today(db),
        "pending_payments_today": pending_payments_today(db),
        "tenant_risks": tenant_risk_summaries(db),
        "recent_incidents": list_incidents(db, limit=10),
    }
