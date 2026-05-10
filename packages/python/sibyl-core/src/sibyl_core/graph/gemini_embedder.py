"""Graphiti-compatible Gemini embedder with Gemini Embedding 2 text formatting."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

from google import genai
from google.genai import types
from graphiti_core.embedder.client import EmbedderClient, EmbedderConfig
from pydantic import Field

from sibyl_core.embeddings.gemini import (
    GeminiInputKind,
    build_gemini_contents,
    format_gemini_embedding_text,
)

DEFAULT_GEMINI_EMBEDDING_MODEL = "gemini-embedding-2"


class SibylGeminiEmbedderConfig(EmbedderConfig):
    embedding_model: str = Field(default=DEFAULT_GEMINI_EMBEDDING_MODEL)
    api_key: str | None = None


class SibylGeminiEmbedder(EmbedderClient):
    def __init__(
        self,
        config: SibylGeminiEmbedderConfig | None = None,
        client: genai.Client | None = None,
    ) -> None:
        self.config = config or SibylGeminiEmbedderConfig()
        self.client = client or genai.Client(api_key=self.config.api_key)

    async def create(
        self,
        input_data: str | list[str] | Iterable[int] | Iterable[Iterable[int]],
    ) -> list[float]:
        text = self._coerce_text(input_data)
        return (await self._embed_texts([text], kind="query"))[0]

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        if not input_data_list:
            return []

        embeddings = await self._embed_texts(input_data_list, kind="document")
        if len(embeddings) == len(input_data_list):
            return embeddings

        return [
            (await self._embed_texts([text], kind="document"))[0]
            for text in input_data_list
        ]

    @staticmethod
    def _coerce_text(
        input_data: str | list[str] | Iterable[int] | Iterable[Iterable[int]],
    ) -> str:
        if isinstance(input_data, str):
            return input_data
        if isinstance(input_data, list) and all(isinstance(item, str) for item in input_data):
            return "\n".join(cast("list[str]", input_data))
        raise TypeError("Gemini embeddings require text input")

    async def _embed_texts(
        self, texts: list[str], *, kind: GeminiInputKind
    ) -> list[list[float]]:
        formatted = [
            format_gemini_embedding_text(
                text,
                model=self.config.embedding_model,
                kind=kind,
            )
            for text in texts
        ]
        result = await self.client.aio.models.embed_content(
            model=self.config.embedding_model,
            contents=cast(Any, build_gemini_contents(formatted)),
            config=types.EmbedContentConfig(output_dimensionality=self.config.embedding_dim),
        )

        if not result.embeddings:
            raise ValueError("No embeddings returned from Gemini API")

        embeddings = []
        for embedding in result.embeddings:
            if not embedding.values:
                raise ValueError("Empty embedding returned from Gemini API")
            embeddings.append(embedding.values)
        return embeddings
