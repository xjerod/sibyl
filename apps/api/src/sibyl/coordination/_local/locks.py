"""Local in-process lock backend."""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import AsyncGenerator

from sibyl.coordination.locks import LOCK_WAIT_TIMEOUT, LockAcquisitionError


class LocalLockManager:
    """Serialize entity writes within a single process."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._tokens: dict[str, str] = {}
        self._registry_lock = asyncio.Lock()

    async def connect(self) -> None:
        """Initialize the local lock manager."""

    async def disconnect(self) -> None:
        """Reset local lock state on shutdown."""
        async with self._registry_lock:
            self._locks = {key: lock for key, lock in self._locks.items() if lock.locked()}
            self._tokens.clear()

    def _lock_key(self, org_id: str, entity_id: str) -> str:
        return f"{org_id}:{entity_id}"

    async def _get_lock(self, key: str) -> asyncio.Lock:
        async with self._registry_lock:
            return self._locks.setdefault(key, asyncio.Lock())

    async def acquire(
        self,
        org_id: str,
        entity_id: str,
        wait_timeout: float = LOCK_WAIT_TIMEOUT,
        blocking: bool = True,
    ) -> str | None:
        """Acquire an in-process lock."""
        key = self._lock_key(org_id, entity_id)
        lock = await self._get_lock(key)

        if not blocking:
            if lock.locked():
                return None
            await lock.acquire()
        else:
            try:
                await asyncio.wait_for(lock.acquire(), timeout=wait_timeout)
            except TimeoutError as exc:
                raise LockAcquisitionError(entity_id, org_id, "timeout") from exc

        token = f"local:{uuid.uuid4().hex[:8]}"
        self._tokens[key] = token
        return token

    async def release(self, org_id: str, entity_id: str, token: str) -> bool:
        """Release a lock if the token matches the current holder."""
        key = self._lock_key(org_id, entity_id)
        lock = self._locks.get(key)
        if lock is None or self._tokens.get(key) != token:
            return False

        self._tokens.pop(key, None)
        if lock.locked():
            lock.release()
        return True

    async def extend(self, org_id: str, entity_id: str, token: str) -> bool:
        """Extend is a no-op in local mode while the process is alive."""
        key = self._lock_key(org_id, entity_id)
        return self._tokens.get(key) == token

    @contextlib.asynccontextmanager
    async def lock(
        self,
        org_id: str,
        entity_id: str,
        wait_timeout: float = LOCK_WAIT_TIMEOUT,
        blocking: bool = True,
    ) -> AsyncGenerator[str | None]:
        """Context manager for entity locking."""
        token = await self.acquire(org_id, entity_id, wait_timeout, blocking)
        try:
            yield token
        finally:
            if token:
                await self.release(org_id, entity_id, token)
