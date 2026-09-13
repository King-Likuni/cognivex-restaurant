"""Reporting service layer."""

import csv
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal
from io import StringIO
from uuid import UUID

from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.auth.models import User
from app.inventory import service as inventory_service
from app.menu.models import MenuItem
from app.orders.enums import OrderStatus, PaymentStatus
from app.orders.models import Order, OrderItem, OrderStatusHistory
from app.payments.models import Payment
from app.reports.schemas import (
    CashierActivitySummary,
    ChannelSummary,
    DailySalesReport,
    HourlySalesSummary,
    PaymentMethodSummary,
    TopMenuItemSummary,
)


def _money(value: Decimal | int | None) -> Decimal:
    return Decimal(value or 0).quantize(Decimal("0.01"))


def _user_name(first_name: str | None, last_name: str | None, email: str | None) -> str:
    full_name = " ".join(part for part in [first_name, last_name] if part)
    return full_name or email or "System"


def _csv_text(headers: list[str], rows: list[list[object]]) -> str:
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


def _json_cell(value: object) -> str:
    return json.dumps(value, default=str, sort_keys=True, separators=(",", ":"))


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

    collected_paid_filter = and_(
        Order.payment_status == PaymentStatus.PAID.value,
        Order.order_status == OrderStatus.COLLECTED.value,
    )
    channel_rows = db.query(
        Order.channel,
        func.count(Order.id).label("orders"),
        func.coalesce(
            func.sum(case((collected_paid_filter, Order.total), else_=0)),
            0,
        ).label("revenue"),
    ).filter(
        Order.restaurant_id == restaurant_id,
        Order.business_date == business_date,
    )
    if branch_id is not None:
        channel_rows = channel_rows.filter(Order.branch_id == branch_id)
    sales_by_channel = [
        ChannelSummary(
            channel=row.channel,
            orders=int(row.orders or 0),
            revenue=_money(row.revenue),
        )
        for row in channel_rows.group_by(Order.channel).order_by(Order.channel).all()
    ]

    hour_bucket = func.extract("hour", Order.collected_at)
    hourly_query = db.query(
        hour_bucket.label("hour"),
        func.count(Order.id).label("orders"),
        func.coalesce(func.sum(Order.total), 0).label("revenue"),
    ).filter(
        Order.restaurant_id == restaurant_id,
        Order.business_date == business_date,
        Order.payment_status == PaymentStatus.PAID.value,
        Order.order_status == OrderStatus.COLLECTED.value,
        Order.collected_at.isnot(None),
    )
    if branch_id is not None:
        hourly_query = hourly_query.filter(Order.branch_id == branch_id)
    hourly_sales = [
        HourlySalesSummary(
            hour=int(row.hour or 0),
            orders=int(row.orders or 0),
            revenue=_money(row.revenue),
        )
        for row in hourly_query.group_by(hour_bucket).order_by(hour_bucket).all()
    ]

    activity: dict[UUID | None, dict[str, object]] = defaultdict(
        lambda: {
            "name": "System",
            "email": None,
            "orders_created": 0,
            "payments_confirmed": 0,
            "orders_collected": 0,
            "revenue_collected": Decimal("0.00"),
        }
    )

    def ensure_activity_row(
        user_id: UUID | None,
        first_name: str | None,
        last_name: str | None,
        email: str | None,
    ) -> dict[str, object]:
        row = activity[user_id]
        row["name"] = _user_name(first_name, last_name, email)
        row["email"] = email
        return row

    created_query = (
        db.query(
            Order.created_by.label("user_id"),
            User.first_name,
            User.last_name,
            User.email,
            func.count(Order.id).label("orders_created"),
        )
        .outerjoin(User, User.id == Order.created_by)
        .filter(Order.restaurant_id == restaurant_id, Order.business_date == business_date)
    )
    if branch_id is not None:
        created_query = created_query.filter(Order.branch_id == branch_id)
    for row in (
        created_query.group_by(Order.created_by, User.first_name, User.last_name, User.email)
        .order_by(User.email)
        .all()
    ):
        activity_row = ensure_activity_row(row.user_id, row.first_name, row.last_name, row.email)
        activity_row["orders_created"] = int(row.orders_created or 0)

    payment_confirmed_query = (
        db.query(
            AuditLog.user_id,
            User.first_name,
            User.last_name,
            User.email,
            func.count(AuditLog.id).label("payments_confirmed"),
        )
        .join(Order, and_(AuditLog.entity_type == "order", AuditLog.entity_id == Order.id))
        .outerjoin(User, User.id == AuditLog.user_id)
        .filter(
            AuditLog.restaurant_id == restaurant_id,
            AuditLog.action.in_(["CASH_PAYMENT_CONFIRMED", "MOBILE_TRANSFER_PAYMENT_CONFIRMED"]),
            Order.business_date == business_date,
        )
    )
    if branch_id is not None:
        payment_confirmed_query = payment_confirmed_query.filter(Order.branch_id == branch_id)
    for row in (
        payment_confirmed_query.group_by(
            AuditLog.user_id,
            User.first_name,
            User.last_name,
            User.email,
        )
        .order_by(User.email)
        .all()
    ):
        activity_row = ensure_activity_row(row.user_id, row.first_name, row.last_name, row.email)
        activity_row["payments_confirmed"] = int(row.payments_confirmed or 0)

    collected_query = (
        db.query(
            OrderStatusHistory.changed_by.label("user_id"),
            User.first_name,
            User.last_name,
            User.email,
            func.count(Order.id).label("orders_collected"),
            func.coalesce(func.sum(Order.total), 0).label("revenue_collected"),
        )
        .join(Order, Order.id == OrderStatusHistory.order_id)
        .outerjoin(User, User.id == OrderStatusHistory.changed_by)
        .filter(
            Order.restaurant_id == restaurant_id,
            Order.business_date == business_date,
            Order.payment_status == PaymentStatus.PAID.value,
            Order.order_status == OrderStatus.COLLECTED.value,
            OrderStatusHistory.new_status == OrderStatus.COLLECTED.value,
        )
    )
    if branch_id is not None:
        collected_query = collected_query.filter(Order.branch_id == branch_id)
    for row in (
        collected_query.group_by(
            OrderStatusHistory.changed_by,
            User.first_name,
            User.last_name,
            User.email,
        )
        .order_by(User.email)
        .all()
    ):
        activity_row = ensure_activity_row(row.user_id, row.first_name, row.last_name, row.email)
        activity_row["orders_collected"] = int(row.orders_collected or 0)
        activity_row["revenue_collected"] = _money(row.revenue_collected)

    cashier_activity = [
        CashierActivitySummary(
            user_id=user_id,
            name=str(row["name"]),
            email=row["email"] if isinstance(row["email"], str) else None,
            orders_created=int(row["orders_created"]),
            payments_confirmed=int(row["payments_confirmed"]),
            orders_collected=int(row["orders_collected"]),
            revenue_collected=_money(row["revenue_collected"]),
        )
        for user_id, row in activity.items()
    ]
    cashier_activity.sort(
        key=lambda row: (
            -row.revenue_collected,
            -row.orders_collected,
            row.name.lower(),
        )
    )

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
        sales_by_channel=sales_by_channel,
        hourly_sales=hourly_sales,
        cashier_activity=cashier_activity,
    )


