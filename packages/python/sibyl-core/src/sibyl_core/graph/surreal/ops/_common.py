"""Shared helpers for SurrealDB operations modules.

Graphiti's record-parser contracts expect dict-shaped records with specific
keys. SurrealDB returns nearly-identical shapes; these helpers smooth the
remaining edges (RecordID unwrapping, attribute merge, date normalization)
so the call sites in individual ops modules stay short.
"""

from __future__ import annotations

from typing import Any


def normalize_record(record: Any) -> dict[str, Any] | None:
    """Coerce a SurrealDB row into the dict shape Graphiti parsers expect.

    SurrealDB returns records as Python dicts keyed by field name, with an
    ``id`` field holding a ``RecordID`` object. Graphiti parsers don't use
    ``id`` directly (they key off the ``uuid`` string field) so we can drop
    it. Returns ``None`` when the input is empty so callers short-circuit.
    """
    if record is None:
        return None
    if not isinstance(record, dict):
        return None
    out = dict(record)
    out.pop("id", None)
    # Graphiti's entity_node_from_record mutates attributes in place, so we
    # always return a fresh mutable dict. Missing optional fields default
    # to the right empty value.
    if "attributes" not in out or out["attributes"] is None:
        out["attributes"] = {}
    if "labels" not in out or out["labels"] is None:
        out["labels"] = []
    return out


def normalize_records(result: Any) -> list[dict[str, Any]]:
    """Coerce an ``execute_query`` result into a list of record dicts.

    SurrealDB SELECT statements return a list of dicts directly. This helper
    tolerates nested shapes (list-of-list, dict-with-result) so callers can
    stay forgiving.
    """
    if result is None:
        return []
    if isinstance(result, dict):
        single = normalize_record(result)
        return [single] if single is not None else []
    if isinstance(result, list):
        out: list[dict[str, Any]] = []
        for item in result:
            if isinstance(item, list):
                # Nested list (eg. multi-statement leak); flatten one level.
                out.extend(n for r in item if (n := normalize_record(r)) is not None)
            elif (n := normalize_record(item)) is not None:
                out.append(n)
        return out
    return []


__all__ = ["normalize_record", "normalize_records"]
