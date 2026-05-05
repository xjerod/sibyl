"""Shared content runtime DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from sibyl_core.models import ChunkType, CrawlStatus, SourceType

type ContentSession = object


class CrawlSourceRecord(Protocol):
    id: UUID
    organization_id: UUID
    name: str
    url: str
    source_type: SourceType
    description: str | None
    crawl_depth: int
    crawl_status: CrawlStatus
    document_count: int
    chunk_count: int
    current_job_id: str | None
    last_crawled_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    include_patterns: list[str] | None
    exclude_patterns: list[str] | None
    tags: list[str]
    categories: list[str]
    favicon_url: str | None


class CrawledDocumentRecord(Protocol):
    id: UUID
    source_id: UUID
    url: str
    title: str
    raw_content: str
    content: str
    content_hash: str
    word_count: int
    token_count: int
    has_code: bool
    is_index: bool
    depth: int
    crawled_at: datetime
    created_at: datetime
    updated_at: datetime
    headings: list[str] | None
    code_languages: list[str] | None
    section_path: list[str] | None


class DocumentChunkRecord(Protocol):
    id: UUID
    document_id: UUID
    content: str
    context: str | None
    chunk_type: ChunkType
    chunk_index: int
    heading_path: list[str] | None
    language: str | None
    has_entities: bool
    entity_ids: list[str] | None
    created_at: datetime
    updated_at: datetime


type RAGSearchRow = tuple[DocumentChunkRecord, CrawledDocumentRecord, str, UUID, float]
type CodeExampleSearchRow = tuple[
    DocumentChunkRecord, CrawledDocumentRecord, UUID, str, float
]
type HybridSearchRow = tuple[
    DocumentChunkRecord, CrawledDocumentRecord, str, UUID, float, float
]


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class CrawlStats:
    total_sources: int
    total_documents: int
    total_chunks: int
    chunks_with_embeddings: int
    sources_by_status: dict[str, int]


@dataclass(frozen=True)
class RawCaptureRecord:
    organization_id: UUID
    title: str
    raw_content: str
    entity_type: str
    entity_id: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
    capture_surface: str | None = None
    created_by_user_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utcnow_naive)


@dataclass(frozen=True)
class DocumentEntityRecord:
    """Resolved document-backed entity payload for entity routes."""

    chunk_id: UUID
    document_id: UUID
    source_id: UUID
    source_name: str
    source_url: str
    document_title: str
    document_url: str
    chunk_index: int
    chunk_type: ChunkType | None
    heading_path: tuple[str, ...]
    language: str | None
    content: str
    created_at: datetime
    updated_at: datetime


__all__ = [
    "CodeExampleSearchRow",
    "ContentSession",
    "CrawledDocumentRecord",
    "CrawlSourceRecord",
    "CrawlStats",
    "DocumentChunkRecord",
    "DocumentEntityRecord",
    "HybridSearchRow",
    "RAGSearchRow",
    "RawCaptureRecord",
]
