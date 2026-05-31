"""Shared memory-scope model."""

from __future__ import annotations

from enum import StrEnum


class MemoryScope(StrEnum):
    PRIVATE = "private"
    DELEGATED = "delegated"
    PROJECT = "project"
    TEAM = "team"
    ORGANIZATION = "organization"
    SHARED = "shared"
    PUBLIC = "public"
