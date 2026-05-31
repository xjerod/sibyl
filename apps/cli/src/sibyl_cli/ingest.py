"""Source ingestion CLI commands."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Annotated, Any, cast

import typer

from sibyl_cli.client import SibylClientError, get_client
from sibyl_cli.common import (
    CORAL,
    console,
    create_table,
    error,
    handle_client_error,
    info,
    print_json,
    run_async,
    success,
)

app = typer.Typer(
    name="ingest",
    help="Import local source archives into raw memory",
    no_args_is_help=True,
)

_TERMINAL_STATUSES = {"completed", "failed", "canceled"}


def _resolve_source_path(source: Path) -> str:
    path = source.expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if path.is_symlink():
        error(f"Transcript source cannot be a symlink: {path}")
        raise typer.Exit(1)
    path = path.resolve()
    if not path.exists():
        error(f"Transcript source not found: {path}")
        raise typer.Exit(1)
    return str(path)


def _scope_label(data: dict[str, object]) -> str:
    scope = str(data.get("target_memory_scope") or "private")
    if scope_key := data.get("target_scope_key"):
        return f"{scope}:{scope_key}"
    return scope


def _progress(data: dict[str, object]) -> dict[str, object]:
    progress = data.get("progress")
    return cast("dict[str, object]", progress) if isinstance(progress, dict) else {}


def _print_import_status(data: dict[str, object]) -> None:
    progress = _progress(data)
    table = create_table("Source Import", "Field", "Value", expand=False)
    table.add_row("Import Id", str(data.get("import_id") or ""))
    table.add_row("Status", str(data.get("status") or ""))
    table.add_row("Adapter", str(data.get("adapter_name") or ""))
    table.add_row("Source", str(data.get("source_identity") or ""))
    table.add_row("Target scope", _scope_label(data))
    table.add_row("Imported", str(progress.get("imported_count") or 0))
    table.add_row("Deduped", str(progress.get("dedupe_count") or 0))
    table.add_row("Skipped", str(progress.get("skipped_count") or 0))
    table.add_row("Errors", str(progress.get("error_count") or 0))
    console.print(table)

    raw_memory_ids = data.get("raw_memory_ids")
    if isinstance(raw_memory_ids, list) and raw_memory_ids:
        console.print("\n[bold]Raw memory receipts[/bold]")
        for raw_memory_id in raw_memory_ids[:18]:
            console.print(f"  [{CORAL}]{raw_memory_id}[/{CORAL}]")


async def _wait_for_import(
    client: Any,
    import_id: str,
    *,
    poll_interval: float,
    timeout: float | None,
) -> dict[str, object]:
    started_at = time.monotonic()
    while True:
        data = await client.ingestion_source_import_status(import_id)
        if str(data.get("status") or "") in _TERMINAL_STATUSES:
            return data
        if timeout is not None and time.monotonic() - started_at >= timeout:
            return data
        await asyncio.sleep(poll_interval)


async def _start_transcript_import(
    *,
    adapter_name: str,
    source: Path,
    scope: str,
    scope_key: str | None,
    source_identity: str | None,
    batch_size: int,
    drain: bool,
    poll_interval: float,
    timeout: float | None,
    json_out: bool,
) -> None:
    source_uri = _resolve_source_path(source)
    options: dict[str, object] = {}
    if source_identity:
        options["source_identity"] = source_identity

    try:
        async with get_client() as client:
            data = await client.start_source_import(
                source_uri=source_uri,
                adapter_name=adapter_name,
                target_memory_scope=scope,
                target_scope_key=scope_key,
                options=options,
                batch_size=batch_size,
                promotion_preview_approved=False,
            )
            if drain:
                import_id = str(data.get("import_id") or "")
                if import_id:
                    if not json_out:
                        info(f"Waiting for import drain {import_id}")
                    data = await _wait_for_import(
                        client,
                        import_id,
                        poll_interval=poll_interval,
                        timeout=timeout,
                    )
            status = str(data.get("status") or "")
            if json_out:
                print_json(data)
                if status in {"failed", "canceled"}:
                    raise typer.Exit(1)
                return

            if status == "completed":
                success("Import completed")
            elif status in {"failed", "canceled"}:
                _print_import_status(data)
                error(f"Import {status}")
                raise typer.Exit(1)
            elif drain and status not in _TERMINAL_STATUSES:
                info("Import drain is still running")
            else:
                success("Import queued")
            _print_import_status(data)
    except SibylClientError as exc:
        handle_client_error(exc, invalid_request_label="Import rejected")


@app.command("claude-code")
def ingest_claude_code(
    source: Annotated[Path, typer.Argument(help="Claude Code JSONL file or directory")],
    scope: Annotated[str, typer.Option("--scope", help="Target memory scope")] = "private",
    scope_key: Annotated[
        str | None,
        typer.Option("--scope-key", help="Target scope key for project/team/shared scopes"),
    ] = None,
    source_identity: Annotated[
        str | None,
        typer.Option("--source-identity", help="Stable identity for moved transcript exports"),
    ] = None,
    batch_size: Annotated[int, typer.Option("--batch-size", help="Import batch size")] = 100,
    drain: Annotated[bool, typer.Option("--drain", help="Wait for the background drain")] = False,
    poll_interval: Annotated[
        float,
        typer.Option("--poll-interval", help="Seconds between drain status checks"),
    ] = 1.0,
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", help="Maximum seconds to wait when draining"),
    ] = None,
    json_out: Annotated[
        bool, typer.Option("--json", "-j", help="JSON output for scripting")
    ] = False,
) -> None:
    """Import Claude Code transcript JSONL."""

    @run_async
    async def _run() -> None:
        await _start_transcript_import(
            adapter_name="claude_code_jsonl",
            source=source,
            scope=scope,
            scope_key=scope_key,
            source_identity=source_identity,
            batch_size=batch_size,
            drain=drain,
            poll_interval=poll_interval,
            timeout=timeout,
            json_out=json_out,
        )

    _run()


@app.command("codex")
def ingest_codex(
    source: Annotated[Path, typer.Argument(help="Codex JSONL file or directory")],
    scope: Annotated[str, typer.Option("--scope", help="Target memory scope")] = "private",
    scope_key: Annotated[
        str | None,
        typer.Option("--scope-key", help="Target scope key for project/team/shared scopes"),
    ] = None,
    source_identity: Annotated[
        str | None,
        typer.Option("--source-identity", help="Stable identity for moved transcript exports"),
    ] = None,
    batch_size: Annotated[int, typer.Option("--batch-size", help="Import batch size")] = 100,
    drain: Annotated[bool, typer.Option("--drain", help="Wait for the background drain")] = False,
    poll_interval: Annotated[
        float,
        typer.Option("--poll-interval", help="Seconds between drain status checks"),
    ] = 1.0,
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", help="Maximum seconds to wait when draining"),
    ] = None,
    json_out: Annotated[
        bool, typer.Option("--json", "-j", help="JSON output for scripting")
    ] = False,
) -> None:
    """Import Codex transcript JSONL."""

    @run_async
    async def _run() -> None:
        await _start_transcript_import(
            adapter_name="codex_jsonl",
            source=source,
            scope=scope,
            scope_key=scope_key,
            source_identity=source_identity,
            batch_size=batch_size,
            drain=drain,
            poll_interval=poll_interval,
            timeout=timeout,
            json_out=json_out,
        )

    _run()
