"""Embedding provider helpers."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "CachedNativeEmbeddingProvider": (
        "sibyl_core.embeddings.native",
        "CachedNativeEmbeddingProvider",
    ),
    "DeterministicNativeEmbeddingProvider": (
        "sibyl_core.embeddings.native",
        "DeterministicNativeEmbeddingProvider",
    ),
    "GeminiInputKind": ("sibyl_core.embeddings.gemini", "GeminiInputKind"),
    "GeminiNativeEmbeddingProvider": (
        "sibyl_core.embeddings.native",
        "GeminiNativeEmbeddingProvider",
    ),
    "NativeEmbeddingInputKind": ("sibyl_core.embeddings.native", "NativeEmbeddingInputKind"),
    "NativeEmbeddingMetadata": ("sibyl_core.embeddings.native", "NativeEmbeddingMetadata"),
    "NativeEmbeddingProvider": ("sibyl_core.embeddings.native", "NativeEmbeddingProvider"),
    "NativeEmbeddingProviderName": (
        "sibyl_core.embeddings.native",
        "NativeEmbeddingProviderName",
    ),
    "OpenAINativeEmbeddingProvider": (
        "sibyl_core.embeddings.native",
        "OpenAINativeEmbeddingProvider",
    ),
    "build_gemini_contents": ("sibyl_core.embeddings.gemini", "build_gemini_contents"),
    "create_native_embedding_provider": (
        "sibyl_core.embeddings.native",
        "create_native_embedding_provider",
    ),
    "format_gemini_embedding_text": (
        "sibyl_core.embeddings.gemini",
        "format_gemini_embedding_text",
    ),
    "is_gemini_embedding_2": ("sibyl_core.embeddings.gemini", "is_gemini_embedding_2"),
    "native_embedding_cache_key": (
        "sibyl_core.embeddings.native",
        "native_embedding_cache_key",
    ),
    "native_entity_embedding_text": (
        "sibyl_core.embeddings.native",
        "native_entity_embedding_text",
    ),
    "native_relationship_embedding_text": (
        "sibyl_core.embeddings.native",
        "native_relationship_embedding_text",
    ),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
