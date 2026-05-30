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
    ensure_schema_version_table,
    get_schema_version,
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
CONTENT_SCHEMA_CURRENT_VERSION = 4
CONTENT_SCHEMA_NAME = "content"

_SCHEMA_DIR = Path(__file__).with_name("schemas") / "content"


def _load_schema_file(filename: str) -> str:
    return (_SCHEMA_DIR / filename).read_text(encoding="utf-8").format(EMBEDDING_DIM=EMBEDDING_DIM)


CONTENT_ANALYZER_DEFINITIONS = _load_schema_file("01_analyzers.surql")
CONTENT_SCHEMA_DEFINITIONS = _load_schema_file("10_tables.surql")

CONTENT_SOURCE_URL_SCOPE_MIGRATION_DEFINITIONS = """
REMOVE INDEX IF EXISTS idx_crawl_sources_url ON TABLE crawl_sources;
DEFINE INDEX IF NOT EXISTS idx_crawl_sources_org_url
    ON crawl_sources FIELDS organization_id, url UNIQUE;
"""

CONTENT_DOCUMENT_URL_SCOPE_MIGRATION_DEFINITIONS = """
REMOVE INDEX IF EXISTS idx_crawled_documents_url ON TABLE crawled_documents;
DEFINE INDEX IF NOT EXISTS idx_crawled_documents_source_url
    ON crawled_documents FIELDS source_id, url UNIQUE;
"""

CONTENT_CHILD_SCOPE_MIGRATION_DEFINITIONS = """
DEFINE FIELD IF NOT EXISTS organization_id ON crawled_documents TYPE string DEFAULT '';
DEFINE FIELD IF NOT EXISTS organization_id ON document_chunks TYPE string DEFAULT '';
DEFINE FIELD IF NOT EXISTS source_id ON document_chunks TYPE string DEFAULT '';
UPDATE crawled_documents SET
    organization_id = (SELECT VALUE organization_id FROM crawl_sources
        WHERE uuid = $parent.source_id LIMIT 1)[0]
    WHERE organization_id = '' OR organization_id = NONE;
UPDATE document_chunks SET
    source_id = (SELECT VALUE source_id FROM crawled_documents
        WHERE uuid = $parent.document_id LIMIT 1)[0],
    organization_id = (SELECT VALUE organization_id FROM crawled_documents
        WHERE uuid = $parent.document_id LIMIT 1)[0]
    WHERE source_id = '' OR source_id = NONE
        OR organization_id = '' OR organization_id = NONE;
DEFINE INDEX IF NOT EXISTS idx_crawled_documents_org_source
    ON crawled_documents FIELDS organization_id, source_id;
DEFINE INDEX IF NOT EXISTS idx_document_chunks_org_source
    ON document_chunks FIELDS organization_id, source_id;
DEFINE INDEX IF NOT EXISTS idx_document_chunks_org_source_entities
    ON document_chunks FIELDS organization_id, source_id, has_entities;
DEFINE INDEX IF NOT EXISTS idx_document_chunks_org_document
    ON document_chunks FIELDS organization_id, document_id;
"""


def _content_schema_migrations(*, url: str) -> tuple[SchemaMigration, ...]:
    compatible_schema = render_fulltext_compatible_sql(
        CONTENT_SCHEMA_DEFINITIONS,
        url=url,
    )
    return (
        SchemaMigration(
            version=1,
            name="content_schema_bootstrap",
            statements=tuple(
                split_statements(CONTENT_ANALYZER_DEFINITIONS) + split_statements(compatible_schema)
            ),
        ),
        SchemaMigration(
            version=2,
            name="content_source_url_org_scope",
            statements=tuple(split_statements(CONTENT_SOURCE_URL_SCOPE_MIGRATION_DEFINITIONS)),
        ),
        SchemaMigration(
            version=3,
            name="content_document_url_source_scope",
            statements=tuple(split_statements(CONTENT_DOCUMENT_URL_SCOPE_MIGRATION_DEFINITIONS)),
        ),
        SchemaMigration(
            version=4,
            name="content_child_scope_fields",
            statements=tuple(split_statements(CONTENT_CHILD_SCOPE_MIGRATION_DEFINITIONS)),
        ),
    )


