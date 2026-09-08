from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from threading import Barrier

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.auth.models import User
from app.menu.schemas import MenuCategoryCreate, MenuItemCreate
from app.menu.service import create_category, create_item
from app.orders import service as order_service
from app.orders.schemas import CashierOrderCreate, OrderLineCreate

pytestmark = pytest.mark.integration


def test_daily_order_sequence_is_safe_under_concurrent_creation(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    seeded_restaurant: dict[str, object],
):
    restaurant = seeded_restaurant["restaurant"]
    branch = seeded_restaurant["branch"]
    owner = seeded_restaurant["owner"]

    category = create_category(
        db_session,
        restaurant.id,
        MenuCategoryCreate(name="Concurrent Numbering", display_order=1),
    )
    item = create_item(
        db_session,
        restaurant.id,
        MenuItemCreate(
            category_id=category.id,
            name="Concurrent Meal",
            description=None,
            price="10.00",
            image_url=None,
            is_available=True,
        ),
    )
    db_session.commit()

    payload = CashierOrderCreate(
        customer_id=None,
        items=[OrderLineCreate(menu_item_id=item.id, quantity=1)],
        payment_method="CASH",
    )
    business_date = date(2026, 9, 4)
    monkeypatch.setattr(order_service, "get_business_date", lambda: business_date)

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db_session.get_bind(),
    )
    start_together = Barrier(5)

    def create_order() -> int:
        worker_session = TestingSessionLocal()
        try:
            worker_owner = worker_session.query(User).filter(User.id == owner.id).one()
            start_together.wait(timeout=10)
            order = order_service.create_cashier_order(
                worker_session,
                restaurant.id,
                branch.id,
                payload,
                worker_owner,
            )
            return order.daily_sequence
        finally:
            worker_session.close()

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(create_order) for _ in range(5)]
        sequences = sorted(future.result() for future in as_completed(futures))

    assert sequences == [1, 2, 3, 4, 5]
