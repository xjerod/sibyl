from __future__ import annotations

import mailbox
from collections.abc import Iterator
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

import pytest

from sibyl.jobs import source_imports
from sibyl.jobs.worker import WorkerSettings
from sibyl_core.services.source_adapters import clear_source_adapters
from sibyl_core.services.surreal_content import MemoryScope, RawMemory


@pytest.fixture(autouse=True)
def _clear_registry() -> Iterator[None]:
    clear_source_adapters()
    yield
    clear_source_adapters()


def _write_mbox(path: Path) -> Path:
    message = EmailMessage()
    message["Message-ID"] = "<job-msg@example.com>"
    message["Subject"] = "Job import"
    message["Date"] = "Thu, 14 May 2026 12:34:00 -0700"
    message["From"] = "Bliss <bliss@example.com>"
    message["To"] = "Nova <nova@example.com>"
    message.set_content("the job path imports raw mailbox records")
    message.add_attachment(
        b"job attachment",
        maintype="text",
        subtype="plain",
        filename="job.txt",
    )

    box = mailbox.mbox(path)
    try:
        box.add(message)
        box.flush()
    finally:
        box.close()
    return path


@pytest.mark.asyncio
async def test_import_source_archive_imports_mbox_with_private_scope(tmp_path: Path) -> None:
    mbox_path = _write_mbox(tmp_path / "job.mbox")
    writes: list[dict[str, object]] = []

    async def fake_remember(**kwargs: object) -> RawMemory:
        writes.append(dict(kwargs))
        return RawMemory(
            id=f"raw-{len(writes)}",
            organization_id=str(kwargs["organization_id"]),
            source_id=str(kwargs["source_id"]),
            principal_id=str(kwargs["principal_id"]),
            memory_scope=kwargs["memory_scope"],
            scope_key=kwargs["scope_key"],
            title=str(kwargs["title"]),
            raw_content=str(kwargs["raw_content"]),
            tags=list(kwargs["tags"]),
            metadata=dict(kwargs["metadata"]),
            provenance=dict(kwargs["provenance"]),
            capture_surface=str(kwargs["capture_surface"]),
            entity_type=str(kwargs["entity_type"]),
            captured_at=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
            created_at=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
        )

    result = await source_imports.import_source_archive(
        {},
        str(mbox_path),
        organization_id="org-1",
        principal_id="user-1",
        remember=fake_remember,
    )

    assert result["adapter_name"] == "mbox"
    assert result["imported_count"] == 1
    assert result["skipped_count"] == 0
    assert result["checkpoint"]["done"] is True
    assert result["policy"]["target_memory_scope"] == "private"
    assert result["policy"]["requires_promotion_preview"] is False
    assert writes[0]["memory_scope"] is MemoryScope.PRIVATE
    assert result["raw_memory_ids"] == ["raw-1"]
    assert str(writes[0]["source_id"]).startswith("source-record:")
    source_metadata = writes[0]["metadata"]["source_record_metadata"]
    assert source_metadata["message_id"] == "job-msg@example.com"
    assert source_metadata["from"] == ["bliss@example.com"]
    assert writes[0]["metadata"]["attachment_count"] == 1


@pytest.mark.asyncio
async def test_import_source_archive_resumes_from_checkpoint(tmp_path: Path) -> None:
    first = EmailMessage()
    first["Message-ID"] = "<first@example.com>"
    first["Subject"] = "First"
    first.set_content("first body")
    second = EmailMessage()
    second["Message-ID"] = "<second@example.com>"
    second["Subject"] = "Second"
    second.set_content("second body")
    box = mailbox.mbox(tmp_path / "resume.mbox")
    try:
        box.add(first)
        box.add(second)
        box.flush()
    finally:
        box.close()

    async def fake_remember(**kwargs: object) -> RawMemory:
        return RawMemory(
            id=str(kwargs["source_id"]),
            organization_id=str(kwargs["organization_id"]),
            source_id=str(kwargs["source_id"]),
            principal_id=str(kwargs["principal_id"]),
            memory_scope=kwargs["memory_scope"],
            scope_key=kwargs["scope_key"],
            title=str(kwargs["title"]),
            raw_content=str(kwargs["raw_content"]),
            tags=list(kwargs["tags"]),
            metadata=dict(kwargs["metadata"]),
            provenance=dict(kwargs["provenance"]),
            capture_surface=str(kwargs["capture_surface"]),
            entity_type=str(kwargs["entity_type"]),
            captured_at=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
            created_at=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
        )

    first_result = await source_imports.import_source_archive(
        {},
        str(tmp_path / "resume.mbox"),
        organization_id="org-1",
        principal_id="user-1",
        batch_size=1,
        remember=fake_remember,
    )
    second_result = await source_imports.import_source_archive(
        {},
        str(tmp_path / "resume.mbox"),
        organization_id="org-1",
        principal_id="user-1",
        checkpoint=first_result["checkpoint"],
        batch_size=1,
        remember=fake_remember,
    )

    assert first_result["checkpoint"]["cursor"] == "1"
    assert first_result["checkpoint"]["done"] is False
    assert second_result["checkpoint"]["cursor"] is None
    assert second_result["checkpoint"]["done"] is True
    assert first_result["dedupe_keys"] != second_result["dedupe_keys"]


def test_worker_settings_registers_source_import_job() -> None:
    assert source_imports.import_source_archive in WorkerSettings.functions
