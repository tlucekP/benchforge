"""Plugin protocol for BenchForge language analysis extensions.

Plugins implement the AnalyzerPlugin protocol to extend BenchForge
with support for additional programming languages or analysis strategies.

Future plugin discovery will use importlib.metadata entry_points.
In MVP, plugins are registered manually via REGISTERED_PLUGINS.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from benchforge.core.analyzer import Issue


@runtime_checkable
class AnalyzerPlugin(Protocol):
    """Protocol that all BenchForge analyzer plugins must satisfy."""

    @property
    def name(self) -> str:
        """Human-readable plugin name, e.g. 'Python Analyzer'."""
        ...

    @property
    def supported_extensions(self) -> frozenset[str]:
        """File extensions this plugin handles, e.g. frozenset({'.py'})."""
        ...

    def analyze(self, path: Path) -> list[Issue]:
        """Analyze a single file and return a list of detected issues.

        Args:
            path: Absolute path to the file.

        Returns:
            List of Issue objects. Empty list if no issues found.
        """
        ...


# ---------------------------------------------------------------------------
# Plugin registry — in MVP populated at import time.
# Phase 2: replace with entry_points discovery.
# ---------------------------------------------------------------------------

_PLUGIN_REGISTRY: list[AnalyzerPlugin] = []


def register_plugin(plugin: AnalyzerPlugin) -> None:
    """Register a plugin instance in the global registry."""
    if not isinstance(plugin, AnalyzerPlugin):
        raise TypeError(
            f"Plugin must satisfy the AnalyzerPlugin protocol, got {type(plugin)}"
        )
    _PLUGIN_REGISTRY.append(plugin)


def get_plugins() -> list[AnalyzerPlugin]:
    """Return a copy of all registered plugins."""
    return list(_PLUGIN_REGISTRY)


def get_plugins_for_extension(ext: str) -> list[AnalyzerPlugin]:
    """Return plugins that support the given file extension.

    Args:
        ext: File extension including dot, e.g. '.py'.
    """
    return [p for p in _PLUGIN_REGISTRY if ext.lower() in p.supported_extensions]
