"""Source import jobs backed by core source adapters."""

from __future__ import annotations

from typing import Any

import structlog

from sibyl_core.models.sources import SourceImportCheckpoint
from sibyl_core.services.mailbox_adapter import ensure_mailbox_adapter_registered
from sibyl_core.services.source_adapters import (
    RawMemoryRememberer,
    get_source_adapter,
    import_source_batch,
)

log = structlog.get_logger()


async def import_source_archive(
    ctx: dict[str, Any],  # noqa: ARG001
    source_uri: str,
    *,
    organization_id: str,
    principal_id: str,
    adapter_name: str = "mbox",
    options: dict[str, Any] | None = None,
    checkpoint: dict[str, Any] | None = None,
    batch_size: int = 100,
    promotion_preview_approved: bool = False,
    remember: RawMemoryRememberer | None = None,
) -> dict[str, Any]:
    """Import a local source archive into raw memory through a source adapter."""
    ensure_mailbox_adapter_registered()
    adapter = get_source_adapter(adapter_name)
    manifest = await adapter.prepare_manifest(
        source_uri=source_uri,
        options=options or {},
    )
    checkpoint_model = (
        SourceImportCheckpoint.model_validate(checkpoint) if checkpoint is not None else None
    )
    import_kwargs: dict[str, Any] = {}
    if remember is not None:
        import_kwargs["remember"] = remember

    result = await import_source_batch(
        adapter,
        manifest,
        organization_id=organization_id,
        principal_id=principal_id,
        checkpoint=checkpoint_model,
        batch_size=batch_size,
        promotion_preview_approved=promotion_preview_approved,
        **import_kwargs,
    )
    payload = {
        "adapter_name": manifest.adapter_name,
        "adapter_version": manifest.adapter_version,
        "source_identity": manifest.source_identity,
        "source_uri": manifest.source_uri,
        "source_version": manifest.source_version,
        "imported_count": result.imported_count,
        "skipped_count": result.skipped_count,
        "raw_memory_ids": list(result.raw_memory_ids),
        "dedupe_keys": list(result.dedupe_keys),
        "skipped_records": [
            skipped.model_dump(mode="json") for skipped in result.skipped_records
        ],
        "checkpoint": result.checkpoint.model_dump(mode="json") if result.checkpoint else None,
        "policy": {
            "privacy_class": result.policy.privacy_class.value,
            "target_memory_scope": result.policy.target_memory_scope.value,
            "target_scope_key": result.policy.target_scope_key,
            "requires_promotion_preview": result.policy.requires_promotion_preview,
            "reasons": list(result.policy.reasons),
        },
    }
    log.info(
        "source_import_archive_complete",
        adapter_name=manifest.adapter_name,
        source_uri=manifest.source_uri,
        imported_count=result.imported_count,
        skipped_count=result.skipped_count,
    )
    return payload


__all__ = ["import_source_archive"]