def export_daily_sales_csv(report: DailySalesReport) -> str:
    rows: list[list[object]] = [
        ["business_date", report.business_date],
        ["restaurant_id", report.restaurant_id],
        ["branch_id", report.branch_id or ""],
        ["orders", report.orders],
        ["collected_orders", report.collected_orders],
        ["ready_orders", report.ready_orders],
        ["uncollected_orders", report.uncollected_orders],
        ["cancelled_orders", report.cancelled_orders],
        ["revenue", report.revenue],
        ["average_order_value", report.average_order_value],
        [],
        ["sold_products"],
        ["menu_item_id", "name", "quantity", "revenue"],
    ]
    rows.extend(
        [item.menu_item_id, item.name, item.quantity, item.revenue] for item in report.top_items
    )
    rows.extend(
        [
            [],
            ["payment_methods"],
            ["provider", "payments", "revenue"],
        ]
    )
    rows.extend(
        [payment.provider, payment.payments, payment.revenue] for payment in report.sales_by_payment
    )
    rows.extend(
        [
            [],
            ["channels"],
            ["channel", "orders", "revenue"],
        ]
    )
    rows.extend(
        [channel.channel, channel.orders, channel.revenue] for channel in report.sales_by_channel
    )
    rows.extend(
        [
            [],
            ["cashier_activity"],
            [
                "user_id",
                "name",
                "email",
                "orders_created",
                "payments_confirmed",
                "orders_collected",
                "revenue_collected",
            ],
        ]
    )
    rows.extend(
        [
            cashier.user_id or "",
            cashier.name,
            cashier.email or "",
            cashier.orders_created,
            cashier.payments_confirmed,
            cashier.orders_collected,
            cashier.revenue_collected,
        ]
        for cashier in report.cashier_activity
    )
    return _csv_text(
        ["section", "value_1", "value_2", "value_3", "value_4", "value_5", "value_6"], rows
    )


