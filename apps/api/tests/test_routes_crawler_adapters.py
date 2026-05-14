from __future__ import annotations

from unittest.mock import patch

import pytest

from sibyl.api.routes.crawler import list_import_adapters
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
