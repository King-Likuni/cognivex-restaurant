"""Report API routes."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.database import get_db
from app.core.dependencies import RoleChecker, ensure_restaurant_access, require_manager
from app.orders import service as order_service
from app.reports import service
from app.reports.schemas import DailySalesReport
from app.tenants.models import Branch

router = APIRouter(prefix="/restaurants/{restaurant_id}/reports", tags=["Reports"])
require_report_reader = RoleChecker(["OWNER", "MANAGER", "CASHIER"])


def csv_response(filename: str, content: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def ensure_report_access(
    db: Session,
    current_user: User,
    restaurant_id: UUID,
    branch_id: UUID | None,
) -> None:
    ensure_restaurant_access(current_user, restaurant_id)
    role_name = current_user.role.name if current_user.role else None
    if role_name in {"OWNER", "MANAGER"}:
        return
    if role_name != "CASHIER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view reports",
        )
    if branch_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cashier reports require a branch",
        )
    branch = (
        db.query(Branch)
        .filter(
            Branch.id == branch_id,
            Branch.restaurant_id == restaurant_id,
            Branch.is_active.is_(True),
        )
        .first()
    )
    if branch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    if branch_id not in {assigned_branch.id for assigned_branch in current_user.branches}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this branch",
        )


@router.get("/daily-sales", response_model=DailySalesReport)
def get_daily_sales(
    restaurant_id: UUID,
    business_date: date | None = Query(default=None),
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_report_reader),
):
    ensure_report_access(db, current_user, restaurant_id, branch_id)
    return service.get_daily_sales_report(
        db,
        restaurant_id,
        business_date or order_service.get_business_date(),
        branch_id,
    )


@router.get("/daily-sales.csv")
def export_daily_sales(
    restaurant_id: UUID,
    business_date: date | None = Query(default=None),
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_report_reader),
):
    ensure_report_access(db, current_user, restaurant_id, branch_id)
    export_date = business_date or order_service.get_business_date()
    report = service.get_daily_sales_report(db, restaurant_id, export_date, branch_id)
    return csv_response(
        f"cognivex-daily-sales-{export_date.isoformat()}.csv",
        service.export_daily_sales_csv(report),
    )


@router.get("/exports/orders.csv")
def export_orders(
    restaurant_id: UUID,
    business_date: date | None = Query(default=None),
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_report_reader),
):
    ensure_report_access(db, current_user, restaurant_id, branch_id)
    export_date = business_date or order_service.get_business_date()
    return csv_response(
        f"cognivex-orders-{export_date.isoformat()}.csv",
        service.export_orders_csv(db, restaurant_id, export_date, branch_id),
    )


@router.get("/exports/payments.csv")
def export_payments(
    restaurant_id: UUID,
    business_date: date | None = Query(default=None),
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_report_reader),
):
    ensure_report_access(db, current_user, restaurant_id, branch_id)
    export_date = business_date or order_service.get_business_date()
    return csv_response(
        f"cognivex-payments-{export_date.isoformat()}.csv",
        service.export_payments_csv(db, restaurant_id, export_date, branch_id),
    )


@router.get("/exports/audit-logs.csv")
def export_audit_logs(
    restaurant_id: UUID,
    branch_id: UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    ensure_restaurant_access(current_user, restaurant_id)
    return csv_response(
        "cognivex-audit-logs.csv",
        service.export_audit_logs_csv(
            db,
            restaurant_id,
            branch_id=branch_id,
            date_from=date_from,
            date_to=date_to,
        ),
    )


@router.get("/exports/inventory-balances.csv")
def export_inventory_balances(
    restaurant_id: UUID,
    branch_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_report_reader),
):
    ensure_report_access(db, current_user, restaurant_id, branch_id)
    return csv_response(
        "cognivex-inventory-balances.csv",
        service.export_inventory_balances_csv(db, restaurant_id, branch_id),
    )
