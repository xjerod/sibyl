from __future__ import annotations

import json
from pathlib import Path

import pytest
from tools.chaos import archive_probe

from sibyl_core.migrate.archive import GRAPH_FILENAME, build_manifest, write_archive


def _write_archive(path: Path) -> None:
    graph_payload = {
        "version": "2.0",
        "created_at": "2026-04-19T20:00:00+00:00",
        "organization_id": "org-123",
        "entity_count": 1,
        "relationship_count": 0,
        "entities": [{"id": "entity-1"}],
        "relationships": [],
    }
    graph_bytes = json.dumps(graph_payload).encode("utf-8")
    manifest = build_manifest(
        organization_id="org-123",
        source_store="legacy",
        files={GRAPH_FILENAME: graph_bytes},
        file_metadata={GRAPH_FILENAME: {"kind": "graph"}},
    )
    write_archive(path, manifest=manifest, files={GRAPH_FILENAME: graph_bytes})


def test_probe_archive_detects_all_default_scenarios(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    archive_path = tmp_path / "migration.tar.gz"
    _write_archive(archive_path)

    exit_code = archive_probe.main([str(archive_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "checksum: detected" in captured.out
    assert "count-drift: detected" in captured.out
    assert "org-mismatch: detected" in captured.out
    assert "Chaos probe passed" in captured.out


def test_probe_archive_fails_when_base_archive_is_invalid(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    archive_path = tmp_path / "migration.tar.gz"
    _write_archive(archive_path)
    loaded = archive_probe.load_archive(archive_path)
    tampered_dir = tmp_path / "tampered"
    tampered_dir.mkdir()
    (tampered_dir / "manifest.json").write_text(
        json.dumps(loaded.manifest.to_dict(), indent=2),
        encoding="utf-8",
    )
    (tampered_dir / GRAPH_FILENAME).write_text('{"tampered": true}\n', encoding="utf-8")

    exit_code = archive_probe.main([str(tampered_dir)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Base archive is already invalid" in captured.out
