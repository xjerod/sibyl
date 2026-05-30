"""SurrealDB schema bootstrap for Sibyl content storage."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sibyl_core.backends.surreal.schema import render_fulltext_compatible_sql
from sibyl_core.backends.surreal.schema_helpers import split_statements
from sibyl_core.backends.surreal.schema_version import (
    SCHEMA_VERSION_TABLE,
    SchemaMigration,
    apply_schema_migrations,
)
from sibyl_core.config import core_config

# Document chunks use the OpenAI embedder dimension (text-embedding-3-small = 1536),
# which differs from the graph node embedder dimension. Keep them as separate
# constants so a graph dim change can't silently break content search and vice versa.
EMBEDDING_DIM = core_config.embedding_dimensions

if TYPE_CHECKING:
    from sibyl_core.backends.surreal.content_client import SurrealContentClient


CONTENT_TABLES = (
    "crawl_sources",
    "crawled_documents",
    "document_chunks",
    "raw_captures",
    "api_idempotency_records",
    "source_imports",
    "system_settings",
    "telemetry_rollups",
    "backup_settings",
    "backups",
)
CONTENT_SCHEMA_CURRENT_VERSION = 1
CONTENT_SCHEMA_NAME = "content"

_SCHEMA_DIR = Path(__file__).with_name("schemas") / "content"


def _load_schema_file(filename: str) -> str:
    return (_SCHEMA_DIR / filename).read_text(encoding="utf-8").format(EMBEDDING_DIM=EMBEDDING_DIM)


CONTENT_ANALYZER_DEFINITIONS = _load_schema_file("01_analyzers.surql")
CONTENT_SCHEMA_DEFINITIONS = _load_schema_file("10_tables.surql")


def _content_schema_migrations(*, url: str) -> tuple[SchemaMigration, ...]:
    compatible_schema = render_fulltext_compatible_sql(
        CONTENT_SCHEMA_DEFINITIONS,
        url=url,
    )
    return (
        SchemaMigration(
            version=CONTENT_SCHEMA_CURRENT_VERSION,
            name="content_schema_bootstrap",
            statements=tuple(
                split_statements(CONTENT_ANALYZER_DEFINITIONS) + split_statements(compatible_schema)
            ),
        ),
    )


async def bootstrap_content_schema(client: SurrealContentClient, *, reset: bool = False) -> None:
    if reset:
        for table in (*CONTENT_TABLES, SCHEMA_VERSION_TABLE):
            await client.execute_query(f"REMOVE TABLE IF EXISTS {table};")

    await apply_schema_migrations(
        client.execute_query,
        _content_schema_migrations(url=getattr(client, "_url", "")),
        name=CONTENT_SCHEMA_NAME,
        scope="content_schema_migration",
    )


__all__ = [
    "CONTENT_ANALYZER_DEFINITIONS",
    "CONTENT_SCHEMA_CURRENT_VERSION",
    "CONTENT_SCHEMA_DEFINITIONS",
    "CONTENT_SCHEMA_NAME",
    "CONTENT_TABLES",
    "bootstrap_content_schema",
]
