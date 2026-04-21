"""Redis-backed pending registry."""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import Any, cast

import structlog
from redis.asyncio import Redis

from sibyl.config import settings
from sibyl.coordination.pending import PENDING_OPS_PREFIX, PENDING_PREFIX, PENDING_TTL

log = structlog.get_logger()


class RedisPendingRegistry:
    """Store pending entities and queued operations in Redis."""

    def __init__(self) -> None:
        self._redis: Redis | None = None

    async def _get_redis(self) -> Redis:
        if self._redis is None:
            self._redis = Redis(
                host=settings.redis_host or "127.0.0.1",
                port=settings.redis_port or 6381,
                password=settings.redis_password_value or None,
                db=settings.redis_jobs_db,
                decode_responses=True,
            )
            await self._redis.ping()
        return self._redis

    async def mark_pending(
        self,
        entity_id: str,
        job_id: str,
        entity_type: str,
        group_id: str,
    ) -> None:
        """Record an entity as pending creation."""
        redis = await self._get_redis()
        key = f"{PENDING_PREFIX}{entity_id}"
        data = {
            "job_id": job_id,
            "entity_type": entity_type,
            "group_id": group_id,
            "created_at": datetime.now(UTC).isoformat(),
        }
        await redis.setex(key, int(PENDING_TTL.total_seconds()), json.dumps(data))
        log.debug("mark_pending", entity_id=entity_id, job_id=job_id, entity_type=entity_type)

    async def is_pending(self, entity_id: str) -> dict[str, Any] | None:
        """Check if an entity is pending creation."""
        redis = await self._get_redis()
        key = f"{PENDING_PREFIX}{entity_id}"
        data = await redis.get(key)
        return json.loads(data) if data else None

    async def clear_pending(self, entity_id: str) -> bool:
        """Remove pending status after entity materializes."""
        redis = await self._get_redis()
        key = f"{PENDING_PREFIX}{entity_id}"
        deleted = await redis.delete(key)
        if deleted:
            log.debug("clear_pending", entity_id=entity_id)
        return deleted > 0

    async def queue_pending_operation(
        self,
        entity_id: str,
        operation: str,
        payload: dict[str, Any],
        user_id: str | None = None,
    ) -> str:
        """Queue an operation to run when the entity materializes."""
        redis = await self._get_redis()
        key = f"{PENDING_OPS_PREFIX}{entity_id}"
        op_id = f"pending_op_{uuid.uuid4()}"
        op_data = {
            "op_id": op_id,
            "operation": operation,
            "payload": payload,
            "user_id": user_id,
            "queued_at": datetime.now(UTC).isoformat(),
        }
        await cast("Awaitable[int]", redis.rpush(key, json.dumps(op_data)))
        await redis.expire(key, int(PENDING_TTL.total_seconds()))

        log.info(
            "queue_pending_operation",
            entity_id=entity_id,
            operation=operation,
            op_id=op_id,
        )
        return op_id

    async def get_pending_operations(self, entity_id: str) -> list[dict[str, Any]]:
        """Return queued operations in FIFO order."""
        redis = await self._get_redis()
        key = f"{PENDING_OPS_PREFIX}{entity_id}"
        ops = await cast("Awaitable[list[str]]", redis.lrange(key, 0, -1))
        return [json.loads(op) for op in ops]

    async def clear_pending_operations(self, entity_id: str) -> int:
        """Clear queued operations for an entity."""
        redis = await self._get_redis()
        key = f"{PENDING_OPS_PREFIX}{entity_id}"
        count = await cast("Awaitable[int]", redis.llen(key))
        if count > 0:
            await redis.delete(key)
            log.debug("clear_pending_operations", entity_id=entity_id, count=count)
        return count
