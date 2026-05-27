"""Redis event bus for cross-pod WebSocket broadcasts."""

from __future__ import annotations

import asyncio
import contextlib
import json
from datetime import UTC, datetime
from typing import Any

import structlog
from redis.asyncio import Redis

from sibyl.config import settings
from sibyl.coordination.events import EventSubscriber

log = structlog.get_logger()

PUBSUB_CHANNEL = "sibyl:websocket:events"
PUBSUB_DB = 2


class RedisEventBus:
    """Redis pub/sub manager for cross-pod WebSocket broadcasts."""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._pubsub: Any | None = None
        self._listener_task: asyncio.Task[None] | None = None
        self._subscribers: list[EventSubscriber] = []

    async def connect(self) -> None:
        """Connect to Redis for pub/sub."""
        if self._redis is not None:
            return

        redis_host = settings.redis_host or "127.0.0.1"
        redis_port = settings.redis_port or 6381

        self._redis = Redis(
            host=redis_host,
            port=redis_port,
            password=settings.redis_password_value or None,
            db=PUBSUB_DB,
            decode_responses=True,
        )

        await self._redis.ping()
        log.info(
            "redis_event_bus_connected",
            host=redis_host,
            port=redis_port,
            db=PUBSUB_DB,
        )

    async def disconnect(self) -> None:
        """Disconnect from Redis and stop the listener."""
        if self._listener_task:
            self._listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener_task
            self._listener_task = None

        if self._pubsub:
            await self._pubsub.unsubscribe(PUBSUB_CHANNEL)
            await self._pubsub.close()
            self._pubsub = None

        if self._redis:
            await self._redis.close()
            self._redis = None

        self._subscribers.clear()
        log.info("redis_event_bus_disconnected")

    async def _require_redis(self) -> Redis:
        if self._redis is None:
            await self.connect()
        if self._redis is None:
            raise RuntimeError("Redis event bus is not connected")
        return self._redis

    async def subscribe(self, subscriber: EventSubscriber) -> None:
        """Subscribe to the Redis channel and forward messages locally."""
        redis = await self._require_redis()

        if subscriber not in self._subscribers:
            self._subscribers.append(subscriber)

        if self._pubsub is None:
            self._pubsub = redis.pubsub()
            await self._pubsub.subscribe(PUBSUB_CHANNEL)
            self._listener_task = asyncio.create_task(self._listen())
            log.info("redis_event_bus_subscribed", channel=PUBSUB_CHANNEL)

    async def publish(self, event: str, data: dict[str, Any], org_id: str | None = None) -> None:
        """Publish an event to the Redis channel."""
        redis = await self._require_redis()

        message = {
            "event": event,
            "data": data,
            "org_id": org_id,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        try:
            await redis.publish(PUBSUB_CHANNEL, json.dumps(message))
            log.debug("redis_event_bus_published", ws_event=event, org_id=org_id)
        except Exception:
            log.exception("redis_event_bus_publish_failed", ws_event=event)
            raise

    async def _listen(self) -> None:
        """Receive events from Redis and fan them out locally."""
        if self._pubsub is None:
            return

        try:
            async for message in self._pubsub.listen():
                if message["type"] != "message":
                    continue

                try:
                    payload = json.loads(message["data"])
                    event = payload.get("event")
                    data = payload.get("data", {})
                    org_id = payload.get("org_id")

                    if not event:
                        continue

                    for subscriber in list(self._subscribers):
                        await subscriber(event, data, org_id)
                except json.JSONDecodeError:
                    log.warning("redis_event_bus_invalid_json", data=message["data"])
                except Exception:
                    log.exception("redis_event_bus_callback_error")

        except asyncio.CancelledError:
            log.debug("redis_event_bus_listener_cancelled")
            raise
        except Exception:
            log.exception("redis_event_bus_listener_error")
