"""In-process domain events (e.g. `record.added`), published after the change is committed.

Until the WebSocket fan-out exists (BU-04 subscribes a Redis publisher here), nothing listens in production.
Subscribers must be quick and must not raise: a failing subscriber is logged and the others still run.
"""

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

Subscriber = Callable[[str, dict], None]
_subscribers: list[Subscriber] = []


def subscribe(subscriber: Subscriber) -> Callable[[], None]:
    """Register `subscriber(event_type, payload)`. Returns a function that removes it again."""
    _subscribers.append(subscriber)
    return lambda: _subscribers.remove(subscriber)


def publish(event_type: str, payload: dict) -> None:
    for subscriber in list(_subscribers):
        try:
            subscriber(event_type, payload)
        except Exception:  # noqa: BLE001 - one broken listener must not break the request that published
            logger.exception("event subscriber failed for %s", event_type)
