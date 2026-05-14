from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from sibyl.api.routes.crawler import _resolve_route_import_source_uri, list_import_adapters
from sibyl.config import settings
from sibyl_core.models.sources import (
    SourceAdapterCapability,
    SourceAdapterDescriptor,
    SourcePrivacyClass,
    SourceTransformBehavior,
)
from sibyl_core.services.source_adapters import clear_source_adapters


@pytest.mark.asyncio
async def test_list_import_adapters_returns_registered_contracts() -> None:
    descriptor = SourceAdapterDescriptor(
        name="mailbox",
        version="1.0",
        source_type="mailbox",
        display_name="Mailbox",
        capabilities=[SourceAdapterCapability.CHECKPOINTS],
        default_privacy_class=SourcePrivacyClass.PERSONAL,
        transform_behavior=SourceTransformBehavior.RAW,
        metadata_schema={"message_id": "string"},
        supports_incremental=True,
    )

    with patch("sibyl.api.routes.crawler.list_source_adapters", return_value=[descriptor]):
        response = await list_import_adapters()

    assert len(response.adapters) == 1
    adapter = response.adapters[0]
    assert adapter.name == "mailbox"
    assert adapter.capabilities == ["checkpoints"]
    assert adapter.default_privacy_class == "personal"
    assert adapter.metadata_schema == {"message_id": "string"}
    assert adapter.supports_incremental is True


@pytest.mark.asyncio
async def test_list_import_adapters_includes_builtin_mailbox() -> None:
    clear_source_adapters()
    try:
        response = await list_import_adapters()
    finally:
        clear_source_adapters()

    names = {adapter.name for adapter in response.adapters}

    assert "mbox" in names


def test_source_import_route_rejects_paths_outside_import_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import_root = tmp_path / "imports"
    import_root.mkdir()
    allowed = import_root / "mail.mbox"
    allowed.write_text("", encoding="utf-8")
    denied = tmp_path / "outside.mbox"
    denied.write_text("", encoding="utf-8")
    monkeypatch.setattr(settings, "source_import_dir", import_root)

    assert _resolve_route_import_source_uri(str(allowed)) == str(allowed.resolve())
    with pytest.raises(HTTPException) as exc:
        _resolve_route_import_source_uri(str(denied))

    assert exc.value.status_code == 403
    assert exc.value.detail == "source_import_path_denied"
