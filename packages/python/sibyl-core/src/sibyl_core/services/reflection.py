"""Structured reflection extraction contracts and deterministic providers."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from sibyl_core.models.reflection import (
    ClaimRecord,
    ReflectionCandidate,
    ReflectionFinding,
    ReflectionFindingKind,
    ReflectionRelationshipRecord,
)

SUPPORTED_REFLECTION_KINDS = frozenset(
    {
        "artifact",
        "claim",
        "decision",
        "idea",
        "plan",
        "procedure",
        "session",
        "task",
    }
)

_KIND_RULES: tuple[tuple[str, tuple[str, ...], str, float], ...] = (
    (
        "decision",
        (
            "decided",
            "decision",
            "we will",
            "we'll",
            "chosen",
            "choose",
            "keep",
            "use ",
        ),
        "captures a choice or direction future agents should preserve",
        0.86,
    ),
    (
        "task",
        (
            "blocked",
            "task",
            "ticket",
            "issue",
            "follow up",
            "follow-up",
        ),
        "captures task state or follow-up work",
        0.82,
    ),
    (
        "plan",
        (
            "plan",
            "next",
            "todo",
            "build",
            "implement",
            "migrate",
            "phase",
            "workstream",
        ),
        "captures sequencing, scope, or intended work",
        0.80,
    ),
    (
        "idea",
        (
            "idea",
            "maybe",
            "could",
            "what if",
            "explore",
            "brainstorm",
            "possible",
        ),
        "captures a possibility before it becomes a decision",
        0.72,
    ),
    (
        "claim",
        (
            "confirmed",
            "validated",
            "observed",
            "because",
            "means",
            "fact",
            "latest",
        ),
        "captures an assertion that may need provenance or contradiction handling",
        0.78,
    ),
    (
        "procedure",
        (
            "workflow",
            "steps",
            "run ",
            "command",
            "use `",
            "verify",
            "test",
        ),
        "captures repeatable process knowledge",
        0.76,
    ),
)

_ARTIFACT_PATTERN = re.compile(
    r"(?i)(https?://\S+|(?:[\w.-]+/)+[\w.-]+\.\w+|[\w.-]+\.(?:md|py|ts|tsx|json|ya?ml|toml|rs))"
)
_SPLIT_PATTERN = re.compile(r"(?:\n+|(?<=[.!?])\s+)")
_SENSITIVE_MARKERS = (
    "api key",
    "credential",
    "password",
    "private key",
    "secret",
    "token",
)


@dataclass(frozen=True)
class ReflectionExtractionRequest:
    content: str
    source_title: str
    intent: str
    domain: str | None = None
    project: str | None = None
    source_ids: tuple[str, ...] = ()
    limit: int = 12


class ReflectionExtractor(Protocol):
    async def extract(self, request: ReflectionExtractionRequest) -> list[ReflectionCandidate]:
        """Return schema-validated reflection candidates for a raw source."""


class HeuristicReflectionExtractor:
    async def extract(self, request: ReflectionExtractionRequest) -> list[ReflectionCandidate]:
        candidates = [
            candidate
            for index, segment in enumerate(_segments(request.content))
            if (
                candidate := _candidate_for_segment(
                    segment,
                    source_title=request.source_title,
                    intent=request.intent,
                    domain=request.domain,
                    project=request.project,
                    source_ids=list(request.source_ids),
                    index=index,
                )
            )
            is not None
        ]
        if not candidates:
            candidates = [
                _fallback_session_candidate(
                    source_title=request.source_title,
                    content=request.content,
                    intent=request.intent,
                    domain=request.domain,
                    project=request.project,
                    source_ids=list(request.source_ids),
                )
            ]
        candidates = _dedupe(candidates, request.limit)
        validate_reflection_candidates(candidates, require_source_ids=bool(request.source_ids))
        return candidates


class DeterministicFakeReflectionExtractor:
    def __init__(self, candidates: Sequence[ReflectionCandidate]) -> None:
        self._candidates = list(candidates)
        self.requests: list[ReflectionExtractionRequest] = []

    async def extract(self, request: ReflectionExtractionRequest) -> list[ReflectionCandidate]:
        self.requests.append(request)
        return list(self._candidates[: request.limit])


def ephemeral_reflection_source_id(content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    return f"reflection:input:{digest}"


def ground_reflection_candidate(
    candidate: ReflectionCandidate,
    *,
    raw_source_ids: Sequence[str],
    suggested_memory_scope: str,
    suggested_scope_key: str | None,
    extraction_prompt_metadata: dict[str, object],
    source_id: str | None,
) -> ReflectionCandidate:
    source_ids = _candidate_source_ids(candidate, raw_source_ids, source_id)
    claim_records = _ground_claim_records(candidate, source_ids)
    findings = _ground_reflection_findings(candidate, source_ids)
    relationships = _ground_relationship_records(candidate, source_ids)
    sensitivity_flags = _str_values(candidate.sensitivity_flags)
    metadata = {
        **candidate.metadata,
        "raw_source_ids": source_ids,
        "source_ids": source_ids,
        "suggested_memory_scope": suggested_memory_scope,
        "suggested_scope_key": suggested_scope_key,
        "review_state": candidate.review_state,
        "extraction_prompt_metadata": dict(extraction_prompt_metadata),
    }
    if source_id:
        metadata["reflection_source_id"] = source_id
    if claim_records:
        metadata["claim_records"] = [claim.to_dict() for claim in claim_records]
    if findings:
        metadata["reflection_findings"] = [finding.to_dict() for finding in findings]
    if relationships:
        metadata["relationship_records"] = [
            relationship.to_dict() for relationship in relationships
        ]
    if sensitivity_flags:
        metadata["sensitivity_flags"] = sensitivity_flags
        metadata["contains_sensitive"] = True
    return replace(
        candidate,
        metadata=metadata,
        raw_source_ids=source_ids,
        suggested_memory_scope=suggested_memory_scope,
        suggested_scope_key=suggested_scope_key,
        claim_records=claim_records,
        reflection_findings=findings,
        relationship_records=relationships,
        sensitivity_flags=sensitivity_flags,
    )


def validate_reflection_candidates(
    candidates: Sequence[ReflectionCandidate],
    *,
    require_source_ids: bool,
) -> None:
    for candidate in candidates:
        if candidate.kind not in SUPPORTED_REFLECTION_KINDS:
            msg = f"unsupported reflection candidate kind: {candidate.kind}"
            raise ValueError(msg)
        if candidate.confidence < 0.0 or candidate.confidence > 1.0:
            msg = f"reflection confidence out of range for {candidate.title}"
            raise ValueError(msg)
        source_ids = _candidate_source_ids(candidate, (), None)
        if require_source_ids and not source_ids:
            msg = f"reflection candidate lacks source_ids: {candidate.title}"
            raise ValueError(msg)
        for claim in candidate.claim_records:
            if require_source_ids and not claim.source_ids:
                msg = f"claim record lacks source_ids: {claim.title or candidate.title}"
                raise ValueError(msg)
        for finding in candidate.reflection_findings:
            if require_source_ids and not finding.source_ids:
                msg = f"reflection finding lacks source_ids: {finding.id}"
                raise ValueError(msg)


def _candidate_for_segment(
    segment: str,
    *,
    source_title: str,
    intent: str,
    domain: str | None,
    project: str | None,
    source_ids: list[str],
    index: int,
) -> ReflectionCandidate | None:
    lower = segment.lower()
    kind = ""
    reason = ""
    confidence = 0.0

    if _ARTIFACT_PATTERN.search(segment):
        kind = "artifact"
        reason = "mentions a concrete file, URL, document, or generated output"
        confidence = 0.82
    elif lower.startswith(("maybe ", "what if ", "could ")):
        kind = "idea"
        reason = "captures a possibility before it becomes a decision"
        confidence = 0.82
    elif lower.startswith(("next ", "todo ", "phase ", "workstream ")):
        kind = "plan"
        reason = "captures sequencing, scope, or intended work"
        confidence = 0.84
    else:
        for candidate_kind, markers, candidate_reason, score in _KIND_RULES:
            if any(marker in lower for marker in markers):
                kind = candidate_kind
                reason = candidate_reason
                confidence = score
                break

    if not kind:
        return None

    return _candidate(
        kind=kind,
        segment=segment,
        reason=reason,
        confidence=confidence,
        source_title=source_title,
        intent=intent,
        domain=domain,
        project=project,
        source_ids=source_ids,
        index=index,
    )


def _fallback_session_candidate(
    *,
    source_title: str,
    content: str,
    intent: str,
    domain: str | None,
    project: str | None,
    source_ids: list[str],
) -> ReflectionCandidate:
    return _candidate(
        kind="session",
        segment=_compact(content, max_chars=1200),
        reason="preserves the raw session checkpoint when no finer candidate is obvious",
        confidence=0.60,
        source_title=source_title,
        intent=intent,
        domain=domain,
        project=project,
        source_ids=source_ids,
        index=0,
    )


def _candidate(
    *,
    kind: str,
    segment: str,
    reason: str,
    confidence: float,
    source_title: str,
    intent: str,
    domain: str | None,
    project: str | None,
    source_ids: list[str],
    index: int,
) -> ReflectionCandidate:
    sensitivity_flags = _sensitivity_flags(segment)
    metadata: dict[str, object] = {
        "reflection_source_title": source_title,
        "reflection_intent": intent,
        "reflection_index": index,
        "extractor_kind": "heuristic",
    }
    if project:
        metadata["project_id"] = project
    if sensitivity_flags:
        metadata["sensitivity_flags"] = sensitivity_flags
        metadata["contains_sensitive"] = True

    title = _derive_title(segment, prefix=kind.capitalize())
    claim_records = _claim_records_for_kind(
        kind=kind,
        title=title,
        content=segment,
        confidence=confidence,
        source_ids=source_ids,
        domain=domain,
        project=project,
    )
    findings = _findings_for_claims(
        claim_records,
        reason=reason,
        source_ids=source_ids,
    )
    return ReflectionCandidate(
        kind=kind,
        title=title,
        content=segment,
        reason=reason,
        confidence=confidence,
        tags=_tags_for(kind, domain, sensitivity_flags),
        metadata=metadata,
        raw_source_ids=list(source_ids),
        claim_records=claim_records,
        reflection_findings=findings,
        relationship_records=_relationship_records_for_project(
            candidate_index=index,
            project=project,
            source_ids=source_ids,
        ),
        sensitivity_flags=sensitivity_flags,
    )


def _claim_records_for_kind(
    *,
    kind: str,
    title: str,
    content: str,
    confidence: float,
    source_ids: list[str],
    domain: str | None,
    project: str | None,
) -> list[ClaimRecord]:
    if kind != "claim":
        return []
    return [
        ClaimRecord(
            title=title,
            content=content,
            confidence=confidence,
            source_ids=list(source_ids),
            raw_source_ids=list(source_ids),
            memory_scope="project" if project else "private",
            scope_key=project,
            metadata={"domain": domain} if domain else {},
        )
    ]


def _findings_for_claims(
    claims: Sequence[ClaimRecord],
    *,
    reason: str,
    source_ids: list[str],
) -> list[ReflectionFinding]:
    return [
        ReflectionFinding(
            kind=ReflectionFindingKind.CLAIM,
            target_source_id=claim.source_ids[0] if claim.source_ids else "",
            reason=reason,
            confidence=claim.confidence,
            source_ids=list(source_ids),
            related_source_ids=[claim.id],
            metadata={"claim_id": claim.id},
        )
        for claim in claims
    ]


def _relationship_records_for_project(
    *,
    candidate_index: int,
    project: str | None,
    source_ids: list[str],
) -> list[ReflectionRelationshipRecord]:
    if not project:
        return []
    return [
        ReflectionRelationshipRecord(
            source_id=f"candidate:{candidate_index}",
            target_id=project,
            relationship_type="BELONGS_TO",
            reason="candidate was reflected in a project-scoped session",
            confidence=1.0,
            source_ids=list(source_ids),
        )
    ]


def _ground_claim_records(
    candidate: ReflectionCandidate,
    source_ids: list[str],
) -> list[ClaimRecord]:
    claims = candidate.claim_records
    if candidate.kind == "claim" and not claims:
        claims = _claim_records_for_kind(
            kind=candidate.kind,
            title=candidate.title,
            content=candidate.content,
            confidence=candidate.confidence,
            source_ids=source_ids,
            domain=_metadata_str(candidate.metadata, "domain"),
            project=_metadata_str(candidate.metadata, "project_id"),
        )
    return [
        replace(
            claim,
            source_ids=_merge_str_values(source_ids, claim.source_ids),
            raw_source_ids=_merge_str_values(source_ids, claim.raw_source_ids),
        )
        for claim in claims
    ]


def _ground_reflection_findings(
    candidate: ReflectionCandidate,
    source_ids: list[str],
) -> list[ReflectionFinding]:
    findings = candidate.reflection_findings
    if candidate.kind == "claim" and candidate.claim_records and not findings:
        findings = _findings_for_claims(
            candidate.claim_records,
            reason=candidate.reason,
            source_ids=source_ids,
        )
    target_source_id = source_ids[0] if source_ids else ""
    return [
        replace(
            finding,
            target_source_id=finding.target_source_id or target_source_id,
            source_ids=_merge_str_values(source_ids, finding.source_ids),
        )
        for finding in findings
    ]


def _ground_relationship_records(
    candidate: ReflectionCandidate,
    source_ids: list[str],
) -> list[ReflectionRelationshipRecord]:
    return [
        replace(
            relationship,
            source_ids=_merge_str_values(source_ids, relationship.source_ids),
        )
        for relationship in candidate.relationship_records
    ]


def _candidate_source_ids(
    candidate: ReflectionCandidate,
    raw_source_ids: Sequence[str],
    source_id: str | None,
) -> list[str]:
    metadata = candidate.metadata
    return _merge_str_values(
        [source_id] if source_id else [],
        raw_source_ids,
        candidate.raw_source_ids,
        _metadata_str_list(metadata, "raw_source_ids"),
        _metadata_str_list(metadata, "source_ids"),
    )


def _dedupe(candidates: list[ReflectionCandidate], limit: int) -> list[ReflectionCandidate]:
    seen: set[tuple[str, str]] = set()
    deduped: list[ReflectionCandidate] = []
    for candidate in sorted(candidates, key=lambda item: item.confidence, reverse=True):
        key = (candidate.kind, candidate.content.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
        if len(deduped) >= limit:
            break
    return deduped


def _segments(content: str) -> list[str]:
    raw_segments = [_compact(part, max_chars=900) for part in _SPLIT_PATTERN.split(content)]
    return [part for part in raw_segments if len(part) >= 12]


def _compact(value: str, max_chars: int = 500) -> str:
    compact = " ".join(value.strip().split())
    if len(compact) <= max_chars:
        return compact
    cutoff = compact.rfind(" ", 0, max_chars + 1)
    if cutoff < max_chars // 2:
        cutoff = max_chars
    return compact[:cutoff].rstrip() + "..."


def _derive_title(text: str, *, prefix: str | None = None, max_chars: int = 86) -> str:
    title = _compact(re.sub(r"^[\-*#>\d.)\s]+", "", text), max_chars=max_chars)
    if prefix and not title.lower().startswith(prefix.lower()):
        return f"{prefix}: {title}"[:max_chars].rstrip()
    return title or "Reflected memory"


def _tags_for(kind: str, domain: str | None, sensitivity_flags: Sequence[str]) -> list[str]:
    tags = ["reflection", kind]
    if domain:
        tags.append(domain.strip().lower().replace(" ", "-"))
    if sensitivity_flags:
        tags.append("sensitive")
    return tags


def _sensitivity_flags(text: str) -> list[str]:
    lower = text.lower()
    return [marker.replace(" ", "_") for marker in _SENSITIVE_MARKERS if marker in lower]


def _metadata_str(metadata: dict[str, object], key: str) -> str | None:
    value = metadata.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _metadata_str_list(metadata: dict[str, object], key: str) -> list[str]:
    return _str_values(metadata.get(key))


def _str_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if not isinstance(value, list | tuple | set):
        return []
    return [str(item) for item in value if str(item).strip()]


def _merge_str_values(*values: object) -> list[str]:
    merged: list[str] = []
    for value in values:
        for item in _str_values(value):
            if item not in merged:
                merged.append(item)
    return merged


__all__ = [
    "SUPPORTED_REFLECTION_KINDS",
    "DeterministicFakeReflectionExtractor",
    "HeuristicReflectionExtractor",
    "ReflectionExtractionRequest",
    "ReflectionExtractor",
    "ephemeral_reflection_source_id",
    "ground_reflection_candidate",
    "validate_reflection_candidates",
]
