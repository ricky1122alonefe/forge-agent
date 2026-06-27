"""Simple in-process event bus (pub/sub).

Use for cross-component signaling without coupling them together.
For distributed scenarios, swap in Redis Pub/Sub / NATS.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable

log = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._subs[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Handler) -> None:
        if handler in self._subs.get(topic, []):
            self._subs[topic].remove(handler)

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        log.debug("EventBus.publish %s: %s", topic, list(payload.keys()))
        for handler in list(self._subs.get(topic, [])):
            try:
                await handler(payload)
            except Exception:  # noqa: BLE001
                log.exception("EventBus handler failed for %s", topic)
