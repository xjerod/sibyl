"""Shared backup runtime DTOs."""

from __future__ import annotations

from dataclasses import dataclass

from sibyl.db.models import Backup


@dataclass(frozen=True, slots=True)
class BackupListResult:
    backups: list[Backup]
    total: int


LegacyBackupList = BackupListResult
