import pytest

from app.orders.enums import OrderStatus
from app.orders.state_machine import can_transition_order, validate_order_transition


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (OrderStatus.DRAFT, OrderStatus.PENDING_PAYMENT),
        (OrderStatus.PENDING_PAYMENT, OrderStatus.CONFIRMED),
        (OrderStatus.CONFIRMED, OrderStatus.QUEUED),
        (OrderStatus.QUEUED, OrderStatus.PREPARING),
        (OrderStatus.PREPARING, OrderStatus.READY),
        (OrderStatus.READY, OrderStatus.COLLECTED),
        (OrderStatus.READY, OrderStatus.UNCOLLECTED),
    ],
)
def test_allowed_order_transitions(current, target):
    assert can_transition_order(current, target)
    validate_order_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (OrderStatus.PENDING_PAYMENT, OrderStatus.PREPARING),
        (OrderStatus.READY, OrderStatus.PREPARING),
        (OrderStatus.COLLECTED, OrderStatus.CANCELLED),
        (OrderStatus.CANCELLED, OrderStatus.CONFIRMED),
    ],
)
def test_invalid_order_transitions_raise(current, target):
    assert not can_transition_order(current, target)
    with pytest.raises(ValueError):
        validate_order_transition(current, target)
