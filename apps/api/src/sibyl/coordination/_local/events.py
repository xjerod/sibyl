"""Local in-process event bus."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from sibyl.coordination.events import EventSubscriber

log = structlog.get_logger()


class LocalEventBus:
    """Fan out events directly to in-process subscribers."""

    def __init__(self) -> None:
        self._subscribers: list[EventSubscriber] = []
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Initialize the local event bus."""

    async def disconnect(self) -> None:
        """Remove all subscribers on shutdown."""
        async with self._lock:
            self._subscribers.clear()

    async def subscribe(self, subscriber: EventSubscriber) -> None:
        """Register an in-process subscriber."""
        async with self._lock:
            if subscriber not in self._subscribers:
                self._subscribers.append(subscriber)

    async def publish(self, event: str, data: dict[str, Any], org_id: str | None = None) -> None:
        """Deliver an event to all in-process subscribers."""
        async with self._lock:
            subscribers = list(self._subscribers)

        for subscriber in subscribers:
            try:
                await subscriber(event, data, org_id)
            except Exception:
                log.exception("local_event_bus_callback_error", ws_event=event, org_id=org_id)
