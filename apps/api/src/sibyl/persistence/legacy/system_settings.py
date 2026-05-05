"""Legacy system-setting adapters backed by the relational runtime."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import select

from sibyl.db.models import SystemSetting as DbSystemSetting
from sibyl.persistence.settings_types import SystemSettingRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _record_from_model(setting: DbSystemSetting) -> SystemSettingRecord:
    return SystemSettingRecord(
        key=setting.key,
        value=setting.value,
        is_secret=setting.is_secret,
        description=setting.description,
        created_at=setting.created_at,
        updated_at=setting.updated_at,
    )


def _model_from_record(setting: SystemSettingRecord) -> DbSystemSetting:
    model = DbSystemSetting(
        key=setting.key,
        value=setting.value,
        is_secret=setting.is_secret,
        description=setting.description,
    )
    if setting.created_at is not None:
        model.created_at = setting.created_at
    if setting.updated_at is not None:
        model.updated_at = setting.updated_at
    return model


async def get_system_setting(
    session: AsyncSession,
    *,
    key: str,
) -> SystemSettingRecord | None:
    result = await session.execute(select(DbSystemSetting).where(DbSystemSetting.key == key))
    setting = result.scalar_one_or_none()
    return _record_from_model(setting) if setting is not None else None


async def list_system_settings(session: AsyncSession) -> list[SystemSettingRecord]:
    result = await session.execute(select(DbSystemSetting))
    return [_record_from_model(setting) for setting in result.scalars()]


async def save_system_setting(
    session: AsyncSession,
    *,
    setting: SystemSettingRecord,
) -> SystemSettingRecord:
    result = await session.execute(
        select(DbSystemSetting).where(DbSystemSetting.key == setting.key)
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        model = _model_from_record(setting)
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return _record_from_model(model)

    existing.value = setting.value
    existing.is_secret = setting.is_secret
    existing.description = setting.description
    await session.flush()
    await session.refresh(existing)
    return _record_from_model(existing)


async def delete_system_setting(
    session: AsyncSession,
    *,
    key: str,
) -> bool:
    result = await session.execute(select(DbSystemSetting).where(DbSystemSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting is None:
        return False
    await session.delete(setting)
    return True
