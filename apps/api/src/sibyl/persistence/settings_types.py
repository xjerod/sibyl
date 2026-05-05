"""Runtime-neutral system setting records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class SystemSettingRecord:
    key: str
    value: str
    is_secret: bool = False
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


__all__ = ["SystemSettingRecord"]
