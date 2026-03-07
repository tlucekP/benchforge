"""Shared pytest fixtures for BenchForge tests."""

from __future__ import annotations

from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def clean_file() -> Path:
    """Return path to the clean sample Python file."""
    return FIXTURES_DIR / "sample_clean.py"


@pytest.fixture()
def issues_file() -> Path:
    """Return path to the intentionally problematic sample Python file."""
    return FIXTURES_DIR / "sample_issues.py"


@pytest.fixture()
def fixtures_dir() -> Path:
    """Return the fixtures directory path."""
    return FIXTURES_DIR


@pytest.fixture()
def tmp_py_file(tmp_path: Path) -> Path:
    """Create a minimal temporary Python file for isolated tests."""
    f = tmp_path / "temp_module.py"
    f.write_text("def hello():\n    return 'hello'\n", encoding="utf-8")
    return f


@pytest.fixture()
def empty_dir(tmp_path: Path) -> Path:
    """Return an empty temporary directory."""
    d = tmp_path / "empty_project"
    d.mkdir()
    return d


@pytest.fixture()
def single_file_project(tmp_path: Path) -> Path:
    """A temp project directory with a single clean Python file."""
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "main.py").write_text(
        "def run():\n    return 42\n",
        encoding="utf-8",
    )
    return proj
