"""Order service layer."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, text
from sqlalchemy.orm import Session, selectinload

from app.audit.models import AuditLog
from app.auth.models import User
from app.customers.models import Customer
from app.menu.models import MenuItem
from app.orders.enums import OrderChannel, OrderStatus, PaymentStatus
from app.orders.models import Order, OrderItem, OrderStatusHistory
from app.orders.numbering import (
    format_display_number,
    generate_payment_reference,
    next_daily_sequence,
)
from app.orders.schemas import CashierOrderCreate, PublicCustomerOrderCreate
from app.orders.state_machine import validate_order_transition
from app.realtime.events import publish_order_event
from app.tenants.models import Branch, Restaurant, RestaurantSettings


def get_business_date() -> date:
    return date.today()


def get_next_daily_sequence(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    business_date: date,
) -> int:
    lock_key = f"orders:{restaurant_id}:{branch_id}:{business_date.isoformat()}"
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
        {"lock_key": lock_key},
    )
    current_max = (
        db.query(func.max(Order.daily_sequence))
        .filter(
            Order.restaurant_id == restaurant_id,
            Order.branch_id == branch_id,
            Order.business_date == business_date,
        )
        .scalar()
    )
    return next_daily_sequence(current_max)


def get_next_status_history_sequence(db: Session, order: Order) -> int:
    in_memory_max = max(
        (history.sequence or 0 for history in order.status_history),
        default=0,
    )
    persisted_max = 0
    if order.id is not None:
        persisted_max = (
            db.query(func.max(OrderStatusHistory.sequence))
            .filter(OrderStatusHistory.order_id == order.id)
            .scalar()
            or 0
        )
    return max(in_memory_max, persisted_max) + 1


def get_active_restaurant_and_branch(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
) -> tuple[Restaurant, Branch]:
    restaurant = (
        db.query(Restaurant)
        .filter(Restaurant.id == restaurant_id, Restaurant.is_active.is_(True))
        .first()
    )
    if restaurant is None:
        raise ValueError("Restaurant not found")

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
        raise ValueError("Branch not found")
    return restaurant, branch


def create_order_items(
    db: Session,
    restaurant_id: UUID,
    items,
) -> tuple[Decimal, list[OrderItem]]:
    menu_item_ids = [line.menu_item_id for line in items]
    menu_items = (
        db.query(MenuItem)
        .filter(
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.id.in_(menu_item_ids),
        )
        .all()
    )
    menu_by_id = {item.id: item for item in menu_items}
    if len(menu_by_id) != len(set(menu_item_ids)):
        raise ValueError("One or more menu items were not found")

    subtotal = Decimal("0.00")
    order_items: list[OrderItem] = []
    for line in items:
        menu_item = menu_by_id[line.menu_item_id]
        if not menu_item.is_available:
            raise ValueError(f"Menu item '{menu_item.name}' is sold out")
        line_total = Decimal(menu_item.price) * line.quantity
        subtotal += line_total
        order_items.append(
            OrderItem(
                menu_item_id=menu_item.id,
                quantity=line.quantity,
                unit_price=menu_item.price,
                total_price=line_total,
            )
        )
    return subtotal, order_items


def create_pending_order(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    *,
    items,
    channel: str,
    customer_id: UUID | None,
    created_by: User | None,
) -> Order:
    restaurant, branch = get_active_restaurant_and_branch(db, restaurant_id, branch_id)
    subtotal, order_items = create_order_items(db, restaurant_id, items)

    settings = (
        db.query(RestaurantSettings)
        .filter(RestaurantSettings.restaurant_id == restaurant_id)
        .first()
    )
    currency = settings.currency if settings else "BWP"
    business_date = get_business_date()
    daily_sequence = get_next_daily_sequence(db, restaurant_id, branch_id, business_date)

    order = Order(
        restaurant_id=restaurant_id,
        branch_id=branch_id,
        business_date=business_date,
        daily_sequence=daily_sequence,
        display_number=format_display_number(daily_sequence),
        payment_reference=generate_payment_reference(
            restaurant_code=restaurant.code,
            branch_code=branch.code,
            business_date=business_date,
            daily_sequence=daily_sequence,
        ),
        customer_id=customer_id,
        channel=channel,
        subtotal=subtotal,
        total=subtotal,
        currency=currency,
        payment_status=PaymentStatus.PENDING.value,
        order_status=OrderStatus.PENDING_PAYMENT.value,
        created_by=created_by.id if created_by else None,
    )
    order.items = order_items
    order.status_history.append(
        OrderStatusHistory(
            sequence=1,
            previous_status=None,
            new_status=OrderStatus.PENDING_PAYMENT.value,
            changed_by=created_by.id if created_by else None,
        )
    )

    db.add(order)
    db.commit()
    db.refresh(order)
    publish_order_event(order, "ORDER_CREATED")
    return order


def get_or_create_customer(
    db: Session,
    restaurant_id: UUID,
    *,
    phone_number: str,
    name: str | None = None,
) -> Customer:
    normalized_phone = phone_number.strip()
    normalized_name = name.strip() if name else None
    if not normalized_phone:
        raise ValueError("Customer phone number is required")
    customer = (
        db.query(Customer)
        .filter(Customer.restaurant_id == restaurant_id, Customer.phone_number == normalized_phone)
        .first()
    )
    if customer is None:
        customer = Customer(
            restaurant_id=restaurant_id,
            phone_number=normalized_phone,
            name=normalized_name,
            total_orders=0,
        )
        db.add(customer)
        db.flush()
    elif normalized_name and not customer.name:
        customer.name = normalized_name
    return customer


def create_cashier_order(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    data: CashierOrderCreate,
    created_by: User,
) -> Order:
    get_active_restaurant_and_branch(db, restaurant_id, branch_id)
    if data.customer_id is not None:
        customer = (
            db.query(Customer)
            .filter(Customer.id == data.customer_id, Customer.restaurant_id == restaurant_id)
            .first()
        )
        if customer is None:
            raise ValueError("Customer not found")

    if data.payment_method.upper() != "CASH":
        raise ValueError("Only CASH cashier payments are implemented in this slice")

    return create_pending_order(
        db,
        restaurant_id=restaurant_id,
        branch_id=branch_id,
        items=data.items,
        customer_id=data.customer_id,
        channel=OrderChannel.CASHIER.value,
        created_by=created_by,
    )


def create_customer_order(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    data: PublicCustomerOrderCreate,
) -> Order:
    get_active_restaurant_and_branch(db, restaurant_id, branch_id)
    customer = get_or_create_customer(
        db,
        restaurant_id,
        phone_number=data.customer_phone_number,
        name=data.customer_name,
    )
    customer.total_orders = (customer.total_orders or 0) + 1

    return create_pending_order(
        db,
        restaurant_id=restaurant_id,
        branch_id=branch_id,
        items=data.items,
        customer_id=customer.id,
        channel=data.channel,
        created_by=None,
    )


def queue_customer_order_for_preparation(db: Session, order: Order) -> Order:
    if order.order_status != OrderStatus.PENDING_PAYMENT.value:
        return order
    transition_order(db, order, OrderStatus.CONFIRMED, None, commit=False)
    return transition_order(db, order, OrderStatus.QUEUED, None)


def get_order(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    order_id: UUID,
) -> Order | None:
    return (
        db.query(Order)
        .options(selectinload(Order.payment))
        .filter(
            Order.id == order_id,
            Order.restaurant_id == restaurant_id,
            Order.branch_id == branch_id,
        )
        .first()
    )


def list_branch_orders(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    *,
    business_date: date | None = None,
    status: str | None = None,
) -> list[Order]:
    query = (
        db.query(Order)
        .options(selectinload(Order.payment))
        .filter(
            Order.restaurant_id == restaurant_id,
            Order.branch_id == branch_id,
        )
    )
    if business_date is not None:
        query = query.filter(Order.business_date == business_date)
    if status is not None:
        query = query.filter(Order.order_status == status)
    return query.order_by(Order.created_at, Order.daily_sequence).all()


def transition_order(
    db: Session,
    order: Order,
    target_status: OrderStatus | str,
    changed_by: User | None = None,
    *,
    commit: bool = True,
) -> Order:
    target = OrderStatus(target_status)
    previous_status = order.order_status
    validate_order_transition(previous_status, target.value)

    now = datetime.now(UTC)
    order.order_status = target.value
    if target == OrderStatus.CONFIRMED:
        order.confirmed_at = now
    elif target == OrderStatus.PREPARING:
        order.preparing_at = now
    elif target == OrderStatus.READY:
        order.ready_at = now
    elif target == OrderStatus.COLLECTED:
        order.collected_at = now

    order.status_history.append(
        OrderStatusHistory(
            sequence=get_next_status_history_sequence(db, order),
            previous_status=previous_status,
            new_status=target.value,
            changed_by=changed_by.id if changed_by else None,
        )
    )

    if commit:
        db.commit()
        db.refresh(order)
        publish_order_event(order, "ORDER_STATUS_CHANGED")
    return order


def collect_order(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    order_id: UUID,
    changed_by: User,
) -> Order:
    order = get_order(db, restaurant_id, branch_id, order_id)
    if order is None:
        raise ValueError("Order not found")
    if order.payment_status != PaymentStatus.PAID.value:
        raise ValueError("Only paid orders can be collected")

    from app.inventory.service import consume_order_stock

    consume_order_stock(db, order, changed_by)
    previous_status = order.order_status
    transition_order(db, order, OrderStatus.COLLECTED, changed_by, commit=False)
    if order.customer_id is not None:
        customer = (
            db.query(Customer)
            .filter(Customer.id == order.customer_id, Customer.restaurant_id == restaurant_id)
            .first()
        )
        if customer is not None:
            customer.completed_orders = (customer.completed_orders or 0) + 1

    db.add(
        AuditLog(
            restaurant_id=restaurant_id,
            user_id=changed_by.id,
            action="ORDER_COLLECTED",
            entity_type="order",
            entity_id=order.id,
            old_values={"order_status": previous_status},
            new_values={"order_status": OrderStatus.COLLECTED.value},
        )
    )
    db.commit()
    db.refresh(order)
    publish_order_event(order, "ORDER_COLLECTED")
    return order


def cancel_order(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    order_id: UUID,
    changed_by: User,
) -> Order:
    order = get_order(db, restaurant_id, branch_id, order_id)
    if order is None:
        raise ValueError("Order not found")
    if order.payment_status == PaymentStatus.PAID.value:
        raise ValueError("Paid orders require a refund workflow before cancellation")

    previous_status = order.order_status
    transition_order(db, order, OrderStatus.CANCELLED, changed_by, commit=False)
    db.add(
        AuditLog(
            restaurant_id=restaurant_id,
            user_id=changed_by.id,
            action="ORDER_CANCELLED",
            entity_type="order",
            entity_id=order.id,
            old_values={"order_status": previous_status},
            new_values={"order_status": OrderStatus.CANCELLED.value},
        )
    )
    db.commit()
    db.refresh(order)
    publish_order_event(order, "ORDER_CANCELLED")
    return order


def mark_uncollected(
    db: Session,
    restaurant_id: UUID,
    branch_id: UUID,
    order_id: UUID,
    changed_by: User,
) -> Order:
    order = get_order(db, restaurant_id, branch_id, order_id)
    if order is None:
        raise ValueError("Order not found")

    previous_status = order.order_status
    transition_order(db, order, OrderStatus.UNCOLLECTED, changed_by, commit=False)
    if order.customer_id is not None:
        customer = (
            db.query(Customer)
            .filter(Customer.id == order.customer_id, Customer.restaurant_id == restaurant_id)
            .first()
        )
        if customer is not None:
            customer.uncollected_orders = (customer.uncollected_orders or 0) + 1

    db.add(
        AuditLog(
            restaurant_id=restaurant_id,
            user_id=changed_by.id,
            action="ORDER_MARKED_UNCOLLECTED",
            entity_type="order",
            entity_id=order.id,
            old_values={"order_status": previous_status},
            new_values={"order_status": OrderStatus.UNCOLLECTED.value},
        )
    )
    db.commit()
    db.refresh(order)
    publish_order_event(order, "ORDER_UNCOLLECTED")
    return order
