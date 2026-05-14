"""Graphiti-compatible cache adapter backed by native embedding providers."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, cast

import structlog

from sibyl_core.embeddings.native import (
    CachedNativeEmbeddingProvider,
    NativeEmbeddingInputKind,
    NativeEmbeddingMetadata,
    NativeEmbeddingProvider,
)

if TYPE_CHECKING:
    from graphiti_core.embedder.client import EmbedderClient

log = structlog.get_logger()
_stats = {"hits": 0, "misses": 0, "evictions": 0}


def get_cache_stats() -> dict[str, int]:
    return _stats.copy()


def reset_cache_stats() -> None:
    global _stats
    _stats = {"hits": 0, "misses": 0, "evictions": 0}


class CachedEmbedder:
    def __init__(
        self,
        embedder: EmbedderClient | NativeEmbeddingProvider,
        max_size: int = 1000,
    ) -> None:
        legacy_embedder: EmbedderClient | None = None
        if _is_native_embedding_provider(embedder):
            provider = cast(NativeEmbeddingProvider, embedder)
        else:
            legacy_embedder = cast(EmbedderClient, embedder)
            provider = _GraphitiEmbeddingProvider(legacy_embedder)
        self._legacy_embedder = legacy_embedder
        self._provider = CachedNativeEmbeddingProvider(
            provider,
            max_size=max_size,
            stats=_stats,
        )

    async def create(
        self,
        input_data: str | list[str] | Iterable[int] | Iterable[Iterable[int]],
    ) -> list[float]:
        if not isinstance(input_data, str):
            if isinstance(input_data, list) and input_data and isinstance(input_data[0], str):
                return await self.create(input_data[0])
            if self._legacy_embedder is not None:
                return await self._legacy_embedder.create(input_data)
            raise TypeError("Native cached embeddings require text input")
        return (await self._provider.embed_texts([input_data], input_kind="query"))[0]

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        return await self._provider.embed_texts(input_data_list, input_kind="document")

    def cache_size(self) -> int:
        return self._provider.cache_size()

    def clear_cache(self) -> None:
        self._provider.clear_cache()
        log.info("Embedding cache cleared")


class _GraphitiEmbeddingProvider:
    def __init__(self, embedder: EmbedderClient) -> None:
        self._embedder = embedder
        config = getattr(embedder, "config", None)
        self._metadata = NativeEmbeddingMetadata(
            provider=embedder.__class__.__name__,
            model=str(getattr(config, "embedding_model", "unknown")),
            dimensions=int(getattr(config, "embedding_dim", 0) or 0),
            cache_namespace="graphiti-compat",
            tokenizer_estimate_method="graphiti",
        )

    @property
    def metadata(self) -> NativeEmbeddingMetadata:
        return self._metadata

    async def embed_texts(
        self,
        texts: Sequence[str],
        *,
        input_kind: NativeEmbeddingInputKind = "document",
    ) -> list[list[float]]:
        if not texts:
            return []
        if input_kind == "query" and len(texts) == 1:
            return [await self._embedder.create(texts[0])]
        try:
            return await self._embedder.create_batch(list(texts))
        except NotImplementedError:
            return [await self._embedder.create(text) for text in texts]


def _is_native_embedding_provider(value: object) -> bool:
    return callable(getattr(value, "embed_texts", None)) and isinstance(
        getattr(value, "metadata", None),
        NativeEmbeddingMetadata,
    )


def wrap_embedder_with_cache(
    embedder: EmbedderClient | NativeEmbeddingProvider,
    max_size: int = 1000,
) -> CachedEmbedder:
    log.info("Wrapping embedder with native LRU cache", max_size=max_size)
    return CachedEmbedder(embedder, max_size=max_size)
