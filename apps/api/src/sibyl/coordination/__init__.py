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
    health: dict[str, Any] = {
        "backend": backend,
        "store": settings.store,
        "durable": backend == "redis",
        "single_process": backend == "local",
        "queue_healthy": False,
        "worker_healthy": False,
        "queue_depth": 0,
    }

    if backend == "local":
        return {
            **health,
            "status": "unavailable",
            "error": "Local coordination backend is not implemented yet",
        }

    try:
        from sibyl.jobs.queue import get_pool

        pool = await get_pool()
        redis_info = await pool.info()
        pool_info = await pool.pool.info()
    except Exception:
        return {
            **health,
            "status": "unhealthy",
            "error": "Health check failed",
        }

    return {
        **health,
        "status": "healthy",
        "queue_healthy": bool(redis_info),
        "worker_healthy": bool(pool_info.get("workers", 0)),
        "queue_depth": pool_info.get("pending_jobs", 0) if pool_info else 0,
        "redis_version": redis_info.get("redis_version", "unknown"),
        "connected_clients": redis_info.get("connected_clients", 0),
        "used_memory_human": redis_info.get("used_memory_human", "unknown"),
    }
