"""Lock backend protocols and backend resolution."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Protocol, cast

from sibyl.coordination import CoordinationBackend, get_coordination_backend

LOCK_TTL_SECONDS = 30
LOCK_RETRY_DELAY_BASE = 0.2
LOCK_MAX_RETRIES = 10
LOCK_WAIT_TIMEOUT = 45.0


class LockAcquisitionError(Exception):
    """Failed to acquire an entity lock."""

    def __init__(self, entity_id: str, org_id: str, reason: str = "timeout"):
        self.entity_id = entity_id
        self.org_id = org_id
        self.reason = reason
        super().__init__(f"Failed to acquire lock for {entity_id}: {reason}")


class LockBackend(Protocol):
    """Backend contract for entity locking."""

    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def acquire(
        self,
        org_id: str,
        entity_id: str,
        wait_timeout: float = LOCK_WAIT_TIMEOUT,
        blocking: bool = True,
    ) -> str | None: ...

    async def release(self, org_id: str, entity_id: str, token: str) -> bool: ...

    async def extend(self, org_id: str, entity_id: str, token: str) -> bool: ...

    def lock(
        self,
        org_id: str,
        entity_id: str,
        wait_timeout: float = LOCK_WAIT_TIMEOUT,
        blocking: bool = True,
    ) -> AbstractAsyncContextManager[str | None]: ...


_locks: LockBackend | None = None
_locks_backend: CoordinationBackend | None = None


def get_locks() -> LockBackend:
    """Return the lock backend for the active coordination backend."""
    global _locks, _locks_backend  # noqa: PLW0603

    backend = get_coordination_backend()
    if _locks is not None and _locks_backend == backend:
        return _locks

    manager: LockBackend
    if backend == "redis":
        from sibyl.coordination._redis.locks import EntityLockManager

        manager = cast("LockBackend", EntityLockManager())
    else:
        from sibyl.coordination._local.locks import LocalLockManager

        manager = cast("LockBackend", LocalLockManager())

    _locks = manager
    _locks_backend = backend
    return manager
