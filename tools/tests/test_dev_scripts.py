from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from shutil import which

from tools.tests.conftest import REPO_ROOT


def _write_docker_stub(bin_dir: Path) -> None:
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "compose" && "${2:-}" == "ps" ]]; then
  printf '{"Service":"falkordb"}\\n'
  exit 0
fi
if [[ "${1:-}" == "volume" && "${2:-}" == "ls" ]]; then
  exit 0
fi
exit 1
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)


def _write_local_migration_stubs(bin_dir: Path) -> None:
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf 'docker %s\\n' "$*" >> "$SIBYL_STUB_LOG"
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)

    uv = bin_dir / "uv"
    uv.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf 'uv %s | store=%s auth=%s coord=%s surreal=%s redis=%s:%s\\n' \
  "$*" \
  "${SIBYL_STORE:-}" \
  "${SIBYL_AUTH_STORE:-}" \
  "${SIBYL_COORDINATION_BACKEND:-}" \
  "${SIBYL_SURREAL_URL:-}" \
  "${SIBYL_REDIS_HOST:-}" \
  "${SIBYL_REDIS_PORT:-}" >> "$SIBYL_STUB_LOG"
""",
        encoding="utf-8",
    )
    uv.chmod(0o755)


def _run_detector(
    tmp_path: Path,
    *,
    migrated: bool,
    explicit_data_dir: bool = True,
    rocksdb: bool = False,
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_docker_stub(bin_dir)

    data_dir = (
        tmp_path / "surreal-dev" if explicit_data_dir else tmp_path / ".moon/cache/surreal-dev"
    )
    data_dir.mkdir(parents=True)
    if migrated:
        (data_dir / ".sibyl-migrated").write_text(
            "archive=/tmp/sibyl-migrate.tar.gz\nmigrated_at=2026-05-04T00:00:00Z\n",
            encoding="utf-8",
        )
    if rocksdb:
        rocksdb_dir = data_dir / "sibyl.db"
        rocksdb_dir.mkdir()
        (rocksdb_dir / "CURRENT").write_text("MANIFEST-000001\n", encoding="utf-8")

    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "SIBYL_STORE": "surreal",
    }
    if explicit_data_dir:
        env["SURREAL_DATA_DIR"] = str(data_dir)
    else:
        env.pop("SURREAL_DATA_DIR", None)

    detector = "source tools/dev/run-surreal-dev.sh; "
    if not explicit_data_dir:
        detector += f"repo_root={shlex.quote(str(tmp_path))}; "
    detector += "warn_if_legacy_setup_detected"

    bash = which("bash")
    assert bash is not None
    return subprocess.run(  # noqa: S603
        [
            bash,
            "-lc",
            detector,
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_legacy_guard_allows_migrated_surreal_runtime(tmp_path: Path) -> None:
    result = _run_detector(tmp_path, migrated=True)

    assert result.returncode == 0
    assert "Local legacy data detected" not in result.stdout


def test_legacy_guard_allows_migrated_default_surreal_runtime(tmp_path: Path) -> None:
    result = _run_detector(tmp_path, migrated=True, explicit_data_dir=False)

    assert result.returncode == 0
    assert "Local legacy data detected" not in result.stdout


def test_legacy_guard_allows_existing_default_surreal_runtime(tmp_path: Path) -> None:
    result = _run_detector(tmp_path, migrated=False, explicit_data_dir=False, rocksdb=True)

    assert result.returncode == 0
    assert "Local legacy data detected" not in result.stdout


def test_legacy_guard_warns_when_legacy_exists_without_surreal_marker(tmp_path: Path) -> None:
    result = _run_detector(tmp_path, migrated=False, explicit_data_dir=False)

    assert result.returncode == 1
    assert "Local legacy data detected" in result.stdout
    assert "moon run dev -- --migrate-legacy" in result.stdout


def test_local_surreal_migration_script_wires_org_and_runtime_env(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_local_migration_stubs(bin_dir)

    log_path = tmp_path / "stub.log"
    archive_path = tmp_path / "migration.tar.gz"
    data_dir = tmp_path / "surreal-dev"
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "SIBYL_STUB_LOG": str(log_path),
        "SURREAL_DATA_DIR": str(data_dir),
    }
    bash = which("bash")
    assert bash is not None

    result = subprocess.run(  # noqa: S603
        [
            bash,
            "tools/dev/migrate-local-surreal.sh",
            "--org-id",
            "org-two",
            "--archive",
            str(archive_path),
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    log = log_path.read_text(encoding="utf-8")
    assert "docker compose up -d falkordb postgres surrealdb redis" in log
    assert (
        f"uv run --directory apps/api sibyld migrate export --output {archive_path} "
        "--include-content --org-id org-two | store=legacy auth=postgres coord="
    ) in log
    assert (
        f"uv run --directory apps/api sibyld migrate import {archive_path} --yes --clean "
        "| store=surreal auth=surreal coord=local surreal=ws://127.0.0.1:8000/rpc "
        "redis=127.0.0.1:6381"
    ) in log
    assert (
        f"uv run --directory apps/api sibyld migrate verify {archive_path} "
        "| store=surreal auth=surreal coord=local surreal=ws://127.0.0.1:8000/rpc "
        "redis=127.0.0.1:6381"
    ) in log
    marker = data_dir / ".sibyl-migrated"
    assert marker.exists()
    assert f"archive={archive_path}" in marker.read_text(encoding="utf-8")


def test_local_surreal_migration_script_restores_database_dump_when_requested(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_local_migration_stubs(bin_dir)

    log_path = tmp_path / "stub.log"
    archive_path = tmp_path / "migration.tar.gz"
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "SIBYL_STUB_LOG": str(log_path),
        "SURREAL_DATA_DIR": str(tmp_path / "surreal-dev"),
    }
    bash = which("bash")
    assert bash is not None

    result = subprocess.run(  # noqa: S603
        [
            bash,
            "tools/dev/migrate-local-surreal.sh",
            "--archive",
            str(archive_path),
            "--restore-database-dump",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    log = log_path.read_text(encoding="utf-8")
    assert f"migrate export --output {archive_path} --include-content" in log
    assert "--org-id" not in log
    assert f"migrate import {archive_path} --yes --clean --restore-database-dump" in log


def test_local_surreal_migration_script_overrides_surreal_coordination_env(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_local_migration_stubs(bin_dir)

    log_path = tmp_path / "stub.log"
    archive_path = tmp_path / "migration.tar.gz"
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "SIBYL_STUB_LOG": str(log_path),
        "SIBYL_COORDINATION_BACKEND": "redis",
        "SIBYL_REDIS_HOST": "bad-redis",
        "SIBYL_REDIS_PORT": "6399",
        "SURREAL_DATA_DIR": str(tmp_path / "surreal-dev"),
    }
    bash = which("bash")
    assert bash is not None

    result = subprocess.run(  # noqa: S603
        [
            bash,
            "tools/dev/migrate-local-surreal.sh",
            "--archive",
            str(archive_path),
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    log = log_path.read_text(encoding="utf-8")
    assert f"migrate export --output {archive_path} --include-content" in log
    assert "migrate import" in log
    assert "migrate verify" in log
    assert "store=surreal auth=surreal coord=local" in log


def test_local_surreal_migration_script_requires_org_id_value() -> None:
    bash = which("bash")
    assert bash is not None

    result = subprocess.run(  # noqa: S603
        [bash, "tools/dev/migrate-local-surreal.sh", "--org-id"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Missing value for --org-id" in result.stderr


def test_local_surreal_migration_script_requires_archive_value() -> None:
    bash = which("bash")
    assert bash is not None

    result = subprocess.run(  # noqa: S603
        [bash, "tools/dev/migrate-local-surreal.sh", "--archive", "--restore-database-dump"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Missing value for --archive" in result.stderr