async def bootstrap_content_schema(client: SurrealContentClient, *, reset: bool = False) -> None:
    if reset:
        for table in (*CONTENT_TABLES, SCHEMA_VERSION_TABLE):
            await client.execute_query(f"REMOVE TABLE IF EXISTS {table};")

    await _assert_content_migrations_safe(client)
    await apply_schema_migrations(
        client.execute_query,
        _content_schema_migrations(url=getattr(client, "_url", "")),
        name=CONTENT_SCHEMA_NAME,
        scope="content_schema_migration",
    )


async def _assert_content_migrations_safe(client: SurrealContentClient) -> None:
    await ensure_schema_version_table(
        client.execute_query,
        scope="content_schema_migration_version",
    )
    current_version = await get_schema_version(client.execute_query, name=CONTENT_SCHEMA_NAME)
    if current_version < 2:
        duplicates = await _duplicate_count_rows(
            client,
            """
            SELECT organization_id, url, count() AS total
            FROM crawl_sources
            WHERE organization_id != NONE AND url != ''
            GROUP BY organization_id, url;
            """,
        )
        if duplicates:
            raise RuntimeError(
                "Cannot migrate crawl_sources URL uniqueness: duplicate "
                "organization_id/url rows exist"
            )
    if current_version < 3:
        duplicates = await _duplicate_count_rows(
            client,
            """
            SELECT source_id, url, count() AS total
            FROM crawled_documents
            WHERE source_id != NONE AND url != ''
            GROUP BY source_id, url;
            """,
        )
        if duplicates:
            raise RuntimeError(
                "Cannot migrate crawled_documents URL uniqueness: duplicate "
                "source_id/url rows exist"
            )
    if current_version < 4:
        missing_source_id = await _matching_rows(
            client,
            """
            SELECT uuid FROM crawled_documents
            WHERE source_id = NONE OR source_id = ''
            LIMIT 1;
            """,
        )
        if missing_source_id:
            raise RuntimeError(
                "Cannot migrate crawled_documents organization scope: source_id is missing"
            )
        orphan_documents = await _matching_rows(
            client,
            """
            SELECT uuid, source_id FROM crawled_documents
            WHERE (SELECT VALUE uuid FROM crawl_sources
                WHERE uuid = $parent.source_id LIMIT 1)[0] = NONE
            LIMIT 1;
            """,
        )
        if orphan_documents:
            raise RuntimeError(
                "Cannot migrate crawled_documents organization scope: "
                "parent crawl_sources rows are missing"
            )
        missing_document_id = await _matching_rows(
            client,
            """
            SELECT uuid FROM document_chunks
            WHERE document_id = NONE OR document_id = ''
            LIMIT 1;
            """,
        )
        if missing_document_id:
            raise RuntimeError(
                "Cannot migrate document_chunks content scope: document_id is missing"
            )
        orphan_chunks = await _matching_rows(
            client,
            """
            SELECT uuid, document_id FROM document_chunks
            WHERE (SELECT VALUE uuid FROM crawled_documents
                WHERE uuid = $parent.document_id LIMIT 1)[0] = NONE
            LIMIT 1;
            """,
        )
        if orphan_chunks:
            raise RuntimeError(
                "Cannot migrate document_chunks content scope: "
                "parent crawled_documents rows are missing"
            )


async def _matching_rows(
    client: SurrealContentClient,
    statement: str,
) -> list[dict[str, object]]:
    from sibyl_core.backends.surreal.records import normalize_records

    return normalize_records(await client.execute_query(statement))


async def _duplicate_count_rows(
    client: SurrealContentClient,
    statement: str,
) -> list[dict[str, object]]:
    rows = await _matching_rows(client, statement)
    return [row for row in rows if _coerce_int(row.get("total")) > 1]


def _coerce_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value:
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


__all__ = [
    "CONTENT_ANALYZER_DEFINITIONS",
    "CONTENT_CHILD_SCOPE_MIGRATION_DEFINITIONS",
    "CONTENT_DOCUMENT_URL_SCOPE_MIGRATION_DEFINITIONS",
    "CONTENT_SCHEMA_CURRENT_VERSION",
    "CONTENT_SCHEMA_DEFINITIONS",
    "CONTENT_SCHEMA_NAME",
    "CONTENT_SOURCE_URL_SCOPE_MIGRATION_DEFINITIONS",
    "CONTENT_TABLES",
    "bootstrap_content_schema",
]
