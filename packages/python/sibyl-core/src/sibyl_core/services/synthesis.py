"""Deterministic source-aware synthesis planning."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import asdict
from typing import Any

from sibyl_core.models.synthesis import (
    SynthesisGap,
    SynthesisOutline,
    SynthesisOutlineSection,
    SynthesisOutputType,
    SynthesisRequest,
    SynthesisRun,
    SynthesisRunStatus,
    SynthesisSectionRequest,
    SynthesisSourcePack,
    SynthesisSourceReference,
    SynthesisVerification,
    SynthesisVerificationStatus,
)
from sibyl_core.tools.responses import ExploreResponse, SearchResponse, SearchResult

SynthesisSearchFn = Callable[..., Awaitable[SearchResponse]]
SynthesisRelatedFn = Callable[..., Awaitable[list[SynthesisSourceReference]]]

SECTION_TEMPLATES: dict[SynthesisOutputType, list[tuple[str, str]]] = {
    SynthesisOutputType.DOCUMENTATION: [
        ("Overview", "Summarize the supported system shape and purpose."),
        ("Key Decisions", "Capture source-backed architectural choices and rationale."),
        ("Implementation Notes", "List relevant implementation details and contracts."),
        ("Risks And Gaps", "Call out unsupported claims, unknowns, and missing sources."),
    ],
    SynthesisOutputType.REPORT: [
        ("Executive Summary", "Summarize the source-backed findings."),
        ("Evidence", "Organize the strongest supporting sources."),
        ("Risks And Gaps", "Identify missing, weak, or stale source coverage."),
    ],
    SynthesisOutputType.BRIEFING: [
        ("Situation", "Describe the current state from available sources."),
        ("Signals", "List important source-backed signals and decisions."),
        ("Next Actions", "Identify supported follow-up work."),
    ],
    SynthesisOutputType.ROADMAP: [
        ("Current State", "Describe what is already supported by the source graph."),
        ("Completed Work", "Summarize completed source-backed decisions and tasks."),
        ("Next Milestones", "Plan the next milestones from tasks, decisions, and artifacts."),
        ("Risks And Open Questions", "List unsupported claims and source gaps."),
    ],
    SynthesisOutputType.RELEASE_NOTES: [
        ("Highlights", "Summarize source-backed user-facing changes."),
        ("Behavior Changes", "List changed behavior with supporting sources."),
        ("Verification", "Collect test, audit, and gate evidence."),
        ("Known Gaps", "Disclose unsupported or incomplete release claims."),
    ],
    SynthesisOutputType.AUDIT_PACKET: [
        ("Scope", "Define the audited surface from available sources."),
        ("Findings", "List source-backed findings and evidence."),
        ("Evidence", "Collect source IDs, tasks, decisions, and artifacts."),
        ("Gaps And Risks", "Identify missing evidence and unsupported sections."),
    ],
    SynthesisOutputType.CUSTOM: [
        ("Overview", "Summarize the requested synthesis from available sources."),
        ("Evidence", "Organize source-backed details."),
        ("Gaps", "List unsupported claims and missing sources."),
    ],
}

SECTION_SOURCE_HINTS: dict[str, tuple[str, ...]] = {
    "completed": ("task", "procedure", "artifact"),
    "current": ("task", "decision", "artifact", "raw_memory"),
    "decision": ("decision",),
    "evidence": ("artifact", "document", "source", "claim", "procedure"),
    "gap": ("task", "claim", "decision", "artifact"),
    "highlight": ("artifact", "task", "decision"),
    "implementation": ("procedure", "task", "artifact", "document"),
    "milestone": ("task", "plan", "epic"),
    "risk": ("claim", "task", "decision", "artifact"),
    "verification": ("claim", "rule", "procedure", "artifact"),
}
TOKEN_STOPWORDS = {
    "and",
    "are",
    "from",
    "into",
    "needs",
    "plan",
    "the",
    "this",
    "with",
}


async def default_search(**kwargs: Any) -> SearchResponse:
    from sibyl_core.tools.search import search

    return await search(**kwargs)


async def default_related_sources(
    *,
    entity_id: str,
    organization_id: str,
    accessible_projects: set[str] | None = None,
    limit: int = 5,
) -> list[SynthesisSourceReference]:
    from sibyl_core.tools.explore import explore

    response = await explore(
        mode="related",
        entity_id=entity_id,
        organization_id=organization_id,
        accessible_projects=accessible_projects,
        limit=limit,
    )
    return _sources_from_explore(response)


def _sources_from_explore(response: ExploreResponse) -> list[SynthesisSourceReference]:
    sources: list[SynthesisSourceReference] = []
    for entity in response.entities:
        metadata = dict(getattr(entity, "metadata", {}) or {})
        relation = getattr(entity, "relationship", None)
        if direction := getattr(entity, "direction", None):
            metadata["direction"] = direction
        if distance := getattr(entity, "distance", None):
            metadata["distance"] = distance
        sources.append(
            SynthesisSourceReference(
                id=str(entity.id),
                type=str(entity.type),
                name=str(entity.name),
                content_preview=str(getattr(entity, "description", "") or ""),
                score=0.5,
                origin="neighborhood",
                relation=str(relation) if relation else None,
                metadata=metadata,
            )
        )
    return sources


def _compact_text(value: str, max_chars: int = 320) -> str:
    compact = " ".join(value.strip().split())
    if len(compact) <= max_chars:
        return compact
    cutoff = compact.rfind(" ", 0, max_chars + 1)
    if cutoff < max_chars // 2:
        cutoff = max_chars
    return compact[:cutoff].rstrip() + "..."


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_-]+", value.lower())
        if len(token) > 2 and token not in TOKEN_STOPWORDS
    }


def _slug(value: str, *, fallback: str) -> str:
    slug = "-".join(re.findall(r"[a-z0-9]+", value.lower()))
    return slug or fallback


def _query_for(request: SynthesisRequest) -> str:
    parts = [request.seed_query or request.goal, request.domain or ""]
    return " ".join(" ".join(part.strip().split()) for part in parts if part).strip()


def _source_type_from_id(source_id: str, fallback: str) -> str:
    prefix = source_id.split(":", 1)[0].split("_", 1)[0].lower()
    if prefix and prefix != source_id.lower():
        return prefix
    return fallback


def _explicit_source(source_id: str, fallback_type: str, origin: str) -> SynthesisSourceReference:
    source_type = _source_type_from_id(source_id, fallback_type)
    return SynthesisSourceReference(
        id=source_id,
        type=source_type,
        name=source_id,
        score=1.0,
        origin=origin,
        metadata={"explicit": True},
    )


def _source_from_result(result: SearchResult, origin: str) -> SynthesisSourceReference:
    metadata = dict(result.metadata or {})
    source = result.source or metadata.get("source_id") or result.id
    metadata.setdefault("source_id", source)
    return SynthesisSourceReference(
        id=result.id,
        type=result.type,
        name=result.name,
        content_preview=_compact_text(result.content),
        score=float(result.score),
        source=str(source) if source is not None else None,
        origin=origin,
        metadata=metadata,
    )


def _dedupe_sources(
    sources: Iterable[SynthesisSourceReference],
) -> list[SynthesisSourceReference]:
    seen: set[str] = set()
    deduped: list[SynthesisSourceReference] = []
    for source in sources:
        if source.id in seen:
            continue
        seen.add(source.id)
        deduped.append(source)
    return deduped


async def _search_sources(
    *,
    query: str,
    organization_id: str,
    project: str | None,
    domain: str | None,
    accessible_projects: set[str] | None,
    search_fn: SynthesisSearchFn,
) -> list[SynthesisSourceReference]:
    specs: list[tuple[list[str], str, int]] = [
        (["decision"], "decision", 6),
        (["task", "epic", "plan"], "task", 8),
        (["artifact", "document", "source", "config_file"], "artifact", 8),
    ]
    sources: list[SynthesisSourceReference] = []
    for types, origin, limit in specs:
        response = await search_fn(
            query=query,
            types=types,
            category=domain,
            project=project,
            accessible_projects=accessible_projects,
            organization_id=organization_id,
            limit=limit,
            include_content=True,
        )
        sources.extend(_source_from_result(result, origin) for result in response.results)
    return sources


async def _neighborhood_sources(
    *,
    entity_ids: list[str],
    organization_id: str,
    accessible_projects: set[str] | None,
    related_fn: SynthesisRelatedFn,
) -> list[SynthesisSourceReference]:
    sources: list[SynthesisSourceReference] = []
    for entity_id in entity_ids:
        related = await related_fn(
            entity_id=entity_id,
            organization_id=organization_id,
            accessible_projects=accessible_projects,
            limit=5,
        )
        sources.extend(related)
    return sources


def _section_requests(request: SynthesisRequest) -> list[SynthesisSectionRequest]:
    if request.required_sections:
        return request.required_sections[: max(1, min(request.max_sections, 12))]
    template = SECTION_TEMPLATES[request.output_type]
    max_sections = max(1, min(request.max_sections, len(template), 12))
    return [
        SynthesisSectionRequest(title=title, prompt=prompt)
        for title, prompt in template[:max_sections]
    ]


def _source_search_text(source: SynthesisSourceReference) -> str:
    metadata_text = " ".join(str(value) for value in source.metadata.values() if value is not None)
    return " ".join(
        [
            source.id,
            source.type,
            source.name,
            source.content_preview,
            source.source or "",
            source.origin,
            source.relation or "",
            metadata_text,
        ]
    )


def _section_source_score(
    *,
    section: SynthesisSectionRequest,
    source: SynthesisSourceReference,
    base_query: str,
) -> float:
    section_text = " ".join([section.title, section.prompt or "", base_query])
    section_tokens = _tokens(section_text)
    source_tokens = _tokens(_source_search_text(source))
    overlap = len(section_tokens & source_tokens)
    hint_bonus = 0.0
    normalized_title = section.title.lower()
    for title_token, source_types in SECTION_SOURCE_HINTS.items():
        if title_token in normalized_title and source.type in source_types:
            hint_bonus += 4.0
    explicit_bonus = 4.0 if source.id in section.required_source_ids else 0.0
    if source.metadata.get("explicit"):
        explicit_bonus += 1.5
    return overlap + hint_bonus + explicit_bonus + source.score


def _select_section_sources(
    *,
    section: SynthesisSectionRequest,
    sources: list[SynthesisSourceReference],
    base_query: str,
    fallback_when_generated: bool,
) -> list[SynthesisSourceReference]:
    by_id = {source.id: source for source in sources}
    required_sources = [
        by_id[source_id] for source_id in section.required_source_ids if source_id in by_id
    ]
    scored = [
        (
            _section_source_score(section=section, source=source, base_query=base_query),
            index,
            source,
        )
        for index, source in enumerate(sources)
        if source.id not in section.required_source_ids
    ]
    matched = [
        source
        for score, _, source in sorted(scored, key=lambda item: (-item[0], item[1], item[2].id))
        if score > source.score
    ][:4]
    if not matched and fallback_when_generated and sources:
        matched = sources[: min(3, len(sources))]
    return _dedupe_sources([*required_sources, *matched])


def _gap_for_section(
    *,
    section_id: str,
    section: SynthesisSectionRequest,
    base_query: str,
) -> SynthesisGap:
    missing_source_ids = list(section.required_source_ids)
    reason = (
        "required_source_ids_not_found"
        if missing_source_ids
        else "no_source_supports_requested_section"
    )
    return SynthesisGap(
        section_id=section_id,
        title=section.title,
        reason=reason,
        query=" ".join([section.title, section.prompt or "", base_query]).strip(),
        missing_source_ids=missing_source_ids,
    )


def _run_id(request: SynthesisRequest) -> str:
    payload = repr(asdict(request)).encode()
    digest = hashlib.sha256(payload).hexdigest()[:16]
    return f"synthesis:{digest}"


async def plan_synthesis(
    request: SynthesisRequest,
    *,
    organization_id: str,
    accessible_projects: set[str] | None = None,
    search_fn: SynthesisSearchFn = default_search,
    related_fn: SynthesisRelatedFn = default_related_sources,
) -> SynthesisRun:
    goal = " ".join(request.goal.strip().split())
    if not goal:
        raise ValueError("goal is required")
    if not organization_id:
        raise ValueError("organization_id is required")

    request = SynthesisRequest(
        goal=goal,
        output_type=request.output_type,
        audience=request.audience,
        depth=request.depth,
        seed_query=request.seed_query,
        project=request.project,
        domain=request.domain,
        entity_ids=list(dict.fromkeys(request.entity_ids)),
        decision_ids=list(dict.fromkeys(request.decision_ids)),
        task_ids=list(dict.fromkeys(request.task_ids)),
        artifact_ids=list(dict.fromkeys(request.artifact_ids)),
        required_sections=request.required_sections,
        constraints=list(request.constraints),
        max_sections=request.max_sections,
        include_neighborhoods=request.include_neighborhoods,
    )
    base_query = _query_for(request)
    explicit_sources = [
        *[_explicit_source(source_id, "entity", "entity") for source_id in request.entity_ids],
        *[_explicit_source(source_id, "decision", "decision") for source_id in request.decision_ids],
        *[_explicit_source(source_id, "task", "task") for source_id in request.task_ids],
        *[_explicit_source(source_id, "artifact", "artifact") for source_id in request.artifact_ids],
    ]
    searched_sources = await _search_sources(
        query=base_query,
        organization_id=organization_id,
        project=request.project,
        domain=request.domain,
        accessible_projects=accessible_projects,
        search_fn=search_fn,
    )
    neighborhood_sources = (
        await _neighborhood_sources(
            entity_ids=[source.id for source in explicit_sources],
            organization_id=organization_id,
            accessible_projects=accessible_projects,
            related_fn=related_fn,
        )
        if request.include_neighborhoods and explicit_sources
        else []
    )
    sources = _dedupe_sources([*explicit_sources, *searched_sources, *neighborhood_sources])

    section_inputs = _section_requests(request)
    generated_outline = not request.required_sections
    outline_sections: list[SynthesisOutlineSection] = []
    source_packs: list[SynthesisSourcePack] = []
    gaps: list[SynthesisGap] = []
    for index, section in enumerate(section_inputs, start=1):
        section_id = f"section:{index:02d}-{_slug(section.title, fallback='section')}"
        selected_sources = _select_section_sources(
            section=section,
            sources=sources,
            base_query=base_query,
            fallback_when_generated=generated_outline,
        )
        section_gaps: list[SynthesisGap] = []
        if not selected_sources:
            section_gaps.append(
                _gap_for_section(section_id=section_id, section=section, base_query=base_query)
            )
        missing_required = []
        if selected_sources:
            missing_required = [
                source_id
                for source_id in section.required_source_ids
                if source_id not in {source.id for source in selected_sources}
            ]
        if missing_required:
            section_gaps.append(
                SynthesisGap(
                    section_id=section_id,
                    title=section.title,
                    reason="required_source_ids_not_found",
                    query=" ".join([section.title, section.prompt or "", base_query]).strip(),
                    missing_source_ids=missing_required,
                )
            )
        gaps.extend(section_gaps)
        source_ids = [source.id for source in selected_sources]
        source_query = " ".join([section.title, section.prompt or "", base_query]).strip()
        outline_sections.append(
            SynthesisOutlineSection(
                section_id=section_id,
                title=section.title,
                prompt=section.prompt or f"Draft {section.title} from cited sources.",
                source_query=source_query,
                source_ids=source_ids,
                gaps=section_gaps,
            )
        )
        source_packs.append(
            SynthesisSourcePack(
                section_id=section_id,
                title=section.title,
                query=source_query,
                source_ids=source_ids,
                sources=selected_sources,
            )
        )

    outline = SynthesisOutline(
        title=goal,
        output_type=request.output_type,
        audience=request.audience,
        sections=outline_sections,
    )
    verification = SynthesisVerification(
        status=(
            SynthesisVerificationStatus.GAPS
            if gaps
            else SynthesisVerificationStatus.PENDING
        ),
        source_count=len({source.id for source in sources}),
        gap_count=len(gaps),
        gaps=gaps,
    )
    return SynthesisRun(
        run_id=_run_id(request),
        status=SynthesisRunStatus.PLANNED,
        request=request,
        outline=outline,
        source_packs=source_packs,
        verification=verification,
    )


def synthesis_run_to_dict(run: SynthesisRun) -> dict[str, Any]:
    return asdict(run)


__all__ = [
    "SynthesisRelatedFn",
    "SynthesisSearchFn",
    "default_related_sources",
    "default_search",
    "plan_synthesis",
    "synthesis_run_to_dict",
]
