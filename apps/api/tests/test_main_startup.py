from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.applications import Starlette

from sibyl import main as main_module


class _FakeSessionManager:
    @asynccontextmanager
    async def run(self):
        yield


class _FakeMCPServer:
    def __init__(self) -> None:
        self.session_manager = _FakeSessionManager()

    def streamable_http_app(self) -> Starlette:
        return Starlette()


@pytest.mark.asyncio
async def test_surreal_mode_skips_legacy_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    run_migrations = AsyncMock()
    recover_stuck_sources = AsyncMock()
    load_api_keys_from_db = AsyncMock()
    init_pubsub = AsyncMock()
    init_locks = AsyncMock()

    monkeypatch.setattr(main_module.settings, "store", "surreal")
    monkeypatch.setattr("sibyl.api.app.create_api_app", lambda: Starlette())
    monkeypatch.setattr("sibyl.server.create_mcp_server", lambda **_: _FakeMCPServer())
    monkeypatch.setattr("sibyl.db.migrations.run_migrations", run_migrations)
    monkeypatch.setattr("sibyl.api.routes.admin.recover_stuck_sources", recover_stuck_sources)
    monkeypatch.setattr("sibyl.services.settings.load_api_keys_from_db", load_api_keys_from_db)
    monkeypatch.setattr("sibyl.api.pubsub.init_pubsub", init_pubsub)
    monkeypatch.setattr("sibyl.locks.init_locks", init_locks)
    monkeypatch.setattr(
        "sibyl_core.graph.client.get_graph_client",
        AsyncMock(return_value=SimpleNamespace(is_connected=True)),
    )

    app = main_module.create_combined_app()

    async with app.router.lifespan_context(app):
        pass

    run_migrations.assert_not_awaited()
    recover_stuck_sources.assert_not_awaited()
    load_api_keys_from_db.assert_not_awaited()
    init_pubsub.assert_not_awaited()
    init_locks.assert_not_awaited()
