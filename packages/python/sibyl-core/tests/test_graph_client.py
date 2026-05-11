from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import graphiti_core
import pytest

import sibyl_core.graph.cached_embedder as cached_embedder
from sibyl_core.backends.surreal import SurrealDriver
from sibyl_core.config import CoreConfig
from sibyl_core.errors import GraphConnectionError
from sibyl_core.graph import client as _graph_client
from sibyl_core.graph.client import GraphClient


def test_core_config_uses_store_env(monkeypatch) -> None:
    monkeypatch.setenv("SIBYL_STORE", "surreal")

    settings = CoreConfig(_env_file=None)

    assert settings.store == "surreal"


def test_core_config_reads_surreal_token(monkeypatch) -> None:
    monkeypatch.setenv("SIBYL_SURREAL_TOKEN", "token-123")

    settings = CoreConfig(_env_file=None)

    assert settings.surreal_token.get_secret_value() == "token-123"


def test_core_config_ignores_removed_graph_backend_alias(monkeypatch) -> None:
    monkeypatch.delenv("SIBYL_STORE", raising=False)
    monkeypatch.setenv("SIBYL_GRAPH_BACKEND", "falkordb")

    settings = CoreConfig(_env_file=None)

    assert settings.store == "surreal"


@pytest.mark.asyncio
async def test_connect_dispatches_to_surreal_runtime(monkeypatch) -> None:
    client = GraphClient()
    connect_surreal = AsyncMock()

    monkeypatch.setattr(_graph_client.settings, "store", "surreal")
    monkeypatch.setattr(client, "_connect_surreal", connect_surreal)

    await client.connect()

    connect_surreal.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_connect_ignores_removed_legacy_runtime(monkeypatch) -> None:
    client = GraphClient()
    connect_surreal = AsyncMock()

    monkeypatch.setattr(_graph_client.settings, "store", "legacy")
    monkeypatch.setattr(client, "_connect_surreal", connect_surreal)

    await client.connect()

    connect_surreal.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_connect_surreal_constructs_surreal_driver(monkeypatch) -> None:
    client = GraphClient()

    class FakeGraphiti:
        def __init__(self, *, graph_driver, llm_client, embedder):
            self.driver = graph_driver
            self.llm_client = llm_client
            self.embedder = embedder

        async def close(self) -> None:
            return None

    monkeypatch.setattr(_graph_client.settings, "surreal_url", "memory://")
    monkeypatch.setattr(_graph_client.settings, "surreal_data_dir", "")
    monkeypatch.setattr(_graph_client.settings, "surreal_username", "")
    monkeypatch.setattr(_graph_client.settings, "surreal_namespace_prefix", "tenant_")
    monkeypatch.setattr(_graph_client.settings, "surreal_database", "graph_test")
    monkeypatch.setattr(
        _graph_client.settings,
        "surreal_password",
        _graph_client.settings.surreal_password,
    )
    monkeypatch.setattr(
        _graph_client.settings,
        "surreal_token",
        _graph_client.settings.surreal_token,
    )
    monkeypatch.setattr(client, "_create_llm_client", lambda: object())
    monkeypatch.setattr(client, "_create_embedder", lambda: object())

    monkeypatch.setattr(graphiti_core, "Graphiti", FakeGraphiti)
    monkeypatch.setattr(
        cached_embedder,
        "wrap_embedder_with_cache",
        lambda embedder, max_size: embedder,
    )

    await client._connect_surreal()

    assert isinstance(client.driver, SurrealDriver)
    assert client.driver.namespace_prefix == "tenant_"
    assert client.driver.default_database == "graph_test"
    assert client.is_connected is True


