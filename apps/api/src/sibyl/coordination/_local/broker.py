"""Local broker placeholder for single-process coordination."""

from __future__ import annotations

from typing import Any, NoReturn
from uuid import UUID

from arq.connections import RedisSettings

from sibyl.coordination.broker import JobInfo

LOCAL_BROKER_ERROR = "Local job broker is not implemented yet"


class LocalQueueBroker:
    """Stub broker until local job execution lands."""

    async def startup(self) -> None:
        """Initialize the local broker."""

    async def shutdown(self) -> None:
        """Shutdown the local broker."""

    async def health(self) -> dict[str, Any]:
        """Report local broker status."""
        return {
            "status": "degraded",
            "error": LOCAL_BROKER_ERROR,
            "queue_healthy": False,
            "worker_healthy": False,
            "queue_depth": 0,
        }

    def get_redis_settings(self) -> RedisSettings:
        """Redis settings are unavailable for local mode."""
        self._raise_unsupported()

    async def get_pool(self) -> Any:
        """Redis pools are unavailable for local mode."""
        self._raise_unsupported()

    async def close_pool(self) -> None:
        """No pool exists in local mode."""

    async def enqueue_crawl(
        self,
        source_id: str | UUID,
        *,
        organization_id: str | None = None,
        max_pages: int = 100,
        max_depth: int = 3,
        generate_embeddings: bool = True,
        force: bool = False,
    ) -> str:
        self._raise_unsupported()

    async def enqueue_sync(
        self,
        source_id: str | UUID,
        *,
        organization_id: str | None = None,
    ) -> str:
        self._raise_unsupported()

    async def enqueue_create_entity(
        self,
        entity_id: str,
        entity_data: dict[str, Any],
        entity_type: str,
        group_id: str,
        relationships: list[dict[str, Any]] | None = None,
        auto_link_params: dict[str, Any] | None = None,
    ) -> str:
        self._raise_unsupported()

    async def enqueue_update_entity(
        self,
        entity_id: str,
        updates: dict[str, Any],
        entity_type: str,
        group_id: str,
    ) -> str:
        self._raise_unsupported()

    async def enqueue_create_learning_episode(
        self,
        task_data: dict[str, Any],
        group_id: str,
    ) -> str:
        self._raise_unsupported()

    async def enqueue_create_learning_procedure(
        self,
        task_data: dict[str, Any],
        group_id: str,
    ) -> str:
        self._raise_unsupported()

    async def enqueue_update_task(
        self,
        task_id: str,
        updates: dict[str, Any],
        group_id: str,
        epic_id: str | None = None,
        new_status: str | None = None,
        add_depends_on: list[str] | None = None,
        remove_depends_on: list[str] | None = None,
    ) -> str:
        self._raise_unsupported()

    async def get_job_status(self, job_id: str) -> JobInfo:
        self._raise_unsupported()

    async def list_jobs(self, *, function: str | None = None, limit: int = 50) -> list[JobInfo]:
        self._raise_unsupported()

    async def cancel_job(self, job_id: str) -> bool:
        self._raise_unsupported()

    async def enqueue_backup(
        self,
        organization_id: str,
        *,
        include_postgres: bool = True,
        include_graph: bool = True,
        backup_id: str | None = None,
    ) -> str:
        self._raise_unsupported()

    async def enqueue_backup_cleanup(
        self,
        *,
        retention_days: int | None = None,
    ) -> str:
        self._raise_unsupported()

    async def enqueue_consolidation(
        self,
        group_id: str,
        *,
        similarity_threshold: float = 0.90,
        max_merges_per_run: int = 50,
    ) -> str:
        self._raise_unsupported()

    async def enqueue_priority_decay(
        self,
        group_id: str,
        *,
        min_age_days: int = 180,
        max_archives_per_run: int = 100,
    ) -> str:
        self._raise_unsupported()

    def _raise_unsupported(self) -> NoReturn:
        raise RuntimeError(LOCAL_BROKER_ERROR)
