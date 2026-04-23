"""Shared backup runtime DTOs."""

from __future__ import annotations

from dataclasses import dataclass

from sibyl.db.models import Backup


@dataclass(frozen=True, slots=True)
class BackupListResult:
    backups: list[Backup]
    total: int


@dataclass(frozen=True, slots=True)
class BackupRuntimeOptions:
    include_database_dump: bool
    include_graph: bool
    include_auth_snapshot: bool
    include_content_snapshot: bool
    database_dump_supported: bool
    archive_contents: tuple[str, ...]

    @property
    def include_postgres(self) -> bool:
        return self.include_database_dump

    @property
    def postgres_dump_supported(self) -> bool:
        return self.database_dump_supported


def resolve_requested_database_dump(
    *,
    include_database_dump: bool | None = None,
    include_postgres: bool | None = None,
) -> bool | None:
    if include_database_dump is not None:
        return include_database_dump
    return include_postgres


def resolve_backup_runtime_options(
    *,
    store: str,
    auth_store: str,
    include_database_dump: bool | None = None,
    include_graph: bool = True,
) -> BackupRuntimeOptions:
    database_dump_supported = not (store == "surreal" and auth_store == "surreal")
    include_database_dump = (True if include_database_dump is None else include_database_dump) and (
        database_dump_supported
    )
    include_auth_snapshot = auth_store == "surreal"
    include_content_snapshot = store == "surreal"

    contents: list[str] = []
    if include_database_dump:
        contents.append("postgres.sql")
    if include_auth_snapshot:
        contents.append("auth.json")
    if include_content_snapshot:
        contents.append("content.json")
    if include_graph:
        contents.append("graph.json")
    contents.append("metadata.json")

    return BackupRuntimeOptions(
        include_database_dump=include_database_dump,
        include_graph=include_graph,
        include_auth_snapshot=include_auth_snapshot,
        include_content_snapshot=include_content_snapshot,
        database_dump_supported=database_dump_supported,
        archive_contents=tuple(contents),
    )


LegacyBackupList = BackupListResult
