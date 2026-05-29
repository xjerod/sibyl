from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from sibyl_core.backends.surreal.dedicated_client import DedicatedSurrealClient


class _ConcurrencyTracker:
    def __init__(self) -> None:
        self.in_flight = 0
        self.peak = 0
        self.release = asyncio.Event()


def _install_overlap_surreal(monkeypatch, tracker: _ConcurrencyTracker) -> list[Any]:
    clients: list[Any] = []

    class FakeAsyncSurreal:
        def __init__(self, url: str) -> None:
            self.url = url
            self.closed = False
            clients.append(self)

        async def signin(self, credentials: dict[str, str]) -> None:
            self.credentials = credentials

        async def use(self, namespace: str, database: str) -> None:
            self.namespace = namespace
            self.database = database

        async def query(self, query: str, params: object | None = None) -> list[dict[str, str]]:
            tracker.in_flight += 1
            tracker.peak = max(tracker.peak, tracker.in_flight)
            try:
                await tracker.release.wait()
                return [{"ok": "yes"}]
            finally:
                tracker.in_flight -= 1

        async def close(self) -> None:
            self.closed = True

    monkeypatch.setitem(sys.modules, "surrealdb", SimpleNamespace(AsyncSurreal=FakeAsyncSurreal))
    return clients


@pytest.mark.asyncio
async def test_two_reads_on_one_client_overlap_in_flight(monkeypatch) -> None:
    tracker = _ConcurrencyTracker()
    clients = _install_overlap_surreal(monkeypatch, tracker)

    client = DedicatedSurrealClient(
        url="ws://localhost:8000/rpc",
        username="root",
        password="root",
        namespace="org_overlap",
        database="graph",
        pool_size=4,
    )

    first = asyncio.create_task(client.execute_query("SELECT * FROM entity;"))
    second = asyncio.create_task(client.execute_query("SELECT * FROM entity;"))

    async def _both_in_flight() -> bool:
        return tracker.in_flight >= 2

    for _ in range(200):
        if await _both_in_flight():
            break
        await asyncio.sleep(0.005)

    assert tracker.in_flight >= 2, "two queries on one client must be in flight at once"

    tracker.release.set()
    results = await asyncio.gather(first, second)

    assert tracker.peak >= 2
    assert results == [[{"ok": "yes"}], [{"ok": "yes"}]]
    assert len(clients) >= 2


@pytest.mark.asyncio
async def test_embedded_url_collapses_to_single_connection(monkeypatch) -> None:
    tracker = _ConcurrencyTracker()
    tracker.release.set()
    clients = _install_overlap_surreal(monkeypatch, tracker)

    client = DedicatedSurrealClient(
        url="memory://",
        namespace="sibyl_content",
        database="content",
    )

    await asyncio.gather(*(client.execute_query("SELECT * FROM crawl_sources;") for _ in range(6)))

    assert len(clients) == 1


@pytest.mark.asyncio
async def test_close_closes_every_pooled_connection(monkeypatch) -> None:
    tracker = _ConcurrencyTracker()
    tracker.release.set()
    clients = _install_overlap_surreal(monkeypatch, tracker)

    client = DedicatedSurrealClient(
        url="ws://localhost:8000/rpc",
        username="root",
        password="root",
        namespace="org_close",
        database="graph",
        pool_size=3,
    )

    await asyncio.gather(*(client.execute_query("SELECT * FROM entity;") for _ in range(3)))
    assert len(clients) == 3

    await client.close()

    assert all(fake.closed for fake in clients)
