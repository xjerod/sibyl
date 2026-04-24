"""Event bus protocols and backend resolution."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from sibyl.coordination import CoordinationBackend, get_coordination_backend

EventSubscriber = Callable[[str, dict[str, Any], str | None], Awaitable[None]]


class EventBus(Protocol):
    """Backend contract for coordination events."""

    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def subscribe(self, subscriber: EventSubscriber) -> None: ...

    async def publish(
        self, event: str, data: dict[str, Any], org_id: str | None = None
    ) -> None: ...


_events: EventBus | None = None
_events_backend: CoordinationBackend | None = None


def get_events() -> EventBus:
    """Return the event bus for the active coordination backend."""
    global _events, _events_backend  # noqa: PLW0603

    backend = get_coordination_backend()
    if _events is not None and _events_backend == backend:
        return _events

    if backend == "redis":
        from sibyl.coordination._redis.events import RedisEventBus

        _events = RedisEventBus()
    else:
        from sibyl.coordination._local.events import LocalEventBus

        _events = LocalEventBus()

    _events_backend = backend
    return _events
