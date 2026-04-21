from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

import sibyl.coordination.broker as broker_module
from sibyl.config import settings
from sibyl.coordination._local.broker import LOCAL_BROKER_ERROR, LocalQueueBroker
from sibyl.coordination._local.events import LocalEventBus
from sibyl.coordination._local.locks import LocalLockManager
from sibyl.coordination._local.pending import LocalPendingRegistry
from sibyl.coordination._redis.broker import RedisQueueBroker


@pytest.mark.asyncio
async def test_local_event_bus_fans_out_to_subscribers() -> None:
    bus = LocalEventBus()
    subscriber = AsyncMock()

    await bus.connect()
    await bus.subscribe(subscriber)
    await bus.publish("entity_updated", {"id": "entity_123"}, "org_456")

    subscriber.assert_awaited_once_with("entity_updated", {"id": "entity_123"}, "org_456")


@pytest.mark.asyncio
async def test_local_lock_manager_serializes_same_entity() -> None:
    manager = LocalLockManager()
    entered_first = asyncio.Event()
    release_first = asyncio.Event()
    order: list[str] = []

    async def first_worker() -> None:
        async with manager.lock("org_123", "entity_456"):
            order.append("first_start")
            entered_first.set()
            await release_first.wait()
            order.append("first_end")

    async def second_worker() -> None:
        await entered_first.wait()
        async with manager.lock("org_123", "entity_456"):
            order.append("second")

    first_task = asyncio.create_task(first_worker())
    second_task = asyncio.create_task(second_worker())

    await entered_first.wait()
    await asyncio.sleep(0)
    assert order == ["first_start"]

    release_first.set()
    await asyncio.gather(first_task, second_task)

    assert order == ["first_start", "first_end", "second"]


@pytest.mark.asyncio
async def test_local_pending_registry_expires_pending_state_and_operations() -> None:
    registry = LocalPendingRegistry()

    await registry.mark_pending("task_123", "create_entity:task_123", "task", "org_456")
    await registry.queue_pending_operation(
        "task_123",
        "add_note",
        {"content": "Test note"},
        "user_789",
    )

    expired_at = datetime.now(UTC) - timedelta(seconds=1)
    registry._pending_expires["task_123"] = expired_at
    registry._operations_expires["task_123"] = expired_at

    assert await registry.is_pending("task_123") is None
    assert await registry.get_pending_operations("task_123") == []


@pytest.mark.asyncio
async def test_local_queue_broker_reports_degraded_health() -> None:
    broker = LocalQueueBroker()

    assert await broker.health() == {
        "status": "degraded",
        "error": LOCAL_BROKER_ERROR,
        "queue_healthy": False,
        "worker_healthy": False,
        "queue_depth": 0,
    }


@pytest.mark.asyncio
async def test_local_queue_broker_enqueue_is_unsupported() -> None:
    broker = LocalQueueBroker()

    with pytest.raises(RuntimeError, match=LOCAL_BROKER_ERROR):
        await broker.enqueue_sync("source_123")


@pytest.mark.parametrize("configured_backend", ["auto", "local"])
def test_surreal_queue_backend_stays_redis_until_local_jobs_exist(
    monkeypatch: pytest.MonkeyPatch,
    configured_backend: str,
) -> None:
    monkeypatch.setattr(settings, "store", "surreal")
    monkeypatch.setattr(settings, "coordination_backend", configured_backend)
    broker_module._broker = None
    broker_module._broker_backend = None

    try:
        assert broker_module.get_queue_backend() == "redis"
        assert isinstance(broker_module.get_broker(), RedisQueueBroker)
    finally:
        broker_module._broker = None
        broker_module._broker_backend = None
