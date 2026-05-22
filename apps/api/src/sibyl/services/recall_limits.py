"""Per-user recall concurrency limits."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sibyl_core.auth import OrganizationRole

DEFAULT_MAX_CONCURRENT_RECALLS_PER_USER = 3
RECALL_MAX_CONCURRENT_ENV = "SIBYL_RECALL_MAX_CONCURRENT_PER_USER"


class RecallConcurrencyLimitExceededError(Exception):
    def __init__(self, *, user_id: str, max_concurrent: int) -> None:
        super().__init__("recall_concurrency_limit_exceeded")
        self.user_id = user_id
        self.max_concurrent = max_concurrent


class RecallConcurrencyLimiter:
    def __init__(self, *, default_max_concurrent: int = DEFAULT_MAX_CONCURRENT_RECALLS_PER_USER):
        self._default_max_concurrent = default_max_concurrent
        self._active: dict[tuple[str, str], int] = {}
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def slot(
        self,
        *,
        organization_id: str,
        user_id: str,
        organization_role: OrganizationRole | str | None,
    ) -> AsyncIterator[None]:
        if _is_owner(organization_role):
            yield
            return

        max_concurrent = _max_concurrent(default=self._default_max_concurrent)
        key = (organization_id, user_id)
        async with self._lock:
            active = self._active.get(key, 0)
            if active >= max_concurrent:
                raise RecallConcurrencyLimitExceededError(
                    user_id=user_id,
                    max_concurrent=max_concurrent,
                )
            self._active[key] = active + 1

        try:
            yield
        finally:
            async with self._lock:
                active = self._active.get(key, 0)
                if active <= 1:
                    self._active.pop(key, None)
                else:
                    self._active[key] = active - 1


_recall_concurrency_limiter = RecallConcurrencyLimiter()


def get_recall_concurrency_limiter() -> RecallConcurrencyLimiter:
    return _recall_concurrency_limiter


@asynccontextmanager
async def recall_concurrency_slot(
    *,
    organization_id: str,
    user_id: str,
    organization_role: OrganizationRole | str | None,
) -> AsyncIterator[None]:
    async with _recall_concurrency_limiter.slot(
        organization_id=organization_id,
        user_id=user_id,
        organization_role=organization_role,
    ):
        yield


def _is_owner(role: OrganizationRole | str | None) -> bool:
    if role is None:
        return False
    return str(role) == OrganizationRole.OWNER.value


def _max_concurrent(*, default: int) -> int:
    raw_value = os.environ.get(RECALL_MAX_CONCURRENT_ENV, "").strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"Invalid {RECALL_MAX_CONCURRENT_ENV}: {raw_value}") from exc
    if value < 1:
        raise ValueError(f"Invalid {RECALL_MAX_CONCURRENT_ENV}: {raw_value}")
    return value
