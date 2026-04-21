"""Local in-process pending registry."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

from sibyl.coordination.pending import PENDING_TTL

log = structlog.get_logger()


class LocalPendingRegistry:
    """Store pending entities and queued operations in memory."""

    def __init__(self) -> None:
        self._pending: dict[str, dict[str, Any]] = {}
        self._pending_expires: dict[str, datetime] = {}
        self._operations: dict[str, list[dict[str, Any]]] = {}
        self._operations_expires: dict[str, datetime] = {}

    def _expires_at(self) -> datetime:
        return datetime.now(UTC) + PENDING_TTL

    def _purge_if_expired(self, entity_id: str) -> None:
        now = datetime.now(UTC)

        pending_expires = self._pending_expires.get(entity_id)
        if pending_expires is not None and pending_expires <= now:
            self._pending.pop(entity_id, None)
            self._pending_expires.pop(entity_id, None)

        ops_expires = self._operations_expires.get(entity_id)
        if ops_expires is not None and ops_expires <= now:
            self._operations.pop(entity_id, None)
            self._operations_expires.pop(entity_id, None)

    async def mark_pending(
        self,
        entity_id: str,
        job_id: str,
        entity_type: str,
        group_id: str,
    ) -> None:
        """Record an entity as pending creation."""
        self._pending[entity_id] = {
            "job_id": job_id,
            "entity_type": entity_type,
            "group_id": group_id,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._pending_expires[entity_id] = self._expires_at()
        log.debug("mark_pending", entity_id=entity_id, job_id=job_id, entity_type=entity_type)

    async def is_pending(self, entity_id: str) -> dict[str, Any] | None:
        """Check whether an entity is still pending creation."""
        self._purge_if_expired(entity_id)
        pending = self._pending.get(entity_id)
        return dict(pending) if pending is not None else None

    async def clear_pending(self, entity_id: str) -> bool:
        """Clear pending status once the entity materializes."""
        self._purge_if_expired(entity_id)
        removed = self._pending.pop(entity_id, None) is not None
        self._pending_expires.pop(entity_id, None)
        if removed:
            log.debug("clear_pending", entity_id=entity_id)
        return removed

    async def queue_pending_operation(
        self,
        entity_id: str,
        operation: str,
        payload: dict[str, Any],
        user_id: str | None = None,
    ) -> str:
        """Queue an operation until the entity exists."""
        self._purge_if_expired(entity_id)

        op_id = f"pending_op_{uuid.uuid4()}"
        op_data = {
            "op_id": op_id,
            "operation": operation,
            "payload": payload,
            "user_id": user_id,
            "queued_at": datetime.now(UTC).isoformat(),
        }
        self._operations.setdefault(entity_id, []).append(op_data)
        self._operations_expires[entity_id] = self._expires_at()

        log.info(
            "queue_pending_operation",
            entity_id=entity_id,
            operation=operation,
            op_id=op_id,
        )
        return op_id

    async def get_pending_operations(self, entity_id: str) -> list[dict[str, Any]]:
        """Return queued operations in FIFO order."""
        self._purge_if_expired(entity_id)
        return [dict(op) for op in self._operations.get(entity_id, [])]

    async def clear_pending_operations(self, entity_id: str) -> int:
        """Clear queued operations for an entity."""
        self._purge_if_expired(entity_id)
        ops = self._operations.pop(entity_id, [])
        self._operations_expires.pop(entity_id, None)
        count = len(ops)
        if count > 0:
            log.debug("clear_pending_operations", entity_id=entity_id, count=count)
        return count
