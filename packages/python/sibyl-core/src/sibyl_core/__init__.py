"""
sibyl-core: Core library for Sibyl knowledge graph operations.

This package provides:
- Domain models (Entity, Task, Project, etc.)
- Graph client and entity management (FalkorDB/Graphiti)
- Hybrid retrieval (Graphiti node-hybrid search + graph traversal)
- Core tools (search, explore, add)
- Task workflow engine
- Auth primitives (JWT, password hashing)
"""

from sibyl_core._version import __version__, get_version
from sibyl_core.config import CoreConfig, core_config
from sibyl_core.errors import (
    EntityCreationError,
    EntityNotFoundError,
    GraphConnectionError,
    GraphError,
    IngestionError,
    InvalidTransitionError,
    SearchError,
    SibylError,
    ValidationError,
)

__all__ = [
    # Config
    "CoreConfig",
    # Errors
    "EntityCreationError",
    "EntityNotFoundError",
    "GraphConnectionError",
    "GraphError",
    "IngestionError",
    "InvalidTransitionError",
    "SearchError",
    "SibylError",
    "ValidationError",
    # Version
    "__version__",
    "core_config",
    "get_version",
]
