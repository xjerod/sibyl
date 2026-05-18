"""Sibyl-owned search filter models for the Surreal compatibility surface."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ComparisonOperator(StrEnum):
    equals = "="
    greater_than = ">"
    greater_than_equal = ">="
    less_than = "<"
    less_than_equal = "<="
    not_equals = "!="
    is_null = "IS NULL"
    is_not_null = "IS NOT NULL"


@dataclass(slots=True)
class DateFilter:
    date: datetime
    comparison_operator: ComparisonOperator


@dataclass(slots=True)
class SearchFilters:
    node_labels: list[str] | None = None
    edge_uuids: list[str] | None = None
    edge_types: list[str] | None = None
    project_ids: list[str] | tuple[str, ...] | None = None
    created_at: list[list[DateFilter]] = field(default_factory=list)
    expired_at: list[list[DateFilter]] = field(default_factory=list)
    valid_at: list[list[DateFilter]] = field(default_factory=list)
    invalid_at: list[list[DateFilter]] = field(default_factory=list)
