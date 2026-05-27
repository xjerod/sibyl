"""Legacy graph client wrapper for Sibyl's SurrealDB runtime."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from dotenv import load_dotenv

from sibyl_core.config import core_config as settings

_env_path = Path(__file__).parent.parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

if not os.getenv("SEMAPHORE_LIMIT"):
    os.environ["SEMAPHORE_LIMIT"] = str(settings.graphiti_semaphore_limit)

if not os.getenv("EMBEDDING_DIM"):
    os.environ["EMBEDDING_DIM"] = str(settings.graph_embedding_dimensions)

from sibyl_core.errors import GraphConnectionError  # noqa: E402
from sibyl_core.utils.resilience import GRAPH_RETRY, TIMEOUTS, retry, with_timeout  # noqa: E402

if TYPE_CHECKING:
    from sibyl_core.backends.surreal import SurrealDriver
    from sibyl_core.embeddings.native import (
        NativeEmbeddingMetadata,
        NativeEmbeddingProvider,
    )

log = structlog.get_logger()


@dataclass(slots=True)
class _SurrealRuntimeClient:
    driver: SurrealDriver
    llm_client: object | None
    embedder: Any

    async def close(self) -> None:
        await self.driver.close()


class GraphClient:
    """Wrapper around the legacy graph client surface.

    Default application code uses ``sibyl_core.services.graph_runtime``. This
    class remains for legacy graph managers and compatibility tests that expect
    a ``.client.driver`` shape.
    """

    def __init__(self) -> None:
        """Initialize the graph client."""
        self._client: Any | None = None
        self._connected = False
        self._store = "surreal"
        self._org_drivers: dict[str, SurrealDriver] = {}

    def _create_llm_client(self) -> object | None:
        """Return the retained mock LLM adapter for compatibility tests."""
        if os.getenv("SIBYL_MOCK_LLM", "").lower() in ("true", "1", "yes"):
            from sibyl_core.graph.mock_llm import MockLLMClient

            log.info("Using MockLLMClient (SIBYL_MOCK_LLM=true)")
            return MockLLMClient()
        return None

    def _prepare_embedder_env(self) -> None:
        """Ensure provider SDKs see configured API keys."""
        openai_key = settings.openai_api_key.get_secret_value()
        if openai_key and not os.getenv("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = openai_key

        gemini_key = settings.gemini_api_key.get_secret_value()
        if gemini_key:
            os.environ.setdefault("GEMINI_API_KEY", gemini_key)
            os.environ.setdefault("GOOGLE_API_KEY", gemini_key)

    def _graph_embedding_provider(self) -> str:
        return os.getenv("SIBYL_GRAPH_EMBEDDING_PROVIDER") or settings.graph_embedding_provider

    def _graph_embedding_model(self) -> str:
        env_model = os.getenv("SIBYL_GRAPH_EMBEDDING_MODEL")
        if env_model:
            return env_model
        if (
            self._graph_embedding_provider() == "gemini"
            and settings.graph_embedding_model == "text-embedding-3-small"
        ):
            return "gemini-embedding-2"
        return settings.graph_embedding_model

    def _graph_embedding_dimensions(self) -> int:
        raw = os.getenv("SIBYL_GRAPH_EMBEDDING_DIMENSIONS")
        if raw:
            return int(raw)
        return settings.graph_embedding_dimensions

    @property
    def node_hybrid_search_config(self) -> Any:
        return None

    def _create_embedder(self) -> Any:
        from sibyl_core.graph.gemini_embedder import (
            SibylGeminiEmbedder,
            SibylGeminiEmbedderConfig,
            SibylNativeEmbedder,
        )

        native_provider = self._create_native_embedding_provider()
        if native_provider.metadata.provider == "gemini":
            return SibylGeminiEmbedder(
                config=SibylGeminiEmbedderConfig(
                    api_key=(
                        os.getenv("SIBYL_GEMINI_API_KEY", "")
                        or os.getenv("GEMINI_API_KEY", "")
                        or os.getenv("GOOGLE_API_KEY", "")
                        or settings.gemini_api_key.get_secret_value()
                        or None
                    ),
                    embedding_model=native_provider.metadata.model,
                    embedding_dim=native_provider.metadata.dimensions,
                ),
                provider=native_provider,
            )
        return SibylNativeEmbedder(native_provider)

    def _create_native_embedding_provider(self) -> NativeEmbeddingProvider:
        provider = self._graph_embedding_provider()
        model = self._graph_embedding_model()
        dimensions = self._graph_embedding_dimensions()
        metadata = self._native_embedding_metadata(
            provider=provider,
            model=model,
            dimensions=dimensions,
        )

        if provider == "gemini":
            from sibyl_core.embeddings.native import (
                CachedNativeEmbeddingProvider,
                GeminiNativeEmbeddingProvider,
            )

            api_key = (
                os.getenv("SIBYL_GEMINI_API_KEY", "")
                or os.getenv("GEMINI_API_KEY", "")
                or os.getenv("GOOGLE_API_KEY", "")
                or settings.gemini_api_key.get_secret_value()
            )
            log.debug("Using Gemini native graph embedder", model=model, dimensions=dimensions)
            return CachedNativeEmbeddingProvider(
                GeminiNativeEmbeddingProvider(metadata=metadata, api_key=api_key or None),
                max_size=2000,
            )

        from sibyl_core.embeddings.native import (
            CachedNativeEmbeddingProvider,
            OpenAINativeEmbeddingProvider,
        )

        api_key = (
            os.getenv("SIBYL_OPENAI_API_KEY", "")
            or os.getenv("OPENAI_API_KEY", "")
            or settings.openai_api_key.get_secret_value()
        )
        log.debug("Using OpenAI native graph embedder", model=model, dimensions=dimensions)
        return CachedNativeEmbeddingProvider(
            OpenAINativeEmbeddingProvider(metadata=metadata, api_key=api_key or None),
            max_size=2000,
        )

    def _native_embedding_metadata(
        self,
        *,
        provider: str,
        model: str,
        dimensions: int,
    ) -> NativeEmbeddingMetadata:
        from sibyl_core.embeddings.native import NativeEmbeddingMetadata

        return NativeEmbeddingMetadata(
            provider=provider,
            model=model,
            dimensions=dimensions,
            cache_namespace="graph",
            tokenizer_estimate_method="provider-default",
        )

    async def _connect_surreal(self) -> None:
        """Establish the SurrealDB runtime connection."""
        try:
            from sibyl_core.backends.surreal import SurrealDriver

            url = settings.resolved_surreal_url
            log.info(
                "Connecting to SurrealDB",
                url=url,
                namespace_prefix=settings.surreal_namespace_prefix,
                database=settings.surreal_database,
                llm_provider=settings.llm_provider,
                llm_model=settings.llm_model,
            )

            driver = SurrealDriver(
                url,
                username=settings.surreal_username or None,
                password=settings.surreal_password.get_secret_value() or None,
                token=settings.surreal_token.get_secret_value() or None,
                namespace_prefix=settings.surreal_namespace_prefix,
                default_database=settings.surreal_database,
            )
            llm_client = self._create_llm_client()

            self._prepare_embedder_env()
            embedder = self._create_embedder()
            self._client = _SurrealRuntimeClient(
                driver=driver,
                llm_client=llm_client,
                embedder=embedder,
            )

            self._connected = True
            self._store = "surreal"
            log.info("Connected to SurrealDB successfully", url=url)

        except Exception as e:
            log.error("Failed to connect to SurrealDB", error=str(e))
            raise GraphConnectionError(
                f"Failed to connect to SurrealDB: {e}",
                details={"url": settings.resolved_surreal_url},
            ) from e

    async def connect(self) -> None:
        """Establish connection to the configured graph runtime."""
        await self._connect_surreal()

    async def disconnect(self) -> None:
        """Close the graph database connection."""
        seen_driver_ids: set[int] = set()
        for driver in self._org_drivers.values():
            driver_id = id(driver)
            if driver_id in seen_driver_ids:
                continue
            seen_driver_ids.add(driver_id)
            close = getattr(driver, "close", None)
            if close is not None:
                await close()
        self._org_drivers.clear()
        if self._client is not None:
            await self._client.close()
            self._connected = False
            log.info("Disconnected from graph runtime", store=self._store)

    @property
    def client(self) -> Any:
        """Get the underlying runtime client.

        Raises:
            GraphConnectionError: If not connected.
        """
        if self._client is None or not self._connected:
            raise GraphConnectionError("Not connected to graph database")
        return self._client

    @property
    def is_connected(self) -> bool:
        """Check if the client is connected."""
        return self._connected

    @property
    def driver(self) -> SurrealDriver:
        """Get the underlying graph driver.

        Convenience property to access client.driver directly.

        Returns:
            The active graph driver instance.

        Raises:
            GraphConnectionError: If not connected.
        """
        return self.client.driver

    async def query_with_timeout(
        self,
        query_coro: Awaitable[Any],
        operation_name: str = "graph_query",
    ) -> object:
        """Execute a query coroutine with timeout protection.

        Args:
            query_coro: The coroutine to execute
            operation_name: Name for timeout error messages

        Returns:
            Query result
        """
        timeout = TIMEOUTS.get(operation_name, TIMEOUTS["graph_query"])
        return await with_timeout(query_coro, timeout, operation_name)

    @staticmethod
    def _dict_record(record: object) -> dict[str, Any] | None:
        if not isinstance(record, dict):
            return None
        return {str(key): value for key, value in record.items()}

    @staticmethod
    def _dict_records(records: object) -> list[dict[str, Any]]:
        if not isinstance(records, list):
            return []
        return [row for item in records if (row := GraphClient._dict_record(item)) is not None]

    @staticmethod
    def normalize_result(result: object) -> list[dict[str, Any]]:
        """Normalize graph driver query results to a consistent list of dicts.

        SurrealDB often returns a single dict or list, and some call sites
        expect just a list of row dicts.

        Args:
            result: Raw result from execute_query

        Returns:
            List of result records (possibly empty)
        """
        if result is None:
            return []
        if isinstance(result, tuple):
            records = result[0] if len(result) > 0 else []
            return GraphClient._dict_records(records)
        if isinstance(result, list):
            return GraphClient._dict_records(result)
        if isinstance(result, dict):
            row = GraphClient._dict_record(result)
            return [row] if row is not None else []
        return []

    def get_org_driver(self, organization_id: str) -> SurrealDriver:
        """Get a driver cloned for a specific organization's graph.

        Each organization gets an isolated logical graph. The group ID becomes
        the cloned driver's org-scoped database or namespace.

        Args:
            organization_id: The organization UUID to scope the driver to.

        Returns:
            A graph driver instance scoped to the org's graph.

        Raises:
            ValueError: If organization_id is empty.
        """
        if not organization_id:
            raise ValueError("organization_id is required for org-scoped operations")
        if organization_id not in self._org_drivers:
            self._org_drivers[organization_id] = self.client.driver.clone(organization_id)
        return self._org_drivers[organization_id]

    def _assert_default_query_allowed(self, operation: str) -> None:
        raise GraphConnectionError(
            f"{operation} is unavailable with SurrealDB; use org-scoped graph operations"
        )

    async def ensure_indexes(self, organization_id: str) -> None:
        """Ensure required indexes exist for an organization's graph.

        Safe to call multiple times. The active runtime handles this idempotently.

        Args:
            organization_id: The organization UUID.
        """
        driver = self.get_org_driver(organization_id)

        await driver.build_indices_and_constraints()
        log.info("Ensured SurrealDB schema", org=organization_id)

    async def execute_read(self, query: str, **params: object) -> list[dict]:
        """Execute a read query on the default graph. DEPRECATED for multi-tenant ops.

        WARNING: This uses the default graph, not org-scoped. Use execute_read_org()
        for multi-tenant operations.

        Args:
            query: Cypher query to execute
            **params: Query parameters

        Returns:
            List of result records as dicts
        """
        self._assert_default_query_allowed("execute_read")
        result = await self.client.driver.execute_query(query, **params)
        return self.normalize_result(result)

    async def execute_write(self, query: str, **params: object) -> list[dict]:
        """Execute a write query on the default graph. DEPRECATED for multi-tenant ops.

        WARNING: This uses the default graph, not org-scoped. Use execute_write_org()
        for multi-tenant operations.

        Args:
            query: Cypher query to execute
            **params: Query parameters

        Returns:
            List of result records as dicts

        Raises:
            Exception: If query execution fails
        """
        self._assert_default_query_allowed("execute_write")
        result = await self.client.driver.execute_query(query, **params)
        return self.normalize_result(result)

    async def execute_read_org(
        self,
        query: str,
        organization_id: str,
        *,
        allow_surreal: bool = False,
        **params: object,
    ) -> list[dict]:
        """Execute a read query on an organization's graph.

        This is the preferred method for multi-tenant read operations.

        Args:
            query: Cypher query to execute
            organization_id: The organization UUID to scope the query to.
            **params: Query parameters

        Returns:
            List of result records as dicts
        """
        if not allow_surreal:
            self._assert_default_query_allowed("execute_read_org")
        driver = self.get_org_driver(organization_id)
        result = await driver.execute_query(query, **params)
        return self.normalize_result(result)

    async def execute_write_org(
        self,
        query: str,
        organization_id: str,
        *,
        allow_surreal: bool = False,
        **params: object,
    ) -> list[dict]:
        """Execute a write query on an organization's graph.

        This is the preferred method for multi-tenant write operations.

        Args:
            query: Cypher query to execute
            organization_id: The organization UUID to scope the query to.
            **params: Query parameters

        Returns:
            List of result records as dicts

        Raises:
            Exception: If query execution fails
        """
        if not allow_surreal:
            self._assert_default_query_allowed("execute_write_org")
        driver = self.get_org_driver(organization_id)
        result = await driver.execute_query(query, **params)
        return self.normalize_result(result)

    async def __aenter__(self) -> GraphClient:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Async context manager exit."""
        await self.disconnect()


# Global client instance with thread-safe initialization
_graph_client: GraphClient | None = None
_client_lock = asyncio.Lock()


@retry(config=GRAPH_RETRY)
async def _connect_client() -> GraphClient:
    """Create and connect a new graph client with retry logic."""
    client = GraphClient()
    await client.connect()
    return client


async def get_graph_client() -> GraphClient:
    """Get the global graph client instance.

    Creates and connects a new client if one doesn't exist.
    Thread-safe via asyncio.Lock to prevent race conditions.
    Retries on transient connection failures.
    """
    global _graph_client
    async with _client_lock:
        if _graph_client is None:
            _graph_client = await _connect_client()
    return _graph_client


async def reset_graph_client() -> None:
    """Reset the global client (useful for testing)."""
    global _graph_client
    async with _client_lock:
        if _graph_client is not None:
            await _graph_client.disconnect()
            _graph_client = None