def test_create_embedder_uses_gemini_runtime_env(monkeypatch) -> None:
    client = GraphClient()

    monkeypatch.setenv("SIBYL_GRAPH_EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setenv("SIBYL_GRAPH_EMBEDDING_MODEL", "gemini-embedding-2")
    monkeypatch.setenv("SIBYL_GRAPH_EMBEDDING_DIMENSIONS", "768")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")

    embedder = client._create_embedder()

    assert embedder.config.embedding_model == "gemini-embedding-2"
    assert embedder.config.embedding_dim == 768
    assert embedder.config.api_key == "gemini-key"


def test_get_org_driver_reuses_same_clone_for_same_org() -> None:
    client = GraphClient()
    base_driver = MagicMock()
    org_driver = MagicMock()
    client._client = SimpleNamespace(driver=base_driver)
    client._connected = True
    base_driver.clone.return_value = org_driver

    first = client.get_org_driver("org-123")
    second = client.get_org_driver("org-123")

    assert first is org_driver
    assert second is org_driver
    base_driver.clone.assert_called_once_with("org-123")


@pytest.mark.asyncio
async def test_default_execute_read_refuses_surreal_store() -> None:
    client = GraphClient()
    client._store = "surreal"
    client._client = SimpleNamespace(driver=MagicMock())
    client._connected = True

    with pytest.raises(GraphConnectionError, match="org-scoped"):
        await client.execute_read("SELECT * FROM entity")


@pytest.mark.asyncio
async def test_default_execute_write_refuses_surreal_store() -> None:
    client = GraphClient()
    client._store = "surreal"
    client._client = SimpleNamespace(driver=MagicMock())
    client._connected = True

    with pytest.raises(GraphConnectionError, match="org-scoped"):
        await client.execute_write("DELETE FROM entity")


@pytest.mark.asyncio
async def test_default_execute_read_refuses_removed_legacy_store() -> None:
    driver = MagicMock()
    driver.execute_query = AsyncMock(return_value=([{"ok": True}], None, None))
    client = GraphClient()
    client._store = "legacy"
    client._client = SimpleNamespace(driver=driver)
    client._connected = True

    with pytest.raises(GraphConnectionError, match="org-scoped"):
        await client.execute_read("MATCH (n) RETURN n")

    driver.execute_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_org_execute_read_refuses_surreal_store_by_default() -> None:
    client = GraphClient()
    client._store = "surreal"
    client._client = SimpleNamespace(driver=MagicMock())
    client._connected = True

    with pytest.raises(GraphConnectionError, match="org-scoped"):
        await client.execute_read_org("SELECT * FROM entity", "org-123")


@pytest.mark.asyncio
async def test_org_execute_write_refuses_surreal_store_by_default() -> None:
    client = GraphClient()
    client._store = "surreal"
    client._client = SimpleNamespace(driver=MagicMock())
    client._connected = True

    with pytest.raises(GraphConnectionError, match="org-scoped"):
        await client.execute_write_org("DELETE FROM entity", "org-123")


@pytest.mark.asyncio
async def test_org_execute_read_allows_explicit_surreal_debug_escape_hatch() -> None:
    base_driver = MagicMock()
    org_driver = MagicMock()
    org_driver.execute_query = AsyncMock(return_value=[{"ok": True}])
    base_driver.clone.return_value = org_driver
    client = GraphClient()
    client._store = "surreal"
    client._client = SimpleNamespace(driver=base_driver)
    client._connected = True

    rows = await client.execute_read_org(
        "SELECT * FROM entity",
        "org-123",
        allow_surreal=True,
    )

    assert rows == [{"ok": True}]
    org_driver.execute_query.assert_awaited_once_with("SELECT * FROM entity")


@pytest.mark.asyncio
async def test_disconnect_closes_cached_org_drivers_once() -> None:
    client = GraphClient()
    base_graphiti = SimpleNamespace(close=AsyncMock())
    org_driver = MagicMock()
    org_driver.close = AsyncMock()
    client._client = base_graphiti
    client._connected = True
    client._org_drivers["org-123"] = org_driver
    client._org_drivers["org-456"] = org_driver

    await client.disconnect()

    org_driver.close.assert_awaited_once_with()
    base_graphiti.close.assert_awaited_once_with()
    assert client._org_drivers == {}