def export_orders_csv(
    db: Session,
    restaurant_id: UUID,
    business_date: date,
    branch_id: UUID | None = None,
) -> str:
    query = (
        db.query(Order, User.email)
        .outerjoin(User, User.id == Order.created_by)
        .filter(Order.restaurant_id == restaurant_id, Order.business_date == business_date)
    )
    if branch_id is not None:
        query = query.filter(Order.branch_id == branch_id)
    rows = [
        [
            order.business_date,
            order.branch_id,
            order.display_number,
            order.channel,
            order.order_status,
            order.payment_status,
            order.payment_provider or "",
            order.total,
            order.currency,
            creator_email or "",
            order.created_at or "",
            order.ready_at or "",
            order.collected_at or "",
        ]
        for order, creator_email in query.order_by(Order.created_at, Order.daily_sequence).all()
    ]
    return _csv_text(
        [
            "business_date",
            "branch_id",
            "display_number",
            "channel",
            "order_status",
            "payment_status",
            "payment_provider",
            "total",
            "currency",
            "created_by",
            "created_at",
            "ready_at",
            "collected_at",
        ],
        rows,
    )


def export_payments_csv(
    db: Session,
    restaurant_id: UUID,
    business_date: date,
    branch_id: UUID | None = None,
) -> str:
    query = (
        db.query(Payment, Order)
        .join(Order, Order.id == Payment.order_id)
        .filter(Payment.restaurant_id == restaurant_id, Order.business_date == business_date)
    )
    if branch_id is not None:
        query = query.filter(Order.branch_id == branch_id)
    rows = [
        [
            order.business_date,
            order.branch_id,
            order.display_number,
            payment.provider,
            payment.reference,
            payment.status,
            payment.amount,
            payment.currency,
            payment.provider_transaction_id or "",
            payment.created_at or "",
            payment.completed_at or "",
        ]
        for payment, order in query.order_by(Order.created_at, Order.daily_sequence).all()
    ]
    return _csv_text(
        [
            "business_date",
            "branch_id",
            "display_number",
            "provider",
            "reference",
            "status",
            "amount",
            "currency",
            "provider_transaction_id",
            "created_at",
            "completed_at",
        ],
        rows,
    )


def export_audit_logs_csv(
    db: Session,
    restaurant_id: UUID,
    *,
    branch_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> str:
    from app.audit.service import list_audit_logs

    rows = [
        [
            log.created_at or "",
            log.action,
            log.entity_type,
            log.entity_id,
            user.email if user else "",
            _json_cell(log.old_values),
            _json_cell(log.new_values),
        ]
        for log, user in list_audit_logs(
            db,
            restaurant_id,
            branch_id=branch_id,
            date_from=date_from,
            date_to=date_to,
            limit=1000,
        )
    ]
    return _csv_text(
        [
            "created_at",
            "action",
            "entity_type",
            "entity_id",
            "user_email",
            "old_values",
            "new_values",
        ],
        rows,
    )


def export_inventory_balances_csv(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
) -> str:
    rows = [
        [ingredient.id, ingredient.name, ingredient.unit, quantity]
        for ingredient, quantity in inventory_service.list_stock_balances(
            db, restaurant_id, branch_id
        )
    ]
    return _csv_text(["ingredient_id", "name", "unit", "quantity_on_hand"], rows)
