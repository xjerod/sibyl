"""Sibyl structlog formatters.

Produces pipe-separated output: service | timestamp | level | message key=value...
"""

from __future__ import annotations

import sys
import traceback
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

from sibyl_core.logging.colors import (
    ANSI_CORAL,
    ANSI_DIM,
    ANSI_ELECTRIC_PURPLE,
    ANSI_ELECTRIC_YELLOW,
    ANSI_ERROR_RED,
    ANSI_NEON_CYAN,
    ANSI_RESET,
    ANSI_SUCCESS_GREEN,
    LEVEL_COLORS,
)

# Service name → color mapping
SERVICE_COLORS: dict[str, str] = {
    "api": ANSI_ELECTRIC_PURPLE,
    "worker": ANSI_ELECTRIC_YELLOW,
    "web": ANSI_NEON_CYAN,
    "cli": ANSI_CORAL,
}

if TYPE_CHECKING:
    from structlog.typing import EventDict, WrappedLogger


class _SupportsIsatty(Protocol):
    def isatty(self) -> bool: ...


def detect_colors(stream: _SupportsIsatty = sys.stderr) -> bool:
    """Detect whether terminal log output should include ANSI colors."""
    import os

    force_color = os.environ.get("FORCE_COLOR", "").lower()
    if force_color not in ("", "0", "false", "no"):
        return True

    if os.environ.get("NO_COLOR") is not None:
        return False

    return stream.isatty()


class SibylRenderer:
    """Custom structlog renderer with Sibyl theming.

    Output format: service | HH:MM:SS | level | message key=value...

    Example:
        api    | 00:17:08 | info  | Starting server port=3334 host=0.0.0.0
        worker | 00:17:09 | debug | Processing job job_id=abc123
    """

    def __init__(
        self,
        service_name: str = "sibyl",
        service_width: int = 7,
        colors: bool | None = None,
        max_exception_frames: int = 5,
        show_service: bool = True,
    ) -> None:
        """Initialize the renderer.

        Args:
            service_name: Service identifier (api, worker, cli, etc.)
            service_width: Width for service name padding
            colors: Enable colors (auto-detect TTY/FORCE_COLOR if None)
            max_exception_frames: Max traceback frames to show
            show_service: Whether to show service prefix (False when concurrently provides it)
        """
        self.service_name = service_name
        self.service_width = service_width
        self.max_exception_frames = max_exception_frames
        self.show_service = show_service

        if colors is None:
            self.colors = detect_colors(sys.stderr)
        else:
            self.colors = colors

    def __call__(
        self,
        logger: WrappedLogger,
        method_name: str,
        event_dict: EventDict,
    ) -> str:
        """Render a log event to a formatted string."""
        # Extract standard fields
        timestamp = event_dict.pop("timestamp", datetime.now().strftime("%H:%M:%S"))
        level = event_dict.pop("level", method_name).lower()
        event = str(event_dict.pop("event", ""))

        # Handle exception info
        exc_info = event_dict.pop("exc_info", None)
        exception_str = ""
        if exc_info:
            exception_str = self._format_exception(exc_info)

        # Format remaining key-value pairs
        kv_pairs = self._format_kv_pairs(event_dict)

        # Build the log line
        if self.colors:
            svc_color = SERVICE_COLORS.get(self.service_name, ANSI_ELECTRIC_PURPLE)
            service = f"{svc_color}{self.service_name:<{self.service_width}}{ANSI_RESET}"
            ts = f"{ANSI_DIM}{timestamp}{ANSI_RESET}"
            lvl_color = LEVEL_COLORS.get(level, LEVEL_COLORS["info"])
            lvl = f"{lvl_color}{level:<5}{ANSI_RESET}"
            msg = event
            kv = f"{ANSI_DIM}{kv_pairs}{ANSI_RESET}" if kv_pairs else ""
        else:
            service = f"{self.service_name:<{self.service_width}}"
            ts = timestamp
            lvl = f"{level:<5}"
            msg = event
            kv = kv_pairs

        # Build line with or without service prefix
        line = f"{service} | {ts} | {lvl} | {msg}" if self.show_service else f"{ts} | {lvl} | {msg}"
        if kv:
            line += f" {kv}"
        if exception_str:
            line += f"\n{exception_str}"

        return line

    def _format_kv_pairs(self, event_dict: EventDict) -> str:
        """Format key-value pairs in a clean, readable way."""
        pairs = []
        for key, value in event_dict.items():
            if key.startswith("_"):
                continue

            # Colorize values based on type
            if self.colors:
                if isinstance(value, bool):
                    color = ANSI_SUCCESS_GREEN if value else ANSI_ERROR_RED
                    formatted = f"{key}={color}{value}{ANSI_RESET}"
                elif isinstance(value, (int, float)):
                    formatted = f"{key}={ANSI_CORAL}{value}{ANSI_RESET}"
                else:
                    formatted = f"{key}={value}"
            else:
                formatted = f"{key}={value}"

            pairs.append(formatted)

        return " ".join(pairs)

    def _format_exception(self, exc_info: tuple[Any, ...] | bool) -> str:
        """Format exception with clean, concise output.

        - Max N frames (most recent)
        - No local variables
        - Colored exception type
        - Copy-paste friendly
        """
        if exc_info is True:
            exc_info = sys.exc_info()

        if not exc_info or exc_info[0] is None:
            return ""

        exc_type, exc_value, exc_tb = exc_info

        # Get traceback lines, limit to most recent frames
        tb_lines = traceback.format_tb(exc_tb)
        if len(tb_lines) > self.max_exception_frames:
            tb_lines = ["  ... (truncated)\n", *tb_lines[-self.max_exception_frames :]]

        # Format cleanly with consistent indentation
        indent = "         "  # Align with message content
        formatted_tb = "".join(tb_lines).rstrip()
        formatted_tb = "\n".join(indent + line for line in formatted_tb.split("\n"))

        # Exception name with module
        exc_name = exc_type.__name__
        if exc_type.__module__ and exc_type.__module__ != "builtins":
            exc_name = f"{exc_type.__module__}.{exc_name}"

        if self.colors:
            return (
                f"{indent}{ANSI_ERROR_RED}{exc_name}: {exc_value}{ANSI_RESET}\n"
                f"{ANSI_DIM}{formatted_tb}{ANSI_RESET}"
            )
        return f"{indent}{exc_name}: {exc_value}\n{formatted_tb}"
