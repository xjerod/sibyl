"""Compatibility shim for coordination event backends."""

from __future__ import annotations

from typing import Any

from sibyl.coordination.events import EventBus, get_events


def get_pubsub() -> EventBus:
    """Return the active event bus backend."""
    return get_events()


async def init_pubsub(local_broadcast_callback: Any) -> None:
    """Initialize the active event bus on server startup."""
    bus = get_pubsub()
    await bus.connect()
    await bus.subscribe(local_broadcast_callback)


async def shutdown_pubsub() -> None:
    """Shutdown the active event bus on server shutdown."""
    bus = get_pubsub()
    await bus.disconnect()


async def publish_event(event: str, data: dict[str, Any], *, org_id: str | None = None) -> None:
    """Publish an event through the active coordination backend."""
    bus = get_pubsub()
    await bus.publish(event, data, org_id)
