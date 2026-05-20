"""Native AI substrate."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "AIError": ("sibyl_core.ai.errors", "AIError"),
    "ConfigField": ("sibyl_core.ai.llm", "ConfigField"),
    "EnvConfigSource": ("sibyl_core.ai.llm", "EnvConfigSource"),
    "Extractor": ("sibyl_core.ai.llm", "Extractor"),
    "ExtractedMemoryEntity": ("sibyl_core.models.memory_extraction", "ExtractedMemoryEntity"),
    "Generator": ("sibyl_core.ai.llm", "Generator"),
    "KeyValidationResult": ("sibyl_core.ai.validation", "KeyValidationResult"),
    "LLMConfig": ("sibyl_core.ai.llm", "LLMConfig"),
    "LLMConfigError": ("sibyl_core.ai.errors", "LLMConfigError"),
    "LLMConfigSource": ("sibyl_core.ai.llm", "LLMConfigSource"),
    "LLMError": ("sibyl_core.ai.errors", "LLMError"),
    "LLMProviderError": ("sibyl_core.ai.errors", "LLMProviderError"),
    "LLMRateLimitError": ("sibyl_core.ai.errors", "LLMRateLimitError"),
    "LLMSurface": ("sibyl_core.ai.llm", "LLMSurface"),
    "LLMTimeoutError": ("sibyl_core.ai.errors", "LLMTimeoutError"),
    "LLMValidationError": ("sibyl_core.ai.errors", "LLMValidationError"),
    "MemoryEntityExtractionResult": (
        "sibyl_core.models.memory_extraction",
        "MemoryEntityExtractionResult",
    ),
    "MemoryExtractionEntityType": (
        "sibyl_core.models.memory_extraction",
        "MemoryExtractionEntityType",
    ),
    "ModelCapability": ("sibyl_core.ai.registry", "ModelCapability"),
    "ModelEntry": ("sibyl_core.ai.registry", "ModelEntry"),
    "ModelKind": ("sibyl_core.ai.registry", "ModelKind"),
    "ModelRegistry": ("sibyl_core.ai.registry", "ModelRegistry"),
    "ModelValidationResult": ("sibyl_core.ai.validation", "ModelValidationResult"),
    "ResolvedLLMConfig": ("sibyl_core.ai.llm", "ResolvedLLMConfig"),
    "SurfaceTestResult": ("sibyl_core.ai.validation", "SurfaceTestResult"),
    "build_model": ("sibyl_core.ai.providers", "build_model"),
    "build_memory_entity_extraction_prompt": (
        "sibyl_core.ai.memory_extraction",
        "build_memory_entity_extraction_prompt",
    ),
    "check_model_availability": ("sibyl_core.ai.validation", "check_model_availability"),
    "check_provider_key": ("sibyl_core.ai.validation", "check_provider_key"),
    "classify_llm_exception": ("sibyl_core.ai.errors", "classify_llm_exception"),
    "embedding_entries": ("sibyl_core.ai.registry", "embedding_entries"),
    "get_config_source": ("sibyl_core.ai.llm", "get_config_source"),
    "invalidate_llm_config": ("sibyl_core.ai.llm", "invalidate_llm_config"),
    "llm_entries": ("sibyl_core.ai.registry", "llm_entries"),
    "memory_entity_extractor": ("sibyl_core.ai.memory_extraction", "memory_entity_extractor"),
    "model_registry": ("sibyl_core.ai.registry", "model_registry"),
    "recommended_for": ("sibyl_core.ai.registry", "recommended_for"),
    "resolve_llm_config": ("sibyl_core.ai.llm", "resolve_llm_config"),
    "resolve_provider_model_id": ("sibyl_core.ai.providers", "resolve_provider_model_id"),
    "set_config_source": ("sibyl_core.ai.llm", "set_config_source"),
    "test_surface_config": ("sibyl_core.ai.validation", "test_surface_config"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
