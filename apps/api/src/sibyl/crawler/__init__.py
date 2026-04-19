"""Sibyl crawler module - Crawl4AI-powered documentation ingestion.

This module provides:
- Web crawling with Crawl4AI
- llms.txt discovery and parsing for AI-friendly content
- Smart chunking for RAG retrieval
- Embedding generation with OpenAI
- Full ingestion pipeline

Usage:
    from sibyl.crawler import ingest_documentation

    stats = await ingest_documentation(
        name="FastAPI Docs",
        url="https://fastapi.tiangolo.com",
        max_pages=50,
    )
    print(f"Ingested {stats.documents_stored} documents")
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

from sibyl.crawler.chunker import (
    Chunk,
    ChunkStrategy,
    DocumentChunker,
    chunk_document,
)
from sibyl.crawler.discovery import (
    DiscoveryResult,
    DiscoveryService,
    is_llms_variant,
)
from sibyl.crawler.embedder import (
    EmbeddingService,
    embed_chunks,
    embed_text,
    get_embedding_service,
)
from sibyl.crawler.llms_parser import (
    LLMsSection,
    parse_llms_full,
)
from sibyl.crawler.local import LocalFileCrawler

if TYPE_CHECKING:
    from sibyl.crawler.pipeline import (
        IngestionPipeline,
        IngestionStats,
        ingest_documentation,
        reingest_source,
    )
    from sibyl.crawler.service import CrawlerService, create_source, get_source_by_url, list_sources

__all__ = [
    # Pipeline
    "IngestionPipeline",
    "IngestionStats",
    "ingest_documentation",
    "reingest_source",
    # Crawler
    "CrawlerService",
    "LocalFileCrawler",
    "create_source",
    "get_source_by_url",
    "list_sources",
    # Discovery
    "DiscoveryService",
    "DiscoveryResult",
    "is_llms_variant",
    # llms.txt Parser
    "LLMsSection",
    "parse_llms_full",
    # Chunker
    "Chunk",
    "ChunkStrategy",
    "DocumentChunker",
    "chunk_document",
    # Embedder
    "EmbeddingService",
    "embed_chunks",
    "embed_text",
    "get_embedding_service",
]

_LAZY_EXPORTS = {
    "IngestionPipeline": ("sibyl.crawler.pipeline", "IngestionPipeline"),
    "IngestionStats": ("sibyl.crawler.pipeline", "IngestionStats"),
    "ingest_documentation": ("sibyl.crawler.pipeline", "ingest_documentation"),
    "reingest_source": ("sibyl.crawler.pipeline", "reingest_source"),
    "CrawlerService": ("sibyl.crawler.service", "CrawlerService"),
    "create_source": ("sibyl.crawler.service", "create_source"),
    "get_source_by_url": ("sibyl.crawler.service", "get_source_by_url"),
    "list_sources": ("sibyl.crawler.service", "list_sources"),
}


def __getattr__(name: str) -> Any:
    module_name, attr_name = _LAZY_EXPORTS.get(name, (None, None))
    if not module_name or not attr_name:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
