"""Data export CLI commands.

Export graph data to JSON/CSV files.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from sibyl.cli.common import (
    error,
    info,
    print_db_hint,
    run_async,
    success,
)
from sibyl_core.models.entities import EntityType

app = typer.Typer(
    name="export",
    help="Export data to files (JSON/CSV)",
    no_args_is_help=True,
)

GRAPH_ENTITY_TYPES = (
    EntityType.PATTERN,
    EntityType.RULE,
    EntityType.TEMPLATE,
    EntityType.TASK,
    EntityType.PROJECT,
    EntityType.EPISODE,
)
GRAPH_ENTITY_PAGE_SIZE = 1000
GRAPH_RELATIONSHIP_PAGE_SIZE = 5000
EXPLORE_PAGE_SIZE = 200


async def _list_entities_by_type_paginated(
    entity_mgr: object,
    entity_type: EntityType,
    *,
    page_size: int,
) -> list[object]:
    entities: list[object] = []
    offset = 0

    while True:
        batch = await entity_mgr.list_by_type(entity_type, limit=page_size, offset=offset)
        if not batch:
            break

        entities.extend(batch)
        if len(batch) < page_size:
            break

        offset += page_size

    return entities


async def _list_relationships_paginated(
    rel_mgr: object,
    *,
    page_size: int,
) -> list[object]:
    relationships: list[object] = []
    offset = 0

    while True:
        batch = await rel_mgr.list_all(limit=page_size, offset=offset)
        if not batch:
            break

        relationships.extend(batch)
        if len(batch) < page_size:
            break

        offset += page_size

    return relationships


async def _explore_paginated(**filters: object) -> list[object]:
    from sibyl_core.tools.core import explore

    entities: list[object] = []
    offset = 0

    while True:
        response = await explore(limit=EXPLORE_PAGE_SIZE, offset=offset, **filters)
        batch = list(response.entities or [])
        if not batch:
            break

        entities.extend(batch)
        if not getattr(response, "has_more", False):
            break

        offset += len(batch)

    return entities


@app.command("graph")
def export_graph(
    output: Annotated[Path, typer.Option("--output", "-o", help="Output file path")] = Path(
        "sibyl_graph.json"
    ),
    org_id: Annotated[
        str,
        typer.Option("--org-id", help="Organization UUID (required for multi-tenant graph)"),
    ] = "",
) -> None:
    """Export the full graph to JSON."""
    if not org_id:
        error("--org-id is required for graph operations")
        raise typer.Exit(code=1)

    @run_async
    async def _export() -> None:
        from sibyl_core.services.native_graph import get_native_graph_runtime

        try:
            runtime = await get_native_graph_runtime(org_id)
            entity_mgr = runtime.entity_manager
            rel_mgr = runtime.relationship_manager

            # Get all entities
            entities = []
            for entity_type in GRAPH_ENTITY_TYPES:
                type_entities = await _list_entities_by_type_paginated(
                    entity_mgr,
                    entity_type,
                    page_size=GRAPH_ENTITY_PAGE_SIZE,
                )
                entities.extend(type_entities)

            # Get all relationships
            relationships = await _list_relationships_paginated(
                rel_mgr,
                page_size=GRAPH_RELATIONSHIP_PAGE_SIZE,
            )

            # Build export data
            exported_at = datetime.now(UTC).isoformat()
            export_data = {
                "version": "2.0",
                "created_at": exported_at,
                "organization_id": org_id,
                "entity_count": len(entities),
                "relationship_count": len(relationships),
                "metadata": {
                    "exported_at": exported_at,
                    "entity_count": len(entities),
                    "relationship_count": len(relationships),
                },
                "entities": [e.model_dump() for e in entities],
                "relationships": [r.model_dump() for r in relationships],
            }

            # Write to file (sync I/O after async work)
            with open(output, "w") as f:  # noqa: ASYNC230
                json.dump(export_data, f, indent=2, default=str)

            success(f"Graph exported to {output}")
            info(f"Entities: {len(entities)}, Relationships: {len(relationships)}")

        except Exception as e:
            error(f"Export failed: {e}")
            print_db_hint()

    _export()


@app.command("tasks")
def export_tasks(
    output: Annotated[Path, typer.Option("--output", "-o", help="Output file path")] = Path(
        "tasks.csv"
    ),
    project: Annotated[
        str | None, typer.Option("--project", "-p", help="Filter by project")
    ] = None,
    status: Annotated[str | None, typer.Option("--status", "-s", help="Filter by status")] = None,
    format_: Annotated[
        str, typer.Option("--format", "-f", help="Output format: json, csv")
    ] = "csv",
) -> None:
    """Export tasks to CSV or JSON."""

    @run_async
    async def _export() -> None:
        try:
            entities = await _explore_paginated(
                mode="list",
                types=["task"],
                project=project,
                status=status,
            )

            if not entities:
                info("No tasks to export")
                return

            if format_ == "json":
                output_path = output.with_suffix(".json")
                with open(output_path, "w") as f:  # noqa: ASYNC230
                    json.dump([e.model_dump() for e in entities], f, indent=2, default=str)
            else:
                import csv

                output_path = output.with_suffix(".csv")
                with open(output_path, "w", newline="") as f:  # noqa: ASYNC230
                    writer = csv.writer(f)
                    writer.writerow(
                        [
                            "id",
                            "title",
                            "description",
                            "status",
                            "priority",
                            "project_id",
                            "feature",
                            "assignees",
                            "created_at",
                        ]
                    )
                    for e in entities:
                        meta = e.metadata or {}
                        writer.writerow(
                            [
                                e.id,
                                e.name,
                                e.description or "",
                                meta.get("status", ""),
                                meta.get("priority", ""),
                                meta.get("project_id", ""),
                                meta.get("feature", ""),
                                ",".join(meta.get("assignees", [])),
                                str(e.created_at) if e.created_at else "",
                            ]
                        )

            success(f"Exported {len(entities)} tasks to {output_path}")

        except Exception as e:
            error(f"Export failed: {e}")
            print_db_hint()

    _export()


@app.command("entities")
def export_entities(
    entity_type: Annotated[str, typer.Option("--type", "-T", help="Entity type to export")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Output file path")] = Path(
        "entities.json"
    ),
    format_: Annotated[
        str, typer.Option("--format", "-f", help="Output format: json, csv")
    ] = "json",
) -> None:
    """Export entities of a specific type."""

    @run_async
    async def _export() -> None:
        try:
            entities = await _explore_paginated(
                mode="list",
                types=[entity_type],
            )

            if not entities:
                info(f"No {entity_type}s to export")
                return

            if format_ == "json":
                output_path = output.with_suffix(".json")
                with open(output_path, "w") as f:  # noqa: ASYNC230
                    json.dump([e.model_dump() for e in entities], f, indent=2, default=str)
            else:
                import csv

                output_path = output.with_suffix(".csv")
                with open(output_path, "w", newline="") as f:  # noqa: ASYNC230
                    writer = csv.writer(f)
                    writer.writerow(["id", "name", "type", "description", "created_at"])
                    for e in entities:
                        writer.writerow(
                            [
                                e.id,
                                e.name,
                                e.type,
                                e.description or "",
                                str(e.created_at) if e.created_at else "",
                            ]
                        )

            success(f"Exported {len(entities)} {entity_type}(s) to {output_path}")

        except Exception as e:
            error(f"Export failed: {e}")
            print_db_hint()

    _export()
