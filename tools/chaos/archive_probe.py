#!/usr/bin/env python3
"""Mutate migration archives and assert the validator catches corruption."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Literal, cast

from sibyl_core.migrate.archive import (
    GRAPH_FILENAME,
    ArchiveFileManifest,
    ArchiveManifest,
    LoadedArchive,
    load_archive,
    validate_archive,
)

ScenarioName = Literal["checksum", "count-drift", "org-mismatch"]
DEFAULT_SCENARIOS: tuple[ScenarioName, ...] = ("checksum", "count-drift", "org-mismatch")


def _echo(message: str = "") -> None:
    sys.stdout.write(f"{message}\n")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _rebuild_manifest(archive: LoadedArchive, files: dict[str, bytes]) -> ArchiveManifest:
    return ArchiveManifest(
        version=archive.manifest.version,
        created_at=archive.manifest.created_at,
        organization_id=archive.manifest.organization_id,
        source_store=archive.manifest.source_store,
        files={
            name: ArchiveFileManifest(
                path=name,
                sha256=_sha256_bytes(payload),
                size_bytes=len(payload),
                kind=archive.manifest.files.get(name, ArchiveFileManifest(name, "", 0)).kind,
                metadata=dict(
                    archive.manifest.files.get(name, ArchiveFileManifest(name, "", 0)).metadata
                ),
            )
            for name, payload in files.items()
        },
        metadata=dict(archive.manifest.metadata),
    )


def mutate_archive(archive: LoadedArchive, scenario: ScenarioName) -> LoadedArchive:
    files = dict(archive.files)
    manifest = archive.manifest
    graph_bytes = files.get(GRAPH_FILENAME)
    if graph_bytes is None:
        msg = "archive does not contain graph.json"
        raise ValueError(msg)

    if scenario == "checksum":
        files[GRAPH_FILENAME] = b'{"tampered": true}\n'
        return LoadedArchive(source=archive.source, manifest=manifest, files=files)

    graph_payload = json.loads(graph_bytes.decode("utf-8"))
    if scenario == "count-drift":
        graph_payload["entity_count"] = int(graph_payload.get("entity_count", 0)) + 3
    elif scenario == "org-mismatch":
        graph_payload["organization_id"] = "other-org"
    else:
        msg = f"unsupported scenario: {scenario}"
        raise ValueError(msg)

    files[GRAPH_FILENAME] = json.dumps(graph_payload, indent=2, sort_keys=True).encode("utf-8")
    manifest = _rebuild_manifest(archive, files)
    return LoadedArchive(source=archive.source, manifest=manifest, files=files)


def probe_archive(archive: LoadedArchive, *, scenarios: list[ScenarioName]) -> list[str]:
    failures: list[str] = []
    for scenario in scenarios:
        mutated = mutate_archive(archive, scenario)
        errors = validate_archive(mutated)
        if not errors:
            failures.append(f"{scenario}: validator accepted the corrupted archive")
            continue
        _echo(f"{scenario}: detected {len(errors)} issue(s)")
        for error in errors:
            _echo(f"  - {error}")
    return failures


def _normalize_scenarios(raw_scenarios: object) -> list[ScenarioName]:
    if not raw_scenarios:
        return list(DEFAULT_SCENARIOS)
    return [cast(ScenarioName, scenario) for scenario in cast(list[str], raw_scenarios)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mutate a migration archive and assert validation catches corruption."
    )
    parser.add_argument("archive", type=Path, help="Archive .tar.gz or directory to probe.")
    parser.add_argument(
        "--scenario",
        action="append",
        choices=("checksum", "count-drift", "org-mismatch"),
        default=[],
        help="Specific corruption scenario to run. Defaults to all scenarios.",
    )
    args = parser.parse_args(argv)

    archive = load_archive(args.archive)
    base_errors = validate_archive(archive)
    if base_errors:
        _echo("Base archive is already invalid:")
        for error in base_errors:
            _echo(f"  - {error}")
        return 1

    scenarios = _normalize_scenarios(args.scenario)
    failures = probe_archive(archive, scenarios=scenarios)
    if failures:
        _echo()
        _echo("Chaos probe failed:")
        for failure in failures:
            _echo(f"  - {failure}")
        return 1

    _echo()
    _echo("Chaos probe passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
