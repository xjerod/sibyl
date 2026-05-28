from __future__ import annotations

from importlib import import_module
from typing import Any

import pytest

from sibyl_core.utils.log_safety import fingerprint_text, query_log_fields, text_log_fields


class FakeLog:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict[str, Any]]] = []

    def debug(self, event: str, **fields: Any) -> None:
        self.events.append(("debug", event, fields))

    def info(self, event: str, **fields: Any) -> None:
        self.events.append(("info", event, fields))

    def warning(self, event: str, **fields: Any) -> None:
        self.events.append(("warning", event, fields))

    def exception(self, event: str, **fields: Any) -> None:
        self.events.append(("exception", event, fields))


def test_fingerprint_text_normalizes_whitespace() -> None:
    assert fingerprint_text("secret literal token") == fingerprint_text(" secret\nliteral  token ")


def test_query_log_fields_do_not_include_query_text() -> None:
    query = "task notification bzzmrxv82 tool toolu_secret"

    fields = query_log_fields(query)

    assert fields == {
        "query_hash": fields["query_hash"],
        "query_length": len(query),
        "query_word_count": 5,
    }
    assert len(str(fields["query_hash"])) == 12
    assert "query" not in fields
    assert "toolu_secret" not in str(fields)


def test_text_log_fields_uses_custom_field_prefix() -> None:
    fields = text_log_fields("alpha beta", field="prompt")

    assert set(fields) == {"prompt_hash", "prompt_length", "prompt_word_count"}


@pytest.mark.asyncio
async def test_unified_search_log_fingerprints_query(monkeypatch: pytest.MonkeyPatch) -> None:
    search_module = import_module("sibyl_core.tools.search")
    fake_log = FakeLog()
    monkeypatch.setattr(search_module, "log", fake_log)
    query = "task notification bzzmrxv82 tool toolu_secret"

    response = await search_module.search(
        query=query,
        organization_id="org_123",
        include_documents=False,
        include_graph=False,
    )

    _level, event, fields = fake_log.events[0]
    assert event == "unified_search"
    assert response.query == query
    assert fields["query_hash"] == fingerprint_text(query)
    assert "query" not in fields
    assert query not in str(fields)
    assert "toolu_secret" not in str(fields)


@pytest.mark.asyncio
async def test_hybrid_search_logs_fingerprint_query(monkeypatch: pytest.MonkeyPatch) -> None:
    from sibyl_core.retrieval import hybrid as hybrid_module

    class FakeEntityManager:
        async def search(self, *_args: Any, **_kwargs: Any) -> list[Any]:
            return []

    fake_log = FakeLog()
    monkeypatch.setattr(hybrid_module, "log", fake_log)
    query = "classify event type pr_opened timestamp secret"

    result = await hybrid_module.hybrid_search(
        query=query,
        client=object(),
        entity_manager=FakeEntityManager(),
        group_id="org_123",
    )

    assert result.metadata["query"] == query
    assert fake_log.events
    for _level, _event, fields in fake_log.events:
        assert "query" not in fields
        assert query not in str(fields)
        assert "secret" not in str(fields)
