from __future__ import annotations

from pathlib import Path

from tools.baselines.common import read_jsonl, resolve_pointer, validate_expectations, write_jsonl

EXPECTED_ERROR_COUNT = 3


def test_resolve_pointer_handles_nested_maps_and_lists() -> None:
    payload = {
        "body": {
            "results": [
                {"name": "Baseline Corpus Episode"},
            ]
        }
    }

    assert resolve_pointer(payload, "/body/results/0/name") == "Baseline Corpus Episode"


def test_validate_expectations_supports_required_equals_minimums_and_list_contains() -> None:
    payload = {
        "status_code": 200,
        "body": {"total": 2, "results": [{"name": "Baseline Corpus Episode"}]},
    }
    expect = {
        "required": ["/body/results"],
        "equals": {"/status_code": 200},
        "minimums": {"/body/total": 1},
        "list_contains": [
            {"pointer": "/body/results", "match": {"name": "Baseline Corpus Episode"}},
        ],
        "serialized_contains": ["Baseline Corpus Episode"],
    }

    assert validate_expectations(payload, expect) == []


def test_validate_expectations_reports_mismatches() -> None:
    payload = {"status_code": 500, "body": {"results": []}}
    expect = {
        "equals": {"/status_code": 200},
        "minimums": {"/body/total": 1},
        "list_contains": [{"pointer": "/body/results", "match": {"name": "Missing"}}],
    }

    errors = validate_expectations(payload, expect)

    assert len(errors) == EXPECTED_ERROR_COUNT
    assert "expected 200" in errors[0]
    assert "missing pointer for minimum check" in errors[1]
    assert "did not contain match" in errors[2]


def test_jsonl_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    rows = [{"id": "case-a"}, {"id": "case-b"}]

    write_jsonl(path, rows)

    assert read_jsonl(path) == rows
