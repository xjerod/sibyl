"""Project reference resolution for CLI commands."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from uuid import UUID

PROJECT_RELINK_HINT = "Run: sibyl project relink"


def is_project_id(value: str) -> bool:
    if value.startswith("project_"):
        return True
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def project_slug(value: object) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _project_slugs(value: object) -> set[str]:
    text = str(value or "").strip()
    if not text:
        return set()

    slugs = {project_slug(text)}
    basename = Path(text.rstrip("/")).name
    if basename.endswith(".git"):
        basename = basename.removesuffix(".git")
    slugs.add(project_slug(basename))
    return {slug for slug in slugs if slug}


def project_matches_path_hint(project: dict[str, Any], path: str) -> bool:
    target = Path(path).expanduser().resolve()
    target_slug = project_slug(target.name)
    if not target_slug:
        return False

    metadata = project.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    candidate_values = [
        project.get("id"),
        project.get("name"),
        metadata.get("slug"),
        metadata.get("repo"),
        metadata.get("repository_url"),
        metadata.get("repository_path"),
        metadata.get("path"),
        metadata.get("local_path"),
    ]
    return any(target_slug in _project_slugs(value) for value in candidate_values if value)


async def list_accessible_projects(client: Any, *, limit: int = 100) -> list[dict[str, Any]]:
    response = await client.explore(mode="list", types=["project"], limit=limit)
    entities = response.get("entities", [])
    return [entity for entity in entities if isinstance(entity, dict)]


def matching_project_refs(projects: list[dict[str, Any]], reference: str) -> list[dict[str, Any]]:
    if is_project_id(reference):
        return [project for project in projects if project.get("id") == reference]

    requested = project_slug(reference)
    matches: list[dict[str, Any]] = []
    for project in projects:
        metadata = project.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        candidates = [
            project.get("id"),
            project.get("name"),
            metadata.get("slug"),
        ]
        if any(project_slug(value) == requested for value in candidates if value):
            matches.append(project)
    return matches


async def resolve_project_reference(client: Any, reference: str) -> str:
    if is_project_id(reference):
        return reference

    projects = await list_accessible_projects(client)
    matches = matching_project_refs(projects, reference)
    if len(matches) == 1:
        return str(matches[0]["id"])
    if not matches:
        msg = f"Project not found: {reference}. {PROJECT_RELINK_HINT}."
        raise ValueError(msg)

    candidates = ", ".join(str(project.get("id", "")) for project in matches[:5])
    msg = f"Ambiguous project reference: {reference}. Matches: {candidates}."
    raise ValueError(msg)
