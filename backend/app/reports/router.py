"""Report API routes."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.database import get_db
from app.core.dependencies import ensure_restaurant_access, require_manager
from app.reports import service
from app.reports.schemas import DailySalesReport

router = APIRouter(prefix="/restaurants/{restaurant_id}/reports", tags=["Reports"])


@router.get("/daily-sales", response_model=DailySalesReport)
def get_daily_sales(
    restaurant_id: UUID,
    business_date: date = Query(...),
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    ensure_restaurant_access(current_user, restaurant_id)
    return service.get_daily_sales_report(db, restaurant_id, business_date, branch_id)
