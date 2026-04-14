"""Tests for job route visibility helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException

from sibyl.api.routes.jobs import _job_visible_to_org, cancel_job, list_jobs


class TestJobVisibility:
    @pytest.mark.asyncio
    async def test_source_jobs_use_embedded_org_metadata_without_db_lookup(self) -> None:
        org = SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000111"))
        session = AsyncMock()
        job = SimpleNamespace(
            function="crawl_source",
            args=("00000000-0000-0000-0000-000000000222",),
            kwargs={"organization_id": str(org.id)},
        )

        assert await _job_visible_to_org(job, org=org, session=session) is True
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_source_jobs_hide_other_org_metadata_without_db_lookup(self) -> None:
        org = SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000111"))
        session = AsyncMock()
        job = SimpleNamespace(
            function="sync_source",
            args=("00000000-0000-0000-0000-000000000222",),
            kwargs={"organization_id": "00000000-0000-0000-0000-000000000999"},
        )

        assert await _job_visible_to_org(job, org=org, session=session) is False
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_legacy_source_jobs_fall_back_to_db_lookup(self) -> None:
        org = SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000111"))
        result = MagicMock()
        result.scalar_one_or_none.return_value = object()
        session = AsyncMock()
        session.execute.return_value = result
        job = SimpleNamespace(
            function="crawl_source",
            args=("00000000-0000-0000-0000-000000000222",),
            kwargs=None,
        )

        assert await _job_visible_to_org(job, org=org, session=session) is True
        session.execute.assert_awaited_once()


class TestListJobsRoute:
    @pytest.mark.asyncio
    async def test_list_jobs_batches_legacy_source_visibility_checks(self) -> None:
        org = SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000111"))
        session = AsyncMock()

        visible_legacy_source_id = UUID("00000000-0000-0000-0000-000000000222")
        invisible_legacy_source_id = UUID("00000000-0000-0000-0000-000000000333")
        embedded_visible_source_id = UUID("00000000-0000-0000-0000-000000000444")
        embedded_hidden_source_id = UUID("00000000-0000-0000-0000-000000000555")

        jobs = [
            SimpleNamespace(
                job_id="crawl:legacy-visible",
                function="crawl_source",
                status=SimpleNamespace(value="queued"),
                enqueue_time=None,
                start_time=None,
                finish_time=None,
                error=None,
                args=(str(visible_legacy_source_id),),
                kwargs=None,
            ),
            SimpleNamespace(
                job_id="sync:legacy-hidden",
                function="sync_source",
                status=SimpleNamespace(value="queued"),
                enqueue_time=None,
                start_time=None,
                finish_time=None,
                error=None,
                args=(str(invisible_legacy_source_id),),
                kwargs=None,
            ),
            SimpleNamespace(
                job_id="crawl:embedded-visible",
                function="crawl_source",
                status=SimpleNamespace(value="queued"),
                enqueue_time=None,
                start_time=None,
                finish_time=None,
                error=None,
                args=(str(embedded_visible_source_id),),
                kwargs={"organization_id": str(org.id)},
            ),
            SimpleNamespace(
                job_id="crawl:embedded-hidden",
                function="crawl_source",
                status=SimpleNamespace(value="queued"),
                enqueue_time=None,
                start_time=None,
                finish_time=None,
                error=None,
                args=(str(embedded_hidden_source_id),),
                kwargs={"organization_id": "00000000-0000-0000-0000-000000000999"},
            ),
            SimpleNamespace(
                job_id="other",
                function="create_entity",
                status=SimpleNamespace(value="queued"),
                enqueue_time=None,
                start_time=None,
                finish_time=None,
                error=None,
                args=(),
                kwargs=None,
            ),
        ]

        result = MagicMock()
        result.scalars.return_value.all.return_value = [visible_legacy_source_id]
        session.execute.return_value = result

        with patch("sibyl.jobs.queue.list_jobs", AsyncMock(return_value=jobs)):
            response = await list_jobs(org=org, session=session)

        session.execute.assert_awaited_once()
        assert [job["job_id"] for job in response["jobs"]] == [
            "crawl:legacy-visible",
            "crawl:embedded-visible",
        ]
        assert response["total"] == 2


class TestCancelJobRoute:
    @pytest.mark.asyncio
    async def test_cancel_job_preserves_not_found_for_invisible_job(self) -> None:
        org = SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000111"))
        session = AsyncMock()
        job = SimpleNamespace(job_id="crawl:source-123")

        with (
            patch("sibyl.jobs.queue.get_job_status", AsyncMock(return_value=job)),
            patch("sibyl.api.routes.jobs._job_visible_to_org", AsyncMock(return_value=False)),
            pytest.raises(HTTPException) as exc_info,
        ):
            await cancel_job("crawl:source-123", org=org, session=session)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Job not found: crawl:source-123"
