"""Compatibility exports for legacy graph community imports."""

from typing import Any

from sibyl_core.services import graph_communities as _graph_communities
from sibyl_core.services.graph_communities import *  # noqa: F403


def __getattr__(name: str) -> Any:
    return getattr(_graph_communities, name)
