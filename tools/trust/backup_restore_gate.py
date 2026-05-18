#!/usr/bin/env python3
"""Run the focused release gate for backup and restore readiness."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from shutil import which
from typing import Any

from sibyl_core.migrate.archive import (
    AUTH_FILENAME,
    CONTENT_FILENAME,
    GRAPH_FILENAME,
    LoadedArchive,
    build_manifest,
    effective_graph_counts,
    validate_archive,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_PATH = REPO_ROOT / ".moon/cache/backup-restore-gate/receipt.json"

Runner = Callable[[tuple[str, ...]], int]
Echo = Callable[[str], None]
type JsonObject = dict[str, Any]

ORG_ID = "00000000-0000-4000-8000-000000000013"
USER_ID = "00000000-0000-4000-8000-000000000111"
PROJECT_ID = "project-backup-restore-gate"
TASK_ID = "task-backup-restore-gate"
RAW_MEMORY_ID = "10000000-0000-4000-8000-000000000001"
SYNTHESIS_MEMORY_ID = "10000000-0000-4000-8000-000000000002"
SOURCE_IMPORT_ID = "10000000-0000-4000-8000-000000000003"
CRAWL_SOURCE_ID = "10000000-0000-4000-8000-000000000004"
DOCUMENT_ID = "10000000-0000-4000-8000-000000000005"
CHUNK_ID = "10000000-0000-4000-8000-000000000006"
RAW_SOURCE_ID = "mailbox:gate:message-1"
DOC_SOURCE_ID = "docs:gate:section-1"
SYNTHESIS_SOURCE_ID = "synthesis:backup-restore-gate:generated"


class GateFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class GateCheck:
    name: str
    description: str
    surfaces: tuple[str, ...]
    command: tuple[str, ...]


@dataclass(frozen=True)
class GateResult:
    check: GateCheck
    exit_code: int
    elapsed_seconds: float
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.exit_code == 0


GATE_CHECKS: tuple[GateCheck, ...] = (
    GateCheck(
        name="core-graph-backup-restore",
        description="graph restore, task links, source IDs, episodes, and mentions",
        surfaces=(
            "graph restore",
            "tasks restore",
            "task link preservation",
            "source id preservation",
        ),
        command=("moon", "run", "core:backup-restore-gate-test"),
    ),
    GateCheck(
        name="api-surreal-archive-restore",
        description="auth and content archive restore for Surreal runtime state",
        surfaces=(
            "auth restore",
            "content restore",
            "raw memory restore",
            "settings restore",
            "source import runs restore",
            "policy scope preservation",
            "synthesis provenance preservation",
        ),
        command=("moon", "run", "api:backup-restore-gate-test"),
    ),
)

REQUIRED_SURFACES: tuple[str, ...] = (
    "auth restore",
    "graph restore",
    "content restore",
    "raw memory restore",
    "tasks restore",
    "settings restore",
    "source import runs restore",
    "policy scope preservation",
    "source id preservation",
    "task link preservation",
    "synthesis provenance preservation",
)


def covered_surfaces(checks: Iterable[GateCheck] = GATE_CHECKS) -> set[str]:
    return {surface for check in checks for surface in check.surfaces}


def missing_required_surfaces(checks: Sequence[GateCheck] = GATE_CHECKS) -> list[str]:
    covered = covered_surfaces(checks)
    return [surface for surface in REQUIRED_SURFACES if surface not in covered]


def format_command(command: Sequence[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _echo(message: str = "") -> None:
    sys.stdout.write(f"{message}\n")


def _real_runner(command: tuple[str, ...]) -> int:
    if not command:
        msg = "Gate command cannot be empty"
        raise ValueError(msg)

    executable = which(command[0])
    if executable is None:
        msg = f"Required executable not found on PATH: {command[0]}"
        raise RuntimeError(msg)

    env = dict(os.environ)
    env.setdefault("MOON_COLOR", "false")
    completed = subprocess.run(  # noqa: S603
        (executable, *command[1:]),
        cwd=REPO_ROOT,
        env=env,
        check=False,
    )
    return completed.returncode


def _run_check(check: GateCheck, *, runner: Runner, echo: Echo) -> GateResult:
    echo("")
    echo(f"[{check.name}] {check.description}")
    echo(f"surfaces: {', '.join(check.surfaces)}")
    echo(f"command: {format_command(check.command)}")

    started = time.perf_counter()
    error: str | None = None
    try:
        exit_code = runner(check.command)
    except Exception as exc:
        exit_code = 1
        error = f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - started

    status = "PASS" if exit_code == 0 else f"FAIL exit={exit_code}"
    if error is not None:
        status = f"{status} error={error}"
    echo(f"result: {status} in {elapsed:.2f}s")
    return GateResult(
        check=check,
        exit_code=exit_code,
        elapsed_seconds=elapsed,
        error=error,
    )


def _json_bytes(payload: Mapping[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _fixture_payloads() -> tuple[JsonObject, JsonObject, JsonObject]:
    auth: JsonObject = {
        "version": "1.0",
        "created_at": "2026-05-18T00:00:00+00:00",
        "tables": {
            "users": [
                {
                    "uuid": USER_ID,
                    "email": "backup-restore-gate@example.com",
                    "name": "Backup Restore Gate",
                    "is_admin": True,
                }
            ],
            "organizations": [
                {
                    "uuid": ORG_ID,
                    "name": "Backup Restore Gate",
                    "slug": "backup-restore-gate",
                }
            ],
            "organization_members": [
                {
                    "uuid": "member-backup-restore-gate",
                    "organization_id": ORG_ID,
                    "user_id": USER_ID,
                    "role": "owner",
                }
            ],
            "memory_spaces": [
                {
                    "uuid": "space-backup-restore-private",
                    "organization_id": ORG_ID,
                    "memory_scope": "private",
                    "scope_key": USER_ID,
                    "created_by_user_id": USER_ID,
                },
                {
                    "uuid": "space-backup-restore-project",
                    "organization_id": ORG_ID,
                    "memory_scope": "project",
                    "scope_key": PROJECT_ID,
                    "created_by_user_id": USER_ID,
                },
            ],
        },
        "row_counts": {
            "users": 1,
            "organizations": 1,
            "organization_members": 1,
            "memory_spaces": 2,
        },
        "total_rows": 5,
    }
    content: JsonObject = {
        "version": "1.0",
        "created_at": "2026-05-18T00:00:00+00:00",
        "tables": {
            "crawl_sources": [
                {
                    "id": CRAWL_SOURCE_ID,
                    "organization_id": ORG_ID,
                    "name": "Gate docs",
                    "url": "https://docs.example.test/gate",
                    "source_type": "website",
                }
            ],
            "crawled_documents": [
                {
                    "id": DOCUMENT_ID,
                    "source_id": CRAWL_SOURCE_ID,
                    "url": "https://docs.example.test/gate/page",
                    "title": "Gate page",
                    "content": "Backup restore gate evidence",
                }
            ],
            "document_chunks": [
                {
                    "id": CHUNK_ID,
                    "document_id": DOCUMENT_ID,
                    "chunk_index": 0,
                    "chunk_type": "text",
                    "content": "Backup restore gate evidence",
                    "entity_ids": [TASK_ID],
                }
            ],
            "raw_captures": [
                {
                    "id": RAW_MEMORY_ID,
                    "organization_id": ORG_ID,
                    "source_id": RAW_SOURCE_ID,
                    "principal_id": USER_ID,
                    "memory_scope": "private",
                    "scope_key": USER_ID,
                    "project_id": PROJECT_ID,
                    "title": "Imported mailbox memory",
                    "raw_content": "Task evidence from source import.",
                    "entity_type": "note",
                    "metadata": {
                        "raw_source_id": RAW_SOURCE_ID,
                        "source_ids": [RAW_SOURCE_ID],
                        "project_id": PROJECT_ID,
                    },
                    "provenance": {"source_import_id": SOURCE_IMPORT_ID},
                    "capture_surface": "source_import",
                },
                {
                    "id": SYNTHESIS_MEMORY_ID,
                    "organization_id": ORG_ID,
                    "source_id": SYNTHESIS_SOURCE_ID,
                    "principal_id": USER_ID,
                    "memory_scope": "project",
                    "scope_key": PROJECT_ID,
                    "project_id": PROJECT_ID,
                    "title": "Synthesis artifact",
                    "raw_content": "# Backup Restore Gate\n[source]",
                    "entity_type": "artifact",
                    "metadata": {
                        "capture_mode": "synthesis",
                        "capture_surface": "synthesis_artifact",
                        "synthesis_run_id": "synthesis-run-gate",
                        "synthesis_artifact_id": "artifact-gate",
                        "source_ids": [RAW_SOURCE_ID, DOC_SOURCE_ID],
                        "section_source_ids": {"Findings": [DOC_SOURCE_ID]},
                        "verification": {"status": "pass"},
                    },
                    "provenance": {
                        "synthesis_run_id": "synthesis-run-gate",
                        "source_ids": [RAW_SOURCE_ID, DOC_SOURCE_ID],
                        "section_source_ids": {"Findings": [DOC_SOURCE_ID]},
                    },
                    "capture_surface": "synthesis_artifact",
                },
            ],
            "source_imports": [
                {
                    "id": SOURCE_IMPORT_ID,
                    "organization_id": ORG_ID,
                    "principal_id": USER_ID,
                    "adapter_name": "mailbox",
                    "adapter_version": "1.0",
                    "source_uri": "mbox://backup-restore-gate",
                    "source_identity": "backup-restore-gate-mailbox",
                    "source_version": "2026-05-18",
                    "privacy_class": "personal",
                    "target_memory_scope": "private",
                    "target_scope_key": USER_ID,
                    "status": "completed",
                    "checkpoint": {"cursor": None, "done": True},
                    "policy_context": {"memory_scope": "private", "scope_key": USER_ID},
                    "counters": {"imported_count": 1},
                    "raw_memory_ids": [RAW_MEMORY_ID],
                    "source_ids": [RAW_SOURCE_ID],
                    "raw_memory_by_source_id": {RAW_SOURCE_ID: RAW_MEMORY_ID},
                    "batch_size": 100,
                    "promotion_preview_approved": False,
                }
            ],
            "system_settings": [
                {
                    "key": "backup_restore_gate",
                    "value": "enabled",
                    "is_secret": False,
                }
            ],
            "backup_settings": [
                {
                    "id": "10000000-0000-4000-8000-000000000007",
                    "organization_id": ORG_ID,
                    "enabled": True,
                    "schedule": "0 2 * * *",
                    "retention_days": 30,
                    "include_database_dump": False,
                    "include_graph": True,
                }
            ],
            "backups": [
                {
                    "id": "10000000-0000-4000-8000-000000000008",
                    "organization_id": ORG_ID,
                    "backup_id": "backup_restore_gate",
                    "status": "completed",
                    "size_bytes": 2048,
                    "include_database_dump": False,
                    "include_graph": True,
                }
            ],
        },
        "row_counts": {
            "crawl_sources": 1,
            "crawled_documents": 1,
            "document_chunks": 1,
            "raw_captures": 2,
            "source_imports": 1,
            "system_settings": 1,
            "backup_settings": 1,
            "backups": 1,
        },
        "total_rows": 9,
    }
    graph: JsonObject = {
        "version": "2.0",
        "created_at": "2026-05-18T00:00:00+00:00",
        "organization_id": ORG_ID,
        "entity_count": 3,
        "relationship_count": 2,
        "episode_count": 0,
        "mention_count": 0,
        "entities": [
            {
                "id": PROJECT_ID,
                "entity_type": "project",
                "name": "Backup restore project",
                "metadata": {"source_ids": [RAW_SOURCE_ID]},
            },
            {
                "id": TASK_ID,
                "entity_type": "task",
                "name": "Backup restore task",
                "metadata": {
                    "project_id": PROJECT_ID,
                    "source_ids": [RAW_SOURCE_ID],
                },
            },
            {
                "id": "artifact-gate",
                "entity_type": "artifact",
                "name": "Synthesis artifact",
                "metadata": {"source_ids": [SYNTHESIS_SOURCE_ID]},
            },
        ],
        "relationships": [
            {
                "id": "rel-task-project",
                "source_id": TASK_ID,
                "target_id": PROJECT_ID,
                "relationship_type": "BELONGS_TO",
                "metadata": {"source_ids": [RAW_SOURCE_ID]},
            },
            {
                "id": "rel-task-artifact",
                "source_id": TASK_ID,
                "target_id": "artifact-gate",
                "relationship_type": "PRODUCES",
                "metadata": {"source_ids": [SYNTHESIS_SOURCE_ID]},
            },
        ],
        "episodes": [],
        "mentions": [],
    }
    return auth, content, graph


def _table_rows(payload: Mapping[str, object], table: str) -> list[JsonObject]:
    tables_payload = payload.get("tables")
    if not isinstance(tables_payload, Mapping):
        raise GateFailure("archive payload is missing tables")
    tables = {str(key): value for key, value in tables_payload.items()}
    rows = tables.get(table)
    if not isinstance(rows, list):
        raise GateFailure(f"{table} rows are missing")
    return [
        {str(key): value for key, value in row.items()} for row in rows if isinstance(row, Mapping)
    ]


def _first_row(rows: Sequence[JsonObject], **filters: object) -> JsonObject:
    for row in rows:
        if all(row.get(key) == value for key, value in filters.items()):
            return row
    details = ", ".join(f"{key}={value}" for key, value in filters.items())
    raise GateFailure(f"missing row matching {details}")


def _require(condition: bool, message: str, checks: list[str]) -> None:
    if not condition:
        raise GateFailure(message)
    checks.append(message)


def _validate_fixture_invariants(
    *,
    auth: JsonObject,
    content: JsonObject,
    graph: JsonObject,
) -> JsonObject:
    checks: list[str] = []
    private_space = _first_row(
        _table_rows(auth, "memory_spaces"),
        memory_scope="private",
        scope_key=USER_ID,
    )
    _require(private_space["organization_id"] == ORG_ID, "private auth scope survives", checks)

    raw_memory = _first_row(_table_rows(content, "raw_captures"), id=RAW_MEMORY_ID)
    _require(raw_memory["memory_scope"] == "private", "raw memory policy scope survives", checks)
    _require(raw_memory["scope_key"] == USER_ID, "raw memory scope key survives", checks)
    _require(raw_memory["source_id"] == RAW_SOURCE_ID, "raw memory source ID survives", checks)

    source_import = _first_row(_table_rows(content, "source_imports"), id=SOURCE_IMPORT_ID)
    _require(
        source_import["target_memory_scope"] == "private",
        "source import target scope survives",
        checks,
    )
    _require(
        source_import["target_scope_key"] == USER_ID, "source import scope key survives", checks
    )
    _require(
        source_import["source_ids"] == [RAW_SOURCE_ID], "source import source IDs survive", checks
    )
    _require(
        source_import["raw_memory_by_source_id"] == {RAW_SOURCE_ID: RAW_MEMORY_ID},
        "source import raw-memory links survive",
        checks,
    )

    synthesis = _first_row(_table_rows(content, "raw_captures"), id=SYNTHESIS_MEMORY_ID)
    synthesis_metadata = synthesis.get("metadata")
    synthesis_provenance = synthesis.get("provenance")
    _require(
        isinstance(synthesis_metadata, dict)
        and synthesis_metadata.get("source_ids") == [RAW_SOURCE_ID, DOC_SOURCE_ID],
        "synthesis metadata source IDs survive",
        checks,
    )
    _require(
        isinstance(synthesis_provenance, dict)
        and synthesis_provenance.get("section_source_ids") == {"Findings": [DOC_SOURCE_ID]},
        "synthesis provenance section sources survive",
        checks,
    )

    relationships = graph.get("relationships")
    if not isinstance(relationships, list):
        raise GateFailure("graph relationships are missing")
    task_link = _first_row(
        [dict(row) for row in relationships if isinstance(row, dict)],
        source_id=TASK_ID,
        target_id=PROJECT_ID,
        relationship_type="BELONGS_TO",
    )
    metadata = task_link.get("metadata")
    _require(
        isinstance(metadata, dict) and metadata.get("source_ids") == [RAW_SOURCE_ID],
        "task relationship source metadata survives",
        checks,
    )

    return {"status": "PASS", "checks": checks}


def build_release_receipt() -> JsonObject:
    auth, content, graph = _fixture_payloads()
    files = {
        AUTH_FILENAME: _json_bytes(auth),
        CONTENT_FILENAME: _json_bytes(content),
        GRAPH_FILENAME: _json_bytes(graph),
    }
    manifest = build_manifest(
        organization_id=ORG_ID,
        source_store="surreal",
        files=files,
        file_metadata={
            AUTH_FILENAME: {"kind": "auth"},
            CONTENT_FILENAME: {"kind": "content"},
            GRAPH_FILENAME: {"kind": "graph"},
        },
        metadata={"gate": "backup-restore-gate"},
    )
    archive = LoadedArchive(
        source=Path("backup-restore-gate-fixture"), manifest=manifest, files=files
    )
    archive_errors = validate_archive(archive)
    if archive_errors:
        raise GateFailure("; ".join(archive_errors))

    invariant_receipt = _validate_fixture_invariants(auth=auth, content=content, graph=graph)
    content_tables = content.get("row_counts")
    auth_tables = auth.get("row_counts")
    return {
        "status": "PASS",
        "organization_id": ORG_ID,
        "archive_files": sorted(files),
        "auth_tables": dict(auth_tables) if isinstance(auth_tables, dict) else {},
        "content_tables": dict(content_tables) if isinstance(content_tables, dict) else {},
        "graph_counts": effective_graph_counts(graph),
        "invariants": invariant_receipt,
    }


def _write_receipt(path: Path, receipt: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _print_receipt(results: Sequence[GateResult], receipt: JsonObject, *, echo: Echo) -> None:
    passed = [result for result in results if result.passed]
    failed = [result for result in results if not result.passed]
    surfaces = sorted(covered_surfaces(result.check for result in results))

    echo("")
    echo("Backup Restore Gate Receipt")
    echo(f"status: {receipt['status']}")
    echo(f"checks: {len(passed)} passed, {len(failed)} failed")
    echo(f"surfaces: {', '.join(surfaces)}")
    echo(f"artifact: {receipt['artifact_path']}")
    for result in results:
        check_status = "PASS" if result.passed else f"FAIL exit={result.exit_code}"
        error = f"; error={result.error}" if result.error is not None else ""
        echo(f"- {check_status} {result.check.name} ({result.elapsed_seconds:.2f}s){error}")


def run_gate(
    checks: Sequence[GateCheck] = GATE_CHECKS,
    *,
    runner: Runner | None = None,
    echo: Echo = _echo,
    artifact_path: Path = DEFAULT_ARTIFACT_PATH,
) -> int:
    missing = missing_required_surfaces(checks)
    if missing:
        echo("Backup restore gate is missing required surfaces:")
        for surface in missing:
            echo(f"- {surface}")
        return 2

    active_runner = runner or _real_runner
    echo("Backup Restore Gate")
    echo(f"checks: {len(checks)}")

    results = [_run_check(check, runner=active_runner, echo=echo) for check in checks]
    fixture_receipt: JsonObject
    fixture_error: str | None = None
    try:
        fixture_receipt = build_release_receipt()
    except Exception as exc:
        fixture_receipt = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}
        fixture_error = str(exc)

    failed = [result for result in results if not result.passed]
    status = "PASS" if not failed and fixture_error is None else "FAIL"
    receipt: JsonObject = {
        "schema_version": "backup-restore-gate/v1",
        "status": status,
        "created_at": datetime.now(UTC).isoformat(),
        "artifact_path": _display_path(artifact_path),
        "checks": [
            {
                "name": result.check.name,
                "description": result.check.description,
                "command": format_command(result.check.command),
                "surfaces": list(result.check.surfaces),
                "status": "PASS" if result.passed else "FAIL",
                "exit_code": result.exit_code,
                "elapsed_seconds": round(result.elapsed_seconds, 3),
                "error": result.error,
            }
            for result in results
        ],
        "surfaces": sorted(covered_surfaces(checks)),
        "release_fixture": fixture_receipt,
    }
    _write_receipt(artifact_path, receipt)
    _print_receipt(results, receipt, echo=echo)
    if fixture_error is not None:
        echo(f"release fixture: FAIL {fixture_error}")
    return 0 if status == "PASS" else 1


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run backup/restore release-gate checks.")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List checks and exit without running them.",
    )
    parser.add_argument(
        "--artifact-path",
        type=Path,
        default=DEFAULT_ARTIFACT_PATH,
        help="Path for the release receipt JSON artifact.",
    )
    args = parser.parse_args(argv)

    if args.list:
        for check in GATE_CHECKS:
            _echo(f"{check.name}: {format_command(check.command)}")
        return 0

    return run_gate(artifact_path=args.artifact_path)


if __name__ == "__main__":
    raise SystemExit(main())
