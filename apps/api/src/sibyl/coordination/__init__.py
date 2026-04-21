"""Coordination backend resolution and health helpers."""

from __future__ import annotations

from typing import Any, Literal

from sibyl.config import settings

CoordinationBackend = Literal["local", "redis"]


def get_coordination_backend() -> CoordinationBackend:
    """Return the resolved coordination backend for the current process."""
    return settings.resolved_coordination_backend


def uses_redis_coordination() -> bool:
    """Return True when Redis-backed coordination should be started."""
    return get_coordination_backend() == "redis"


async def get_coordination_health() -> dict[str, Any]:
    """Return coordination health metadata for admin and jobs surfaces."""
    backend = get_coordination_backend()
    from sibyl.coordination.broker import get_queue_backend

    queue_backend = get_queue_backend()
    health: dict[str, Any] = {
        "backend": backend,
        "store": settings.store,
        "durable": backend == "redis",
        "queue_backend": queue_backend,
        "queue_durable": queue_backend == "redis",
        "single_process": backend == "local",
        "queue_healthy": False,
        "worker_healthy": False,
        "queue_depth": 0,
    }

    try:
        from sibyl.coordination.broker import get_broker

        broker_health = await get_broker().health()
    except Exception:
        return {
            **health,
            "status": "unhealthy",
            "error": "Health check failed",
        }

    return {**health, **broker_health}
