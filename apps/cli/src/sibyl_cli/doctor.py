"""Environment diagnostics for the Sibyl CLI."""

from __future__ import annotations

import os
import socket
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import httpx
import typer

from sibyl_cli import config_store
from sibyl_cli.client import SibylClientError, get_client
from sibyl_cli.common import (
    ELECTRIC_YELLOW,
    ERROR_RED,
    NEON_CYAN,
    SUCCESS_GREEN,
    console,
    create_table,
    print_json,
    run_async,
)

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    message: str
    detail: str | None = None

    @property
    def failed(self) -> bool:
        return self.status == "fail"

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "name": self.name,
            "status": self.status,
            "message": self.message,
        }
        if self.detail:
            payload["detail"] = self.detail
        return payload


@dataclass(frozen=True)
class DoctorContext:
    name: str
    server_url: str
    insecure: bool = False
    source: str = "context"


def _api_health_url(server_url: str) -> str:
    return f"{server_url.rstrip('/')}/api/health"


def _is_local_server(server_url: str) -> bool:
    parsed = urlparse(server_url)
    return (parsed.hostname or "").lower() in LOCAL_HOSTS


def _server_host_port(server_url: str) -> tuple[str, int] | None:
    parsed = urlparse(server_url)
    if not parsed.hostname:
        return None
    if parsed.port:
        return parsed.hostname, parsed.port
    if parsed.scheme == "https":
        return parsed.hostname, 443
    if parsed.scheme == "http":
        return parsed.hostname, 80
    return None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def embedded_lock_path() -> Path:
    return config_store.config_dir() / "run" / "embedded-surreal.lock"


def _probe_port(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _load_config_context() -> tuple[list[DoctorCheck], DoctorContext | None]:
    path = config_store.config_path()
    if not path.exists():
        return [
            DoctorCheck(
                "config",
                "fail",
                "No Sibyl config exists.",
                f"Run 'sibyl init' to create {path}.",
            )
        ], None

    try:
        with open(path, "rb") as stream:
            raw_config = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [
            DoctorCheck(
                "config",
                "fail",
                "Sibyl config is unreadable.",
                str(exc),
            )
        ], None

    config = config_store.load_config()
    active_name = str(config.get("active_context") or "").strip()
    contexts = raw_config.get("contexts", {})
    checks: list[DoctorCheck] = [DoctorCheck("config", "pass", f"Config file is readable: {path}")]

    if active_name:
        ctx = config_store.get_context(active_name)
        if ctx is None:
            checks.append(
                DoctorCheck(
                    "context",
                    "fail",
                    f"Active context '{active_name}' is missing.",
                    "Run 'sibyl context list' and 'sibyl context use <name>'.",
                )
            )
            return checks, None
        checks.append(DoctorCheck("context", "pass", f"Active context: {active_name}"))
        return checks, DoctorContext(
            name=ctx.name,
            server_url=ctx.server_url,
            insecure=ctx.insecure,
        )

    if contexts:
        checks.append(
            DoctorCheck(
                "context",
                "warn",
                "Contexts exist but none is active.",
                "Run 'sibyl context use <name>' to make writes explicit.",
            )
        )
        return checks, None

    server_url = str(config.get("server", {}).get("url") or "").strip()
    if not server_url:
        checks.append(
            DoctorCheck(
                "context",
                "fail",
                "No server URL is configured.",
                "Run 'sibyl init' or 'sibyl context create local --use'.",
            )
        )
        return checks, None

    checks.append(
        DoctorCheck(
            "context",
            "warn",
            "Using legacy server.url because no named context is active.",
            "Run 'sibyl init --force' to create an explicit local or remote context.",
        )
    )
    return checks, DoctorContext(name="legacy", server_url=server_url, source="legacy")


async def _check_public_health(context: DoctorContext, timeout: float) -> DoctorCheck:
    url = _api_health_url(context.server_url)
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=not context.insecure) as client:
            response = await client.get(url)
    except httpx.ConnectError as exc:
        return DoctorCheck("daemon", "fail", "Sibyl API is not reachable.", str(exc))
    except httpx.TimeoutException as exc:
        return DoctorCheck("daemon", "fail", "Sibyl API health check timed out.", str(exc))
    except httpx.HTTPError as exc:
        return DoctorCheck("daemon", "fail", "Sibyl API health check failed.", str(exc))

    if response.status_code != 200:
        return DoctorCheck(
            "daemon",
            "fail",
            f"Sibyl API returned HTTP {response.status_code}.",
            url,
        )

    try:
        data = response.json()
    except ValueError:
        return DoctorCheck("daemon", "fail", "Sibyl API returned non-JSON health data.", url)

    status = str(data.get("status") or "unknown")
    if status != "healthy":
        return DoctorCheck("daemon", "fail", f"Sibyl API is {status}.", url)
    version = str(data.get("version") or "").strip()
    suffix = f" ({version})" if version else ""
    return DoctorCheck("daemon", "pass", f"Sibyl API is healthy{suffix}.", url)


