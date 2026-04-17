"""Legacy admin adapters backed by the current relational runtime."""

from __future__ import annotations

from typing import Any

import structlog

log = structlog.get_logger()


async def recover_legacy_stuck_sources() -> dict[str, Any]:
    """Recover sources stuck in IN_PROGRESS state after server restart."""
    from sqlalchemy import func, select
    from sqlmodel import col

    from sibyl.db import CrawledDocument, CrawlSource, DocumentChunk, get_session
    from sibyl.db.models import CrawlStatus

    recovered = 0
    completed = 0
    reset_to_pending = 0

    try:
        async with get_session() as session:
            result = await session.execute(
                select(CrawlSource).where(col(CrawlSource.crawl_status) == CrawlStatus.IN_PROGRESS)
            )
            stuck_sources = list(result.scalars().all())

            if not stuck_sources:
                log.info("No stuck sources found during startup recovery")
                return {"recovered": 0, "completed": 0, "reset_to_pending": 0}

            log.warning(
                "Found stuck IN_PROGRESS sources",
                count=len(stuck_sources),
                sources=[source.name for source in stuck_sources],
            )

            for source in stuck_sources:
                doc_count_result = await session.execute(
                    select(func.count(CrawledDocument.id)).where(
                        col(CrawledDocument.source_id) == source.id
                    )
                )
                doc_count = doc_count_result.scalar() or 0

                chunk_count_result = await session.execute(
                    select(func.count(DocumentChunk.id))
                    .join(CrawledDocument)
                    .where(col(CrawledDocument.source_id) == source.id)
                )
                chunk_count = chunk_count_result.scalar() or 0

                old_status = source.crawl_status

                if doc_count > 0:
                    source.crawl_status = CrawlStatus.COMPLETED
                    source.document_count = doc_count
                    source.chunk_count = chunk_count
                    completed += 1
                else:
                    source.crawl_status = CrawlStatus.PENDING
                    reset_to_pending += 1

                source.current_job_id = None

                log.info(
                    "Recovered stuck source",
                    source_name=source.name,
                    old_status=old_status.value,
                    new_status=source.crawl_status.value,
                    doc_count=doc_count,
                )
                recovered += 1

        log.info(
            "Startup recovery complete",
            recovered=recovered,
            completed=completed,
            reset_to_pending=reset_to_pending,
        )

    except Exception as exc:
        log.exception("Startup recovery failed", error=str(exc))

    return {
        "recovered": recovered,
        "completed": completed,
        "reset_to_pending": reset_to_pending,
    }
