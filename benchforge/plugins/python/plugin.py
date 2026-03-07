"""Built-in Python language plugin for BenchForge.

This plugin delegates to the core analyzer for Python-specific analysis.
It serves as the reference implementation for the plugin protocol.
"""

from __future__ import annotations

from pathlib import Path

from benchforge.core.analyzer import Issue, analyze_file
from benchforge.plugins.base import AnalyzerPlugin, register_plugin


class PythonAnalyzerPlugin:
    """Python language analyzer plugin."""

    @property
    def name(self) -> str:
        return "Python Analyzer"

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".py"})

    def analyze(self, path: Path) -> list[Issue]:
        """Analyze a Python file using the core AST-based analyzer.

        Args:
            path: Absolute path to a .py file.

        Returns:
            List of detected issues. Empty list for files with no issues.
        """
        if path.suffix.lower() not in self.supported_extensions:
            return []

        file_analysis = analyze_file(path, root=path.parent)
        return file_analysis.issues


# Register the built-in plugin on import.
_python_plugin = PythonAnalyzerPlugin()

# Validate protocol compliance at module load time (fast, no IO).
assert isinstance(_python_plugin, AnalyzerPlugin), (
    "PythonAnalyzerPlugin does not satisfy AnalyzerPlugin protocol"
)

register_plugin(_python_plugin)
