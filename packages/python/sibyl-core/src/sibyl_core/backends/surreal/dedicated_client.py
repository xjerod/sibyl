"""Shared client wrapper for dedicated SurrealDB namespaces."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import cast

from sibyl_core.backends.surreal.connection import (
    _can_retry_query,
    _can_retry_raw_query,
    _is_transient_connection_error,
)
from sibyl_core.backends.surreal.observability import (
    elapsed_ms,
    log_query,
    query_start,
)
from sibyl_core.backends.surreal.protocols import QueryParams, SurrealClient

logger = logging.getLogger(__name__)
_MAX_CLOSED_CONNECTION_RETRIES = 2
_DEFAULT_POOL_SIZE = 4


def _default_pool_size_for_url(url: str) -> int:
    # Embedded stores are single-writer and `memory://` hands out a fresh empty
    # database per connection, so a pool there would fragment state. Server URLs
    # get the real pool; embedded collapses to one reused connection.
    if url.startswith(("memory://", "surrealkv://", "rocksdb://", "file://")):
        return 1
    return _DEFAULT_POOL_SIZE


class _PooledConnection:
    """One independent SurrealDB socket, used by at most one query at a time."""

    def __init__(
        self,
        *,
        url: str,
        username: str,
        password: str,
        token: str,
        namespace: str,
        database: str,
    ) -> None:
        self._url = url
        self._username = username
        self._password = password
        self._token = token
        self._namespace = namespace
        self._database = database
        self._client: SurrealClient | None = None
        self._connect_lock = asyncio.Lock()

    async def connect(self) -> SurrealClient:
        if self._client is not None:
            return self._client

        async with self._connect_lock:
            if self._client is not None:
                return self._client

            from surrealdb import AsyncSurreal

            client = cast(SurrealClient, AsyncSurreal(self._url))
            try:
                if self._requires_auth():
                    if self._token:
                        await client.authenticate(self._token)
                    elif self._username and self._password:
                        await client.signin(
                            {"username": self._username, "password": self._password}
                        )
                await client.use(self._namespace, self._database)
            except Exception:
                with contextlib.suppress(Exception):
                    await client.close()
                raise
            self._client = client
            return client

    def _requires_auth(self) -> bool:
        return not self._url.startswith(("memory://", "surrealkv://"))

    async def drop(self) -> None:
        async with self._connect_lock:
            await self._close_locked()

    async def close(self) -> None:
        async with self._connect_lock:
            await self._close_locked()

    async def _close_locked(self) -> None:
        client = self._client
        self._client = None
        if client is not None:
            try:
                await client.close()
            except Exception as exc:
                logger.debug("SurrealDB pooled connection close failed: %s", exc)


class DedicatedSurrealClient:
    def __init__(
        self,
        *,
        url: str,
        username: str = "",
        password: str = "",
        token: str = "",
        namespace: str,
        database: str,
        client_kind: str = "dedicated",
        pool_size: int | None = None,
    ) -> None:
        self._url = url
        self._username = username
        self._password = password
        self._token = token
        self._namespace = namespace
        self._database = database
        self._client_kind = client_kind
        resolved_pool_size = pool_size if pool_size is not None else _default_pool_size_for_url(url)
        self._pool_size = max(1, resolved_pool_size)
        self._pool: list[_PooledConnection] = [
            self._new_connection() for _ in range(self._pool_size)
        ]
        self._available: asyncio.Queue[_PooledConnection] = asyncio.Queue()
        for connection in self._pool:
            self._available.put_nowait(connection)
        self._close_lock = asyncio.Lock()

    @property
    def namespace(self) -> str:
        return self._namespace

    @property
    def database(self) -> str:
        return self._database

    def _new_connection(self) -> _PooledConnection:
        return _PooledConnection(
            url=self._url,
            username=self._username,
            password=self._password,
            token=self._token,
            namespace=self._namespace,
            database=self._database,
        )

    async def connect(self) -> SurrealClient:
        connection = await self._available.get()
        try:
            return await connection.connect()
        finally:
            self._available.put_nowait(connection)

    async def execute_query(self, query: str, **params: object) -> object:
        return await self._execute(query, params=params, raw=False)

    async def execute_query_raw(self, query: str, **params: object) -> object:
        return await self._execute(query, params=params, raw=True)

    async def close(self) -> None:
        async with self._close_lock:
            await asyncio.gather(
                *(connection.close() for connection in self._pool),
                return_exceptions=True,
            )

    async def _execute(self, query: str, *, params: QueryParams, raw: bool) -> object:
        started_at = query_start()
        retry_count = 0
        result: object = None
        connection = await self._available.get()
        try:
            while True:
                try:
                    client = await connection.connect()
                    result = await self._send_query(client, query, params=params, raw=raw)
                    break
                except Exception as exc:
                    if not _is_transient_connection_error(exc):
                        raise
                    await connection.drop()
                    can_retry = _can_retry_raw_query(query) if raw else _can_retry_query(query)
                    if not can_retry or retry_count >= _MAX_CLOSED_CONNECTION_RETRIES:
                        raise
                    retry_count += 1
                    logger.warning(
                        "SurrealDB dedicated client connection failed during read; retrying "
                        "attempt=%s error=%s",
                        retry_count,
                        exc,
                    )
        except Exception as exc:
            log_query(
                query,
                client_kind=self._client_kind,
                namespace=self._namespace,
                database=self._database,
                raw=raw,
                elapsed=elapsed_ms(started_at),
                retry_count=retry_count,
                error=exc,
            )
            raise
        finally:
            self._available.put_nowait(connection)
        log_query(
            query,
            client_kind=self._client_kind,
            namespace=self._namespace,
            database=self._database,
            raw=raw,
            elapsed=elapsed_ms(started_at),
            retry_count=retry_count,
        )
        return result

    async def _send_query(
        self,
        client: SurrealClient,
        query: str,
        *,
        params: QueryParams,
        raw: bool,
    ) -> object:
        bound_params = params if params else None
        if raw:
            return await client.query_raw(query, bound_params)
        return await client.query(query, bound_params)


__all__ = ["DedicatedSurrealClient"]
