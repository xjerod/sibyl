"""Legacy backup adapters backed by the relational runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from sibyl.db.connection import get_session
from sibyl.db.models import Backup, BackupSettings, BackupStatus


@dataclass(frozen=True, slots=True)
class LegacyBackupList:
    backups: list[Backup]
    total: int


async def get_or_create_legacy_backup_settings(
    session: AsyncSession, org_id: UUID
) -> BackupSettings:
    """Get or create backup settings for an organization."""
    result = await session.execute(
        select(BackupSettings).where(col(BackupSettings.organization_id) == org_id)
    )
    settings = result.scalar_one_or_none()

    if settings is None:
        settings = BackupSettings(organization_id=org_id)
        session.add(settings)
        await session.flush()

    return settings


async def get_legacy_backup_settings(org_id: UUID) -> BackupSettings:
    """Return persisted backup settings for an organization."""
    async with get_session() as session:
        settings = await get_or_create_legacy_backup_settings(session, org_id)
        await session.commit()
        return settings


async def update_legacy_backup_settings(
    org_id: UUID,
    *,
    enabled: bool | None = None,
    schedule: str | None = None,
    retention_days: int | None = None,
    include_postgres: bool | None = None,
    include_graph: bool | None = None,
) -> BackupSettings:
    """Persist backup setting changes for an organization."""
    async with get_session() as session:
        settings = await get_or_create_legacy_backup_settings(session, org_id)

        if enabled is not None:
            settings.enabled = enabled
        if schedule is not None:
            settings.schedule = schedule
        if retention_days is not None:
            settings.retention_days = retention_days
        if include_postgres is not None:
            settings.include_postgres = include_postgres
        if include_graph is not None:
            settings.include_graph = include_graph

        settings.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await session.commit()
        return settings


async def create_legacy_backup_record(
    *,
    org_id: UUID,
    backup_id: str,
    include_postgres: bool,
    include_graph: bool,
    created_by_user_id: UUID | None,
) -> Backup:
    """Create a pending backup record for an organization."""
    async with get_session() as session:
        backup = Backup(
            organization_id=org_id,
            backup_id=backup_id,
            status=BackupStatus.PENDING.value,
            include_postgres=include_postgres,
            include_graph=include_graph,
            triggered_by="manual",
            created_by_user_id=created_by_user_id,
        )
        session.add(backup)
        await session.commit()
        await session.refresh(backup)
        return backup


async def attach_legacy_backup_job(record_id: UUID, job_id: str) -> Backup:
    """Attach a queued job identifier to a backup record."""
    async with get_session() as session:
        backup = await session.get(Backup, record_id)
        if backup is None:
            raise HTTPException(status_code=404, detail="Backup record not found")

        backup.job_id = job_id
        await session.commit()
        await session.refresh(backup)
        return backup


async def list_legacy_backups(org_id: UUID, *, limit: int, offset: int) -> LegacyBackupList:
    """List persisted backup records for an organization."""
    async with get_session() as session:
        count_result = await session.execute(
            select(Backup).where(col(Backup.organization_id) == org_id)
        )
        all_backups = count_result.scalars().all()

        result = await session.execute(
            select(Backup)
            .where(col(Backup.organization_id) == org_id)
            .order_by(col(Backup.created_at).desc())
            .limit(limit)
            .offset(offset)
        )
        return LegacyBackupList(backups=list(result.scalars().all()), total=len(all_backups))


async def get_legacy_backup(org_id: UUID, backup_id: str) -> Backup:
    """Return a persisted backup record or raise 404."""
    async with get_session() as session:
        result = await session.execute(
            select(Backup).where(
                col(Backup.organization_id) == org_id,
                col(Backup.backup_id) == backup_id,
            )
        )
        backup = result.scalar_one_or_none()

    if backup is None:
        raise HTTPException(status_code=404, detail=f"Backup not found: {backup_id}")
    return backup


async def get_legacy_backup_retention(org_id: UUID, requested_retention: int | None) -> int:
    """Resolve backup retention days from the request or stored settings."""
    if requested_retention is not None:
        return requested_retention

    settings = await get_legacy_backup_settings(org_id)
    return settings.retention_days


async def delete_legacy_backup_record(org_id: UUID, backup_id: str) -> Backup:
    """Delete a persisted backup record and return it."""
    async with get_session() as session:
        result = await session.execute(
            select(Backup).where(
                col(Backup.organization_id) == org_id,
                col(Backup.backup_id) == backup_id,
            )
        )
        backup = result.scalar_one_or_none()

        if backup is None:
            raise HTTPException(status_code=404, detail=f"Backup not found: {backup_id}")

        await session.delete(backup)
        await session.commit()
        return backup
