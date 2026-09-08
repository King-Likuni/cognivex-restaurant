"""Reporting service layer."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.menu.models import MenuItem
from app.orders.enums import OrderStatus, PaymentStatus
from app.orders.models import Order, OrderItem
from app.payments.models import Payment
from app.reports.schemas import DailySalesReport, PaymentMethodSummary, TopMenuItemSummary


def _money(value: Decimal | int | None) -> Decimal:
    return Decimal(value or 0).quantize(Decimal("0.01"))


def get_daily_sales_report(
    db: Session,
    restaurant_id: UUID,
    business_date: date,
    branch_id: UUID | None = None,
) -> DailySalesReport:
    orders_query = db.query(Order).filter(
        Order.restaurant_id == restaurant_id,
        Order.business_date == business_date,
    )
    if branch_id is not None:
        orders_query = orders_query.filter(Order.branch_id == branch_id)

    orders_count = orders_query.count()
    collected_orders = orders_query.filter(
        Order.order_status == OrderStatus.COLLECTED.value
    ).count()
    ready_orders = orders_query.filter(Order.order_status == OrderStatus.READY.value).count()
    uncollected_orders = orders_query.filter(
        Order.order_status == OrderStatus.UNCOLLECTED.value
    ).count()
    cancelled_orders = orders_query.filter(
        Order.order_status == OrderStatus.CANCELLED.value
    ).count()

    revenue_query = db.query(func.coalesce(func.sum(Order.total), 0)).filter(
        Order.restaurant_id == restaurant_id,
        Order.business_date == business_date,
        Order.payment_status == PaymentStatus.PAID.value,
        Order.order_status == OrderStatus.COLLECTED.value,
    )
    if branch_id is not None:
        revenue_query = revenue_query.filter(Order.branch_id == branch_id)
    revenue = _money(revenue_query.scalar())
    average_order_value = (
        _money(revenue / collected_orders) if collected_orders else Decimal("0.00")
    )

    top_items_query = (
        db.query(
            MenuItem.id,
            MenuItem.name,
            func.coalesce(func.sum(OrderItem.quantity), 0).label("quantity"),
            func.coalesce(func.sum(OrderItem.total_price), 0).label("revenue"),
        )
        .join(OrderItem, OrderItem.menu_item_id == MenuItem.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(
            Order.restaurant_id == restaurant_id,
            Order.business_date == business_date,
            Order.payment_status == PaymentStatus.PAID.value,
            Order.order_status == OrderStatus.COLLECTED.value,
        )
    )
    if branch_id is not None:
        top_items_query = top_items_query.filter(Order.branch_id == branch_id)
    top_items = [
        TopMenuItemSummary(
            menu_item_id=row.id,
            name=row.name,
            quantity=int(row.quantity or 0),
            revenue=_money(row.revenue),
        )
        for row in (
            top_items_query.group_by(MenuItem.id, MenuItem.name)
            .order_by(func.sum(OrderItem.quantity).desc(), MenuItem.name)
            .limit(10)
            .all()
        )
    ]

    payment_query = (
        db.query(
            Payment.provider,
            func.count(Payment.id).label("payments"),
            func.coalesce(func.sum(Payment.amount), 0).label("revenue"),
        )
        .join(Order, Order.id == Payment.order_id)
        .filter(
            Payment.restaurant_id == restaurant_id,
            Payment.status == PaymentStatus.PAID.value,
            Order.business_date == business_date,
            Order.order_status == OrderStatus.COLLECTED.value,
        )
    )
    if branch_id is not None:
        payment_query = payment_query.filter(Order.branch_id == branch_id)
    sales_by_payment = [
        PaymentMethodSummary(
            provider=row.provider,
            payments=int(row.payments or 0),
            revenue=_money(row.revenue),
        )
        for row in payment_query.group_by(Payment.provider).order_by(Payment.provider).all()
    ]

    return DailySalesReport(
        restaurant_id=restaurant_id,
        branch_id=branch_id,
        business_date=business_date,
        orders=orders_count,
        collected_orders=collected_orders,
        ready_orders=ready_orders,
        uncollected_orders=uncollected_orders,
        cancelled_orders=cancelled_orders,
        revenue=revenue,
        average_order_value=average_order_value,
        top_items=top_items,
        sales_by_payment=sales_by_payment,
    )