def _check_local_port(context: DoctorContext, timeout: float, health: DoctorCheck) -> DoctorCheck:
    host_port = _server_host_port(context.server_url)
    if host_port is None:
        return DoctorCheck("port", "warn", "Could not parse local server port.")
    host, port = host_port
    if _probe_port(host, port, timeout):
        status = "pass" if health.status == "pass" else "fail"
        message = (
            f"Port {host}:{port} is serving Sibyl."
            if health.status == "pass"
            else f"Port {host}:{port} is open but Sibyl health failed."
        )
        return DoctorCheck("port", status, message)
    return DoctorCheck(
        "port",
        "fail",
        f"Port {host}:{port} is closed.",
        "Run 'sibyl serve' for local mode or switch contexts.",
    )


def _check_embedded_lock(
    *,
    lock_path: os.PathLike[str] | str | None = None,
    pid_alive: Callable[[int], bool] = _pid_alive,
) -> DoctorCheck:
    path = Path(lock_path) if lock_path is not None else embedded_lock_path()
    if not path.exists():
        return DoctorCheck(
            "embedded-lock",
            "warn",
            "No embedded SurrealDB lockfile was found.",
            f"Expected at {path}; this is fine for remote or Docker contexts.",
        )

    try:
        with open(path, "rb") as stream:
            data = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return DoctorCheck("embedded-lock", "fail", "Embedded lockfile is unreadable.", str(exc))

    pid_value = data.get("pid")
    if not isinstance(pid_value, int | str):
        return DoctorCheck("embedded-lock", "fail", "Embedded lockfile does not contain a PID.")
    try:
        pid = int(pid_value)
    except (TypeError, ValueError):
        return DoctorCheck("embedded-lock", "fail", "Embedded lockfile does not contain a PID.")

    if pid_alive(pid):
        return DoctorCheck("embedded-lock", "pass", f"Embedded lock is held by PID {pid}.")
    return DoctorCheck(
        "embedded-lock",
        "fail",
        f"Embedded lock is stale; PID {pid} is not running.",
        f"Remove {path} only after confirming no sibyld process is active.",
    )


async def _check_write_probe(enabled: bool) -> DoctorCheck:
    if not enabled:
        return DoctorCheck("write-test", "warn", "Write probe skipped by --no-write-test.")
    try:
        async with get_client() as client:
            data = await client._request("POST", "/admin/write-test", _buffer_pending=False)
    except SibylClientError as exc:
        return DoctorCheck(
            "write-test",
            "fail",
            "Authenticated write probe failed.",
            exc.remediation or exc.detail or str(exc),
        )

    status = str(data.get("status") or "unknown")
    if status != "ok":
        return DoctorCheck("write-test", "fail", f"Write probe returned {status}.")
    return DoctorCheck("write-test", "pass", "Authenticated write probe succeeded.")


async def collect_doctor_checks(*, timeout: float, write_test: bool) -> list[DoctorCheck]:
    checks, context = _load_config_context()
    if context is None:
        return checks

    health = await _check_public_health(context, timeout)
    checks.append(health)
    if _is_local_server(context.server_url):
        checks.append(_check_local_port(context, timeout, health))
        checks.append(_check_embedded_lock())
    else:
        checks.append(DoctorCheck("port", "warn", "Port probe skipped for remote context."))
        checks.append(
            DoctorCheck("embedded-lock", "warn", "Embedded lock probe skipped for remote context.")
        )
    checks.append(await _check_write_probe(write_test))
    return checks


def _render_checks(checks: list[DoctorCheck]) -> None:
    table = create_table("Sibyl Doctor", "Check", "Status", "Message", "Detail")
    colors = {"pass": SUCCESS_GREEN, "warn": ELECTRIC_YELLOW, "fail": ERROR_RED}
    labels = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}
    for check in checks:
        color = colors.get(check.status, NEON_CYAN)
        table.add_row(
            check.name,
            f"[{color}]{labels.get(check.status, check.status.upper())}[/{color}]",
            check.message,
            check.detail or "",
        )
    console.print(table)


def doctor(
    json_output: Annotated[bool, typer.Option("--json", "-j", help="Output as JSON")] = False,
    timeout: Annotated[float, typer.Option("--timeout", help="Network timeout in seconds")] = 2.0,
    write_test: Annotated[
        bool,
        typer.Option("--write-test/--no-write-test", help="Run the authenticated write probe"),
    ] = True,
) -> None:
    """Diagnose Sibyl config, daemon health, locks, and write readiness."""

    @run_async
    async def _run() -> None:
        checks = await collect_doctor_checks(timeout=timeout, write_test=write_test)
        ok = not any(check.failed for check in checks)
        if json_output:
            print_json({"ok": ok, "checks": [check.to_dict() for check in checks]})
        else:
            _render_checks(checks)
        if not ok:
            raise typer.Exit(1)

    _run()
