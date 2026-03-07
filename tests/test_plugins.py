"""Tests for the BenchForge plugin system.

Includes:
  - protocol compliance tests for the built-in Python plugin
  - registry functionality
  - placeholder tests for future plugin support
"""

from __future__ import annotations

from pathlib import Path

import pytest

from benchforge.plugins.base import (
    AnalyzerPlugin,
    get_plugins,
    get_plugins_for_extension,
    register_plugin,
)
from benchforge.plugins.python.plugin import PythonAnalyzerPlugin


class TestAnalyzerPluginProtocol:
    def test_python_plugin_satisfies_protocol(self) -> None:
        plugin = PythonAnalyzerPlugin()
        assert isinstance(plugin, AnalyzerPlugin)

    def test_python_plugin_name(self) -> None:
        plugin = PythonAnalyzerPlugin()
        assert isinstance(plugin.name, str)
        assert plugin.name

    def test_python_plugin_extensions(self) -> None:
        plugin = PythonAnalyzerPlugin()
        assert isinstance(plugin.supported_extensions, frozenset)
        assert ".py" in plugin.supported_extensions

    def test_python_plugin_analyze_returns_list(self, clean_file: Path) -> None:
        plugin = PythonAnalyzerPlugin()
        issues = plugin.analyze(clean_file)
        assert isinstance(issues, list)

    def test_python_plugin_unsupported_extension(self, tmp_path: Path) -> None:
        js_file = tmp_path / "app.js"
        js_file.write_text("const x = 1;\n", encoding="utf-8")
        plugin = PythonAnalyzerPlugin()
        issues = plugin.analyze(js_file)
        assert issues == []


class TestPluginRegistry:
    def test_python_plugin_registered_on_import(self) -> None:
        """Importing the plugin module registers it automatically."""
        import benchforge.plugins.python.plugin  # noqa: F401  (side-effect import)
        plugins = get_plugins()
        names = [p.name for p in plugins]
        assert "Python Analyzer" in names

    def test_get_plugins_returns_list(self) -> None:
        plugins = get_plugins()
        assert isinstance(plugins, list)

    def test_get_plugins_for_py_extension(self) -> None:
        import benchforge.plugins.python.plugin  # noqa: F401
        py_plugins = get_plugins_for_extension(".py")
        assert len(py_plugins) >= 1

    def test_get_plugins_for_unknown_extension(self) -> None:
        result = get_plugins_for_extension(".cobol")
        assert result == []

    def test_register_invalid_plugin_raises(self) -> None:
        class NotAPlugin:
            pass

        with pytest.raises(TypeError):
            register_plugin(NotAPlugin())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Placeholder tests for future plugin support (Phase 2)
# ---------------------------------------------------------------------------

class TestFuturePluginSupport:
    """Placeholders for upcoming plugin features.

    These tests document expected behaviour and will be implemented
    when the features are ready (Phase 2).
    """

    @pytest.mark.skip(reason="Phase 2: entry_points discovery not yet implemented")
    def test_plugin_discovered_via_entry_points(self) -> None:
        """Plugins installed as packages should be auto-discovered."""
        pass

    @pytest.mark.skip(reason="Phase 2: JavaScript plugin not yet implemented")
    def test_javascript_plugin_registered(self) -> None:
        """A JS plugin should register and handle .js files."""
        pass

    @pytest.mark.skip(reason="Phase 2: plugin config file not yet implemented")
    def test_plugin_configurable_via_file(self) -> None:
        """Plugins should be configurable via benchforge.toml or similar."""
        pass
