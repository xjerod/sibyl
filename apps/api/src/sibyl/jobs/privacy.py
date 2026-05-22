"""Privacy lifecycle jobs."""

from __future__ import annotations

from typing import Any

import structlog

from sibyl.persistence.content_runtime import purge_due_deleted_raw_captures

log = structlog.get_logger()


async def purge_due_deleted_personal_memories(ctx: dict[str, Any]) -> dict[str, int]:
    del ctx
    purged = await purge_due_deleted_raw_captures()
    log.info("deleted_personal_memories_purged", count=purged)
    return {"purged": purged}
