from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from sibyl_cli import config_store
from sibyl_cli import doctor as doctor_module
from sibyl_cli.doctor import DoctorCheck, DoctorContext
from sibyl_cli.main import app


def _use_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_store.Path, "home", lambda: tmp_path)


def test_doctor_json_reports_missing_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_home(tmp_path, monkeypatch)

    result = CliRunner().invoke(app, ["doctor", "--json"])

    assert result.exit_code == 1
    assert '"ok": false' in result.stdout
    assert "No Sibyl config exists" in result.stdout


def test_doctor_fails_when_active_context_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_home(tmp_path, monkeypatch)
    config_store.ensure_config_dir()
    config_store.config_path().write_text('active_context = "ghost"\n')

    checks, context = doctor_module._load_config_context()

    assert context is None
    assert any(check.name == "context" and check.status == "fail" for check in checks)


def test_doctor_embedded_lock_detects_stale_pid(tmp_path: Path) -> None:
    lock_path = tmp_path / "embedded-surreal.lock"
    lock_path.write_text('pid = 424242\n')

    check = doctor_module._check_embedded_lock(
        lock_path=lock_path,
        pid_alive=lambda _pid: False,
    )

    assert check.status == "fail"
    assert "stale" in check.message


@pytest.mark.asyncio
async def test_doctor_collects_healthy_local_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_home(tmp_path, monkeypatch)
    config_store.create_context(
        "local",
        "http://localhost:3334",
        set_active=True,
    )

    async def health(_context: DoctorContext, _timeout: float) -> DoctorCheck:
        return DoctorCheck("daemon", "pass", "Sibyl API is healthy.")

    async def write_probe(_enabled: bool) -> DoctorCheck:
        return DoctorCheck("write-test", "pass", "Authenticated write probe succeeded.")

    monkeypatch.setattr(doctor_module, "_check_public_health", health)
    monkeypatch.setattr(doctor_module, "_check_write_probe", write_probe)
    monkeypatch.setattr(doctor_module, "_probe_port", lambda *_args: True)

    checks = await doctor_module.collect_doctor_checks(timeout=0.1, write_test=True)

    assert not any(check.failed for check in checks)
    assert [check.name for check in checks] == [
        "config",
        "context",
        "daemon",
        "port",
        "embedded-lock",
        "write-test",
    ]
