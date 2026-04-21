"""Pending registry protocols and backend resolution."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Protocol

from sibyl.coordination import CoordinationBackend, get_coordination_backend

PENDING_TTL = timedelta(minutes=5)
PENDING_PREFIX = "sibyl:pending:"
PENDING_OPS_PREFIX = "sibyl:pending_ops:"


class PendingRegistry(Protocol):
    """Backend contract for pending entity coordination."""

    async def mark_pending(
        self,
        entity_id: str,
        job_id: str,
        entity_type: str,
        group_id: str,
    ) -> None: ...

    async def is_pending(self, entity_id: str) -> dict[str, Any] | None: ...

    async def clear_pending(self, entity_id: str) -> bool: ...

    async def queue_pending_operation(
        self,
        entity_id: str,
        operation: str,
        payload: dict[str, Any],
        user_id: str | None = None,
    ) -> str: ...

    async def get_pending_operations(self, entity_id: str) -> list[dict[str, Any]]: ...

    async def clear_pending_operations(self, entity_id: str) -> int: ...


_pending: PendingRegistry | None = None
_pending_backend: CoordinationBackend | None = None


def get_pending() -> PendingRegistry:
    """Return the pending registry for the active coordination backend."""
    global _pending, _pending_backend  # noqa: PLW0603

    backend = get_coordination_backend()
    if _pending is not None and _pending_backend == backend:
        return _pending

    if backend == "redis":
        from sibyl.coordination._redis.pending import RedisPendingRegistry

        _pending = RedisPendingRegistry()
    else:
        from sibyl.coordination._local.pending import LocalPendingRegistry

        _pending = LocalPendingRegistry()

    _pending_backend = backend
    return _pending
