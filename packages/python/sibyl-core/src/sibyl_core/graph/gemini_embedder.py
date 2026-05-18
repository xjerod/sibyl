"""Graphiti-compatible adapters over Sibyl's native embedding providers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from pydantic import BaseModel, Field

from sibyl_core.embeddings.native import (
    GeminiNativeEmbeddingProvider,
    NativeEmbeddingMetadata,
    NativeEmbeddingProvider,
)

DEFAULT_GEMINI_EMBEDDING_MODEL = "gemini-embedding-2"
DEFAULT_GRAPH_EMBEDDING_DIMENSIONS = 1024


class SibylGeminiEmbedderConfig(BaseModel):
    embedding_model: str = Field(default=DEFAULT_GEMINI_EMBEDDING_MODEL)
    embedding_dim: int = Field(default=DEFAULT_GRAPH_EMBEDDING_DIMENSIONS)
    api_key: str | None = None


class SibylNativeEmbedderConfig(BaseModel):
    embedding_model: str
    embedding_dim: int
    api_key: str | None = None
    provider: str = "native"
    cache_namespace: str = "graph"


class _NativeEmbedderMixin:
    provider: NativeEmbeddingProvider

    async def create(
        self,
        input_data: str | list[str] | Iterable[int] | Iterable[Iterable[int]],
    ) -> list[float]:
        text = self._coerce_text(input_data)
        return (await self.provider.embed_texts([text], input_kind="query"))[0]

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        return await self.provider.embed_texts(input_data_list, input_kind="document")

    @staticmethod
    def _coerce_text(
        input_data: str | list[str] | Iterable[int] | Iterable[Iterable[int]],
    ) -> str:
        if isinstance(input_data, str):
            return input_data
        if isinstance(input_data, list) and all(isinstance(item, str) for item in input_data):
            return "\n".join(cast("list[str]", input_data))
        raise TypeError("Native graph embeddings require text input")


class SibylNativeEmbedder(_NativeEmbedderMixin):
    def __init__(self, provider: NativeEmbeddingProvider) -> None:
        self.provider = provider
        self.config = SibylNativeEmbedderConfig(
            embedding_model=provider.metadata.model,
            embedding_dim=provider.metadata.dimensions,
            provider=provider.metadata.provider,
            cache_namespace=provider.metadata.cache_namespace,
        )


class SibylGeminiEmbedder(_NativeEmbedderMixin):
    def __init__(
        self,
        config: SibylGeminiEmbedderConfig | None = None,
        client: object | None = None,
        provider: NativeEmbeddingProvider | None = None,
    ) -> None:
        self.config = config or SibylGeminiEmbedderConfig()
        self.provider = provider or GeminiNativeEmbeddingProvider(
            metadata=NativeEmbeddingMetadata(
                provider="gemini",
                model=self.config.embedding_model,
                dimensions=self.config.embedding_dim,
                cache_namespace="graph",
                tokenizer_estimate_method="gemini",
            ),
            api_key=self.config.api_key,
            client=client,
        )
