"""In-process realtime event broadcaster.

This keeps the domain services independent from WebSocket connection details.
The implementation can be swapped for Redis pub/sub when the API runs on
multiple processes or hosts.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from uuid import UUID

from app.orders.models import Order

Channel = str


@dataclass(frozen=True, eq=False)
class Subscriber:
    channel: Channel
    queue: asyncio.Queue[dict[str, str]]
    loop: asyncio.AbstractEventLoop


class RealtimeEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[Channel, set[Subscriber]] = {}
        self._lock = Lock()

    def subscribe(self, channel: Channel) -> Subscriber:
        subscriber = Subscriber(
            channel=channel,
            queue=asyncio.Queue(),
            loop=asyncio.get_running_loop(),
        )
        with self._lock:
            self._subscribers.setdefault(channel, set()).add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: Subscriber) -> None:
        with self._lock:
            subscribers = self._subscribers.get(subscriber.channel)
            if subscribers is None:
                return
            subscribers.discard(subscriber)
            if not subscribers:
                self._subscribers.pop(subscriber.channel, None)

    def publish(self, channels: set[Channel], event: dict[str, str]) -> None:
        with self._lock:
            subscribers = [
                subscriber
                for channel in channels
                for subscriber in self._subscribers.get(channel, set())
            ]
        for subscriber in subscribers:
            subscriber.loop.call_soon_threadsafe(subscriber.queue.put_nowait, event)


event_bus = RealtimeEventBus()


def branch_channel(restaurant_id: UUID, branch_id: UUID, audience: str) -> Channel:
    return f"restaurant:{restaurant_id}:branch:{branch_id}:{audience}"


def order_channel(order_id: UUID) -> Channel:
    return f"order:{order_id}:status"


def build_order_event(order: Order, event_type: str) -> dict[str, str]:
    return {
        "type": event_type,
        "restaurant_id": str(order.restaurant_id),
        "branch_id": str(order.branch_id),
        "order_id": str(order.id),
        "display_number": order.display_number,
        "order_status": order.order_status,
        "payment_status": order.payment_status,
        "channel": order.channel,
        "occurred_at": datetime.now(UTC).isoformat(),
    }


def publish_order_event(order: Order, event_type: str) -> None:
    event = build_order_event(order, event_type)
    event_bus.publish(
        {
            branch_channel(order.restaurant_id, order.branch_id, "cashier"),
            branch_channel(order.restaurant_id, order.branch_id, "kitchen"),
            order_channel(order.id),
        },
        event,
    )
