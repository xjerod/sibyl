"""Host-managed embedded daemon commands."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import typer

from sibyl_cli import config_store
from sibyl_cli.common import NEON_CYAN, console, error, info, success
from sibyl_cli.state import get_context_override

SIBYL_RUN_DIR = Path.home() / ".sibyl" / "run"
SIBYLD_PID_FILE = SIBYL_RUN_DIR / "sibyld.pid"
SIBYLD_LOG_FILE = SIBYL_RUN_DIR / "sibyld.log"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True)
class HostContext:
    name: str
    server_url: str


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def resolve_host_context() -> HostContext | None:
    context_name = get_context_override()
    ctx = config_store.get_context(context_name) if context_name else config_store.get_active_context()
    if ctx is None:
        return None
    return HostContext(name=ctx.name, server_url=ctx.server_url)


def is_local_server(server_url: str) -> bool:
    parsed = urlparse(server_url)
    return (parsed.hostname or "").lower() in LOCAL_HOSTS


def require_local_context() -> HostContext:
    ctx = resolve_host_context()
    if ctx is None:
        error("No active context is configured.")
        info("Run 'sibyl init --local' before starting the local daemon.")
        raise typer.Exit(1)
    if not is_local_server(ctx.server_url):
        error(f"Context '{ctx.name}' points to {ctx.server_url}.")
        info("Switch to a local context with 'sibyl context use local'.")
        raise typer.Exit(1)
    return ctx


def read_pid(path: Path | None = None) -> int | None:
    path = path or SIBYLD_PID_FILE
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def daemon_command(host: str, port: int, transport: str) -> list[str]:
    return [
        "sibyld",
        "serve",
        "--embedded",
        "--host",
        host,
        "--port",
        str(port),
        "--transport",
        transport,
    ]


def serve(
    host: Annotated[str, typer.Option("--host", help="Host to bind")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", "-p", help="Port to listen on")] = 3334,
    transport: Annotated[str, typer.Option("--transport", "-t", help="MCP transport")] = (
        "streamable-http"
    ),
    background: Annotated[bool, typer.Option("--background", "-d", help="Run in the background")] = (
        False
    ),
    web: Annotated[bool, typer.Option("--web", help="Also start the web UI when bundled")] = False,
) -> None:
    """Start the local embedded Sibyl daemon for the active local context."""
    ctx = require_local_context()
    if web:
        error("The web UI is not bundled into the host install yet.")
        info("Use 'sibyl docker up' for the full API + web stack.")
        raise typer.Exit(1)

    cmd = daemon_command(host, port, transport)
    if not background:
        console.print(f"[{NEON_CYAN}]Context:[/{NEON_CYAN}] {ctx.name} -> {ctx.server_url}")
        raise typer.Exit(subprocess.run(cmd, check=False).returncode)

    existing_pid = read_pid()
    if existing_pid and pid_alive(existing_pid):
        error(f"sibyld is already running as pid {existing_pid}.")
        raise typer.Exit(1)

    SIBYL_RUN_DIR.mkdir(parents=True, exist_ok=True)
    log = SIBYLD_LOG_FILE.open("a", encoding="utf-8")
    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        log.close()
    SIBYLD_PID_FILE.write_text(f"{process.pid}\n")
    success(f"Started sibyld as pid {process.pid}")
    console.print(f"  [{NEON_CYAN}]Context:[/{NEON_CYAN}] {ctx.name} -> {ctx.server_url}")
    console.print(f"  [{NEON_CYAN}]Logs:[/{NEON_CYAN}]    {SIBYLD_LOG_FILE}")


def stop(
    timeout: Annotated[float, typer.Option("--timeout", help="Seconds to wait before failing")] = 5.0,
) -> None:
    """Stop the background local embedded daemon."""
    pid = read_pid()
    if pid is None:
        info("No sibyld pid file found.")
        return
    if not pid_alive(pid):
        SIBYLD_PID_FILE.unlink(missing_ok=True)
        info(f"Removed stale sibyld pid file for pid {pid}.")
        return

    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not pid_alive(pid):
            SIBYLD_PID_FILE.unlink(missing_ok=True)
            success("sibyld stopped")
            return
        time.sleep(0.1)

    error(f"sibyld pid {pid} did not stop within {timeout:g}s.")
    raise typer.Exit(1)
