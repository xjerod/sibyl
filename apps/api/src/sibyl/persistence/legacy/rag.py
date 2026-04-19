"""Legacy relational helpers for RAG route queries."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlmodel import col

from sibyl.db import CrawledDocument, CrawlSource, DocumentChunk
from sibyl.db.models import ChunkType


async def search_rag_chunks(
    session: Any,
    *,
    query_embedding: list[float],
    organization_id: UUID | str,
    similarity_threshold: float,
    match_count: int,
    source_id: UUID | None = None,
    source_name: str | None = None,
) -> list[Any]:
    """Search document chunks by vector similarity."""

    similarity_expr = 1 - DocumentChunk.embedding.cosine_distance(query_embedding)
    query = (
        select(
            DocumentChunk,
            CrawledDocument,
            col(CrawlSource.name).label("source_name"),
            col(CrawlSource.id).label("source_id"),
            similarity_expr.label("similarity"),
        )
        .join(CrawledDocument, col(DocumentChunk.document_id) == col(CrawledDocument.id))
        .join(CrawlSource, col(CrawledDocument.source_id) == col(CrawlSource.id))
        .where(col(DocumentChunk.embedding).is_not(None))
        .where(col(CrawlSource.organization_id) == organization_id)
    )

    if source_id:
        query = query.where(col(CrawlSource.id) == source_id)
    elif source_name:
        query = query.where(col(CrawlSource.name).ilike(f"%{source_name}%"))

    query = (
        query.where(similarity_expr >= similarity_threshold)
        .order_by(similarity_expr.desc())
        .limit(match_count)
    )
    result = await session.execute(query)
    return result.all()


async def search_code_example_chunks(
    session: Any,
    *,
    query_embedding: list[float],
    organization_id: UUID | str,
    match_count: int,
    source_id: UUID | None = None,
    language: str | None = None,
) -> list[Any]:
    """Search code chunks by vector similarity."""

    similarity_expr = 1 - DocumentChunk.embedding.cosine_distance(query_embedding)
    query = (
        select(
            DocumentChunk,
            CrawledDocument,
            col(CrawlSource.id).label("source_id"),
            col(CrawlSource.name).label("source_name"),
            similarity_expr.label("similarity"),
        )
        .join(CrawledDocument, col(DocumentChunk.document_id) == col(CrawledDocument.id))
        .join(CrawlSource, col(CrawledDocument.source_id) == col(CrawlSource.id))
        .where(col(DocumentChunk.embedding).is_not(None))
        .where(col(DocumentChunk.chunk_type) == ChunkType.CODE)
        .where(col(CrawlSource.organization_id) == organization_id)
    )

    if source_id:
        query = query.where(col(CrawlSource.id) == source_id)

    if language:
        query = query.where(col(DocumentChunk.language).ilike(language))

    result = await session.execute(query.order_by(similarity_expr.desc()).limit(match_count))
    return result.all()


async def list_source_documents_page(
    session: Any,
    *,
    source_id: UUID,
    limit: int,
    offset: int,
    has_code: bool | None = None,
    is_index: bool | None = None,
) -> tuple[list[Any], int]:
    """List paginated documents for a source."""

    query = select(CrawledDocument).where(col(CrawledDocument.source_id) == source_id)

    if has_code is not None:
        query = query.where(col(CrawledDocument.has_code) == has_code)

    if is_index is not None:
        query = query.where(col(CrawledDocument.is_index) == is_index)

    count_query = select(func.count()).select_from(query.subquery())
    count_result = await session.execute(count_query)
    total = count_result.scalar() or 0

    result = await session.execute(
        query.order_by(col(CrawledDocument.title)).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


async def get_document_by_url_for_org(
    session: Any,
    *,
    url: str,
    organization_id: UUID | str,
) -> Any | None:
    """Fetch a document by URL scoped to the organization."""

    result = await session.execute(
        select(CrawledDocument)
        .join(CrawlSource, col(CrawledDocument.source_id) == col(CrawlSource.id))
        .where(col(CrawledDocument.url) == url)
        .where(col(CrawlSource.organization_id) == organization_id)
    )
    return result.scalar_one_or_none()


async def hybrid_search_chunks(
    session: Any,
    *,
    query_text: str,
    query_embedding: list[float],
    organization_id: UUID | str,
    similarity_threshold: float,
    match_count: int,
    source_id: UUID | None = None,
    source_name: str | None = None,
) -> list[Any]:
    """Run weighted hybrid vector and full-text search."""

    similarity_expr = 1 - DocumentChunk.embedding.cosine_distance(query_embedding)
    ts_query = func.plainto_tsquery("english", query_text)
    ts_vector = func.to_tsvector("english", DocumentChunk.content)
    fts_rank = func.ts_rank(ts_vector, ts_query)
    combined_score = similarity_expr * 0.7 + fts_rank * 0.3

    query = (
        select(
            DocumentChunk,
            CrawledDocument,
            col(CrawlSource.name).label("source_name"),
            col(CrawlSource.id).label("source_id"),
            similarity_expr.label("similarity"),
            fts_rank.label("fts_rank"),
        )
        .join(CrawledDocument, col(DocumentChunk.document_id) == col(CrawledDocument.id))
        .join(CrawlSource, col(CrawledDocument.source_id) == col(CrawlSource.id))
        .where(col(DocumentChunk.embedding).is_not(None))
        .where(col(CrawlSource.organization_id) == organization_id)
    )

    if source_id:
        query = query.where(col(CrawlSource.id) == source_id)
    elif source_name:
        query = query.where(col(CrawlSource.name).ilike(f"%{source_name}%"))

    result = await session.execute(
        query.where(similarity_expr >= similarity_threshold)
        .order_by(combined_score.desc())
        .limit(match_count)
    )
    return result.all()
