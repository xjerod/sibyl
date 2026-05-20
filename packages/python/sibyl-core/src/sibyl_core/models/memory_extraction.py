"""Structured contracts for LLM-powered memory extraction."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sibyl_core.models.entities import EntityType

MAX_MEMORY_EXTRACTED_ENTITIES = 12


class MemoryExtractionEntityType(StrEnum):
    TOPIC = "topic"
    CLAIM = "claim"
    PREFERENCE = "preference"
    PERSON = "person"
    PLACE = "place"
    EVENT = "event"
    ARTIFACT = "artifact"
    TOOL = "tool"
    LANGUAGE = "language"
    PATTERN = "pattern"
    PROCEDURE = "procedure"
    DOMAIN = "domain"

    def to_entity_type(self) -> EntityType:
        return EntityType(self.value)


class ExtractedMemoryEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=160)
    entity_type: MemoryExtractionEntityType = MemoryExtractionEntityType.TOPIC
    summary: str = Field(default="", max_length=600)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence: str = Field(default="", max_length=400)

    @field_validator("name", "summary", "evidence")
    @classmethod
    def _collapse_whitespace(cls, value: str) -> str:
        return " ".join(value.split())

    def to_entity_type(self) -> EntityType:
        return self.entity_type.to_entity_type()


class MemoryEntityExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entities: list[ExtractedMemoryEntity] = Field(
        default_factory=list,
        max_length=MAX_MEMORY_EXTRACTED_ENTITIES,
    )


__all__ = [
    "MAX_MEMORY_EXTRACTED_ENTITIES",
    "ExtractedMemoryEntity",
    "MemoryEntityExtractionResult",
    "MemoryExtractionEntityType",
]
