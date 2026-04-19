"""Legacy relational helpers for crawler route queries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlmodel import col

from sibyl.db import CrawledDocument, CrawlSource, DocumentChunk


@dataclass(frozen=True)
class LegacyCrawlStats:
    total_sources: int
    total_documents: int
    total_chunks: int
    chunks_with_embeddings: int
    sources_by_status: dict[str, int]


async def get_org_crawl_source(
    session: Any,
    *,
    source_id: UUID,
    organization_id: UUID,
) -> Any | None:
    """Fetch a crawl source scoped to an organization."""

    result = await session.execute(
        select(CrawlSource).where(
            col(CrawlSource.id) == source_id,
            col(CrawlSource.organization_id) == organization_id,
        )
    )
    return result.scalar_one_or_none()


async def get_crawl_stats_payload(
    session: Any,
    *,
    organization_id: UUID,
) -> LegacyCrawlStats:
    """Aggregate crawl stats for an organization."""

    sources_result = await session.execute(
        select(func.count(CrawlSource.id)).where(col(CrawlSource.organization_id) == organization_id)
    )
    total_sources = sources_result.scalar() or 0

    docs_result = await session.execute(
        select(func.count(CrawledDocument.id))
        .join(CrawlSource, col(CrawledDocument.source_id) == col(CrawlSource.id))
        .where(col(CrawlSource.organization_id) == organization_id)
    )
    total_documents = docs_result.scalar() or 0

    chunks_result = await session.execute(
        select(func.count(DocumentChunk.id))
        .join(CrawledDocument, col(DocumentChunk.document_id) == col(CrawledDocument.id))
        .join(CrawlSource, col(CrawledDocument.source_id) == col(CrawlSource.id))
        .where(col(CrawlSource.organization_id) == organization_id)
    )
    total_chunks = chunks_result.scalar() or 0

    embedded_result = await session.execute(
        select(func.count(DocumentChunk.id))
        .join(CrawledDocument, col(DocumentChunk.document_id) == col(CrawledDocument.id))
        .join(CrawlSource, col(CrawledDocument.source_id) == col(CrawlSource.id))
        .where(
            col(CrawlSource.organization_id) == organization_id,
            col(DocumentChunk.embedding).is_not(None),
        )
    )
    chunks_with_embeddings = embedded_result.scalar() or 0

    status_result = await session.execute(
        select(
            col(CrawlSource.crawl_status),
            func.count(col(CrawlSource.id)),
        )
        .where(col(CrawlSource.organization_id) == organization_id)
        .group_by(col(CrawlSource.crawl_status))
    )
    sources_by_status = {
        str(status.value) if hasattr(status, "value") else str(status): count
        for status, count in status_result.all()
    }

    return LegacyCrawlStats(
        total_sources=total_sources,
        total_documents=total_documents,
        total_chunks=total_chunks,
        chunks_with_embeddings=chunks_with_embeddings,
        sources_by_status=sources_by_status,
    )


async def list_crawled_documents_for_org(
    session: Any,
    *,
    organization_id: UUID,
    limit: int,
    offset: int,
) -> tuple[list[Any], int]:
    """List paginated documents for an organization."""

    query = (
        select(CrawledDocument)
        .join(CrawlSource, col(CrawledDocument.source_id) == col(CrawlSource.id))
        .where(col(CrawlSource.organization_id) == organization_id)
        .order_by(col(CrawledDocument.crawled_at).desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(query)
    documents = list(result.scalars().all())

    count_result = await session.execute(
        select(func.count(CrawledDocument.id))
        .join(CrawlSource, col(CrawledDocument.source_id) == col(CrawlSource.id))
        .where(col(CrawlSource.organization_id) == organization_id)
    )
    total = count_result.scalar() or 0
    return documents, total


async def get_crawled_document_for_org(
    session: Any,
    *,
    document_id: UUID,
    organization_id: UUID,
) -> Any | None:
    """Fetch a crawled document scoped to an organization."""

    result = await session.execute(
        select(CrawledDocument)
        .join(CrawlSource, col(CrawledDocument.source_id) == col(CrawlSource.id))
        .where(
            col(CrawledDocument.id) == document_id,
            col(CrawlSource.organization_id) == organization_id,
        )
    )
    return result.scalar_one_or_none()


async def list_document_chunks(
    session: Any,
    *,
    document_id: UUID,
) -> list[Any]:
    """List ordered chunks for a document."""

    result = await session.execute(
        select(DocumentChunk)
        .where(col(DocumentChunk.document_id) == document_id)
        .order_by(col(DocumentChunk.chunk_index))
    )
    return list(result.scalars().all())


async def list_source_documents_page(
    session: Any,
    *,
    source_id: UUID,
    limit: int,
    offset: int,
) -> tuple[list[Any], int]:
    """List paginated documents for a source."""

    query = (
        select(CrawledDocument)
        .where(col(CrawledDocument.source_id) == source_id)
        .order_by(col(CrawledDocument.crawled_at).desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(query)
    documents = list(result.scalars().all())

    count_result = await session.execute(
        select(func.count(CrawledDocument.id)).where(col(CrawledDocument.source_id) == source_id)
    )
    total = count_result.scalar() or 0
    return documents, total


async def list_source_chunks(
    session: Any,
    *,
    source_id: UUID,
) -> list[Any]:
    """List all chunks belonging to a source."""

    result = await session.execute(
        select(DocumentChunk)
        .join(CrawledDocument, col(DocumentChunk.document_id) == col(CrawledDocument.id))
        .where(col(CrawledDocument.source_id) == source_id)
    )
    return list(result.scalars().all())


async def list_source_documents(
    session: Any,
    *,
    source_id: UUID,
) -> list[Any]:
    """List all documents belonging to a source."""

    result = await session.execute(
        select(CrawledDocument).where(col(CrawledDocument.source_id) == source_id)
    )
    return list(result.scalars().all())


async def count_source_documents(
    session: Any,
    *,
    source_id: UUID,
) -> int:
    """Count documents for a source."""

    result = await session.execute(
        select(func.count(CrawledDocument.id)).where(col(CrawledDocument.source_id) == source_id)
    )
    return result.scalar() or 0


async def count_source_chunks(
    session: Any,
    *,
    source_id: UUID,
) -> int:
    """Count chunks for a source."""

    result = await session.execute(
        select(func.count(DocumentChunk.id))
        .join(CrawledDocument, col(DocumentChunk.document_id) == col(CrawledDocument.id))
        .where(col(CrawledDocument.source_id) == source_id)
    )
    return result.scalar() or 0


async def get_source_sync_counts(
    session: Any,
    *,
    source_id: UUID,
) -> tuple[int, int]:
    """Return actual document and chunk totals for a source."""

    document_count = await count_source_documents(session, source_id=source_id)
    chunk_count = await count_source_chunks(session, source_id=source_id)
    return document_count, chunk_count


async def list_sources_for_graph_linking(
    session: Any,
    *,
    organization_id: UUID,
    source_id: UUID | None = None,
) -> list[Any]:
    """List sources to process for graph linking."""

    if source_id is not None:
        source = await get_org_crawl_source(
            session,
            source_id=source_id,
            organization_id=organization_id,
        )
        return [source] if source is not None else []

    result = await session.execute(
        select(CrawlSource).where(col(CrawlSource.organization_id) == organization_id)
    )
    return list(result.scalars().all())


async def list_unlinked_source_chunks(
    session: Any,
    *,
    source_id: UUID,
    limit: int,
) -> list[Any]:
    """List pending entity-linking chunks for a source."""

    result = await session.execute(
        select(DocumentChunk)
        .join(CrawledDocument, col(DocumentChunk.document_id) == col(CrawledDocument.id))
        .where(col(CrawledDocument.source_id) == source_id)
        .where(col(DocumentChunk.has_entities) == False)  # noqa: E712
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_remaining_unlinked_chunks(
    session: Any,
    *,
    organization_id: UUID,
    source_id: UUID | None = None,
) -> int:
    """Count remaining unlinked chunks for an organization or source."""

    query = (
        select(func.count(DocumentChunk.id))
        .join(CrawledDocument, col(CrawledDocument.id) == col(DocumentChunk.document_id))
        .join(CrawlSource, col(CrawlSource.id) == col(CrawledDocument.source_id))
        .where(col(CrawlSource.organization_id) == organization_id)
        .where(col(DocumentChunk.has_entities) == False)  # noqa: E712
    )
    if source_id is not None:
        query = query.where(col(CrawledDocument.source_id) == source_id)

    result = await session.execute(query)
    return result.scalar() or 0
