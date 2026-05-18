from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from shutil import which
from typing import NotRequired, TypedDict, cast

import pytest
from tools.trust import backup_restore_gate

MISSING_SURFACE_EXIT_CODE = 2
EXPECTED_MEMORY_SPACE_COUNT = 2
EXPECTED_RAW_CAPTURE_COUNT = 2
REPO_ROOT = Path(__file__).resolve().parents[2]


class MoonTask(TypedDict):
    command: str
    args: NotRequired[list[str]]
    target: str


class MoonTaskQuery(TypedDict):
    tasks: dict[str, dict[str, MoonTask]]


def _moon_tasks(project: str) -> dict[str, MoonTask]:
    moon = which("moon")
    assert moon is not None

    result = subprocess.run(  # noqa: S603
        [moon, "query", "tasks", "--project", project],
        cwd=REPO_ROOT,
        env={**os.environ, "MOON_COLOR": "false"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = cast(MoonTaskQuery, json.loads(result.stdout))
    return payload["tasks"][project]


def test_gate_checks_cover_required_surfaces() -> None:
    assert backup_restore_gate.missing_required_surfaces() == []


def test_gate_checks_use_moon_package_slices() -> None:
    commands = [check.command for check in backup_restore_gate.GATE_CHECKS]

    assert all(command[:2] == ("moon", "run") for command in commands)
    assert ("moon", "run", "core:backup-restore-gate-test") in commands
    assert ("moon", "run", "api:backup-restore-gate-test") in commands


def test_release_receipt_fixture_covers_restore_invariants() -> None:
    receipt = backup_restore_gate.build_release_receipt()

    assert receipt["status"] == "PASS"
    assert receipt["archive_files"] == ["auth.json", "content.json", "graph.json"]
    assert receipt["auth_tables"]["memory_spaces"] == EXPECTED_MEMORY_SPACE_COUNT
    assert receipt["content_tables"]["raw_captures"] == EXPECTED_RAW_CAPTURE_COUNT
    assert receipt["content_tables"]["source_imports"] == 1
    assert receipt["graph_counts"] == {
        "entity_count": 3,
        "relationship_count": 2,
        "episode_count": 0,
        "mention_count": 0,
    }
    assert "source import source IDs survive" in receipt["invariants"]["checks"]
    assert "task relationship source metadata survives" in receipt["invariants"]["checks"]
    assert "synthesis provenance section sources survive" in receipt["invariants"]["checks"]


def test_run_gate_prints_and_writes_release_receipt(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    commands: list[tuple[str, ...]] = []

    def runner(command: tuple[str, ...]) -> int:
        commands.append(command)
        return 0

    artifact_path = tmp_path / "receipt.json"
    exit_code = backup_restore_gate.run_gate(runner=runner, artifact_path=artifact_path)

    captured = capsys.readouterr()
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert commands == [check.command for check in backup_restore_gate.GATE_CHECKS]
    assert "Backup Restore Gate Receipt" in captured.out
    assert "status: PASS" in captured.out
    assert "source import runs restore" in captured.out
    assert payload["schema_version"] == "backup-restore-gate/v1"
    assert payload["status"] == "PASS"
    assert payload["release_fixture"]["content_tables"]["source_imports"] == 1


def test_run_gate_executes_all_checks_before_failure(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    commands: list[tuple[str, ...]] = []
    failing_check = backup_restore_gate.GATE_CHECKS[1]
    failing_command = failing_check.command

    def runner(command: tuple[str, ...]) -> int:
        commands.append(command)
        return 1 if command == failing_command else 0

    artifact_path = tmp_path / "receipt.json"
    exit_code = backup_restore_gate.run_gate(runner=runner, artifact_path=artifact_path)

    captured = capsys.readouterr()
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert commands == [check.command for check in backup_restore_gate.GATE_CHECKS]
    assert "status: FAIL" in captured.out
    assert f"FAIL exit=1 {failing_check.name}" in captured.out
    assert payload["status"] == "FAIL"


def test_run_gate_turns_runner_exceptions_into_receipts(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    def runner(command: tuple[str, ...]) -> int:
        msg = f"cannot run {command[0]}"
        raise RuntimeError(msg)

    artifact_path = tmp_path / "receipt.json"
    exit_code = backup_restore_gate.run_gate(runner=runner, artifact_path=artifact_path)

    captured = capsys.readouterr()
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert "status: FAIL" in captured.out
    assert "RuntimeError: cannot run moon" in captured.out
    assert payload["checks"][0]["error"] == "RuntimeError: cannot run moon"


def test_run_gate_rejects_missing_required_surface() -> None:
    check = backup_restore_gate.GateCheck(
        name="partial",
        description="partial coverage",
        surfaces=("auth restore",),
        command=("moon", "run", "api:test"),
    )
    messages: list[str] = []

    exit_code = backup_restore_gate.run_gate([check], runner=lambda _: 0, echo=messages.append)

    assert exit_code == MISSING_SURFACE_EXIT_CODE
    assert "Backup restore gate is missing required surfaces:" in messages
    assert "- graph restore" in messages


def test_main_lists_gate_checks(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = backup_restore_gate.main(["--list"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "core-graph-backup-restore: moon run core:backup-restore-gate-test" in captured.out
    assert "api-surreal-archive-restore: moon run api:backup-restore-gate-test" in captured.out


def test_root_moon_tasks_expose_backup_restore_gate() -> None:
    tasks = _moon_tasks("root")

    gate = tasks["backup-restore-gate"]
    assert gate["target"] == "root:backup-restore-gate"
    assert gate["command"] == "uv"
    assert gate["args"] == ["run", "python", "-m", "tools.trust.backup_restore_gate"]

    test_task = tasks["backup-restore-gate-test"]
    assert test_task["target"] == "root:backup-restore-gate-test"
    assert test_task["command"] == "uv"
    assert test_task["args"] == ["run", "pytest", "tools/tests/test_backup_restore_gate.py", "-v"]


def test_package_moon_tasks_expose_backup_restore_slices() -> None:
    core_tasks = _moon_tasks("core")
    api_tasks = _moon_tasks("api")

    core = core_tasks["backup-restore-gate-test"]
    assert core["target"] == "core:backup-restore-gate-test"
    assert core["command"] == "uv"
    assert core["args"] == [
        "run",
        "pytest",
        "tests/test_tools_admin.py::TestBackupInventory",
        "tests/test_tools_admin.py::TestRestoreBackup",
        "tests/test_migrate_archive.py",
        "-v",
    ]

    api = api_tasks["backup-restore-gate-test"]
    assert api["target"] == "api:backup-restore-gate-test"
    assert api["command"] == "uv"
    assert api["args"] == [
        "run",
        "pytest",
        "tests/test_jobs_backup.py",
        "tests/test_backups_routes.py",
        "tests/test_surreal_auth_persistence.py::test_auth_archive_restore_accepts_full_user_rows",
        "tests/test_surreal_content_persistence.py::test_content_archive_restore_preserves_embeddings_and_metadata",
        "tests/test_surreal_content_persistence.py::test_content_archive_export_reads_from_surreal_backend",
        "-v",
    ]
