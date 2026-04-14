"""Raw capture archive CLI commands."""

from typing import Annotated

import typer

from sibyl_cli.client import SibylClientError, get_client
from sibyl_cli.common import (
    CORAL,
    ELECTRIC_PURPLE,
    NEON_CYAN,
    console,
    create_panel,
    create_table,
    print_json,
    run_async,
    success,
    truncate,
)
from sibyl_cli.common import handle_client_error as _handle_client_error

app = typer.Typer(
    name="archive",
    help="Browse archived raw quick captures",
    no_args_is_help=True,
)


@app.command("list")
def list_archive(
    entity_type: Annotated[
        str | None, typer.Option("--type", "-t", help="Filter by entity type")
    ] = None,
    capture_surface: Annotated[
        str | None, typer.Option("--surface", help="Filter by capture surface")
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 20,
    offset: Annotated[int, typer.Option("--offset", help="Skip first N results")] = 0,
    json_out: Annotated[
        bool, typer.Option("--json", "-j", help="JSON output (for scripting)")
    ] = False,
) -> None:
    """List archived raw quick captures."""

    @run_async
    async def _list() -> None:
        try:
            async with get_client() as client:
                response = await client.list_raw_captures(
                    entity_type=entity_type,
                    capture_surface=capture_surface,
                    limit=limit,
                    offset=offset,
                )

                if json_out:
                    print_json(response)
                    return

                captures = response.get("captures", [])
                if not captures:
                    success("No archived raw captures found")
                    return

                table = create_table("Raw Capture Archive", "ID", "Title", "Type", "Surface")
                for capture in captures:
                    table.add_row(
                        capture.get("id", ""),
                        truncate(capture.get("title", ""), 46),
                        capture.get("entity_type", ""),
                        capture.get("capture_surface") or "unknown",
                    )
                console.print(table)

                if response.get("has_more"):
                    console.print(
                        f"\n[dim]More captures available. Try --offset {offset + limit}.[/dim]"
                    )
        except SibylClientError as e:
            _handle_client_error(e)

    _list()


@app.command("show")
def show_archive_capture(
    capture_id: Annotated[str, typer.Argument(help="Raw capture ID")],
    json_out: Annotated[
        bool, typer.Option("--json", "-j", help="JSON output (for scripting)")
    ] = False,
) -> None:
    """Show a single archived raw quick capture."""

    @run_async
    async def _show() -> None:
        try:
            async with get_client() as client:
                capture = await client.get_raw_capture(capture_id)

                if json_out:
                    print_json(capture)
                    return

                lines = [
                    f"[{ELECTRIC_PURPLE}]Title:[/{ELECTRIC_PURPLE}] {capture.get('title', '')}",
                    f"[{ELECTRIC_PURPLE}]Type:[/{ELECTRIC_PURPLE}] {capture.get('entity_type', '')}",
                    f"[{ELECTRIC_PURPLE}]Archive ID:[/{ELECTRIC_PURPLE}] {capture.get('id', '')}",
                ]

                if capture.get("entity_id"):
                    lines.append(
                        f"[{ELECTRIC_PURPLE}]Entity ID:[/{ELECTRIC_PURPLE}] {capture.get('entity_id', '')}"
                    )
                if capture.get("capture_surface"):
                    lines.append(
                        f"[{ELECTRIC_PURPLE}]Surface:[/{ELECTRIC_PURPLE}] {capture.get('capture_surface', '')}"
                    )
                if capture.get("created_at"):
                    lines.append(
                        f"[{ELECTRIC_PURPLE}]Captured:[/{ELECTRIC_PURPLE}] {capture.get('created_at', '')}"
                    )
                if capture.get("tags"):
                    lines.append(
                        f"[{ELECTRIC_PURPLE}]Tags:[/{ELECTRIC_PURPLE}] {', '.join(capture.get('tags', []))}"
                    )

                metadata = capture.get("metadata", {})
                if metadata:
                    lines.extend(["", f"[{CORAL}]Metadata:[/{CORAL}]"])
                    for key, value in metadata.items():
                        lines.append(f"  {key}: {truncate(str(value), 80)}")

                lines.extend(
                    [
                        "",
                        f"[{NEON_CYAN}]Raw Content:[/{NEON_CYAN}]",
                        capture.get("raw_content", ""),
                    ]
                )

                console.print(create_panel("\n".join(lines), title="Raw Capture"))
        except SibylClientError as e:
            _handle_client_error(e)

    _show()
