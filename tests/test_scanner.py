"""Tests for benchforge.core.scanner."""

from __future__ import annotations

from pathlib import Path

import pytest

from benchforge.core.scanner import scan_project, ScanResult


class TestScanProject:
    def test_returns_scan_result(self, single_file_project: Path) -> None:
        result = scan_project(single_file_project)
        assert isinstance(result, ScanResult)

    def test_file_count(self, single_file_project: Path) -> None:
        result = scan_project(single_file_project)
        assert result.file_count == 1

    def test_detects_python_language(self, single_file_project: Path) -> None:
        result = scan_project(single_file_project)
        assert "Python" in result.languages
        assert result.languages["Python"] == 1

    def test_primary_language_python(self, single_file_project: Path) -> None:
        result = scan_project(single_file_project)
        assert result.primary_language == "Python"

    def test_empty_directory(self, empty_dir: Path) -> None:
        result = scan_project(empty_dir)
        assert result.file_count == 0
        assert result.languages == {}
        assert result.primary_language is None

    def test_invalid_path_raises(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does_not_exist"
        with pytest.raises(NotADirectoryError):
            scan_project(nonexistent)

    def test_file_path_raises(self, tmp_py_file: Path) -> None:
        with pytest.raises(NotADirectoryError):
            scan_project(tmp_py_file)

    def test_total_size_positive(self, single_file_project: Path) -> None:
        result = scan_project(single_file_project)
        assert result.total_size_bytes > 0
        assert result.total_size_kb > 0

    def test_files_list_populated(self, single_file_project: Path) -> None:
        result = scan_project(single_file_project)
        assert len(result.files) == 1
        assert result.files[0].suffix == ".py"

    def test_detects_python_package_module(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "utils.py").write_text("x = 1\n", encoding="utf-8")
        result = scan_project(tmp_path)
        assert len(result.modules) >= 1

    def test_skips_hidden_directories(self, tmp_path: Path) -> None:
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "secret.py").write_text("x = 1\n", encoding="utf-8")
        visible = tmp_path / "visible.py"
        visible.write_text("y = 2\n", encoding="utf-8")
        result = scan_project(tmp_path)
        assert result.file_count == 1

    def test_skips_pycache(self, tmp_path: Path) -> None:
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "module.pyc").write_text("", encoding="utf-8")
        (tmp_path / "real.py").write_text("x = 1\n", encoding="utf-8")
        result = scan_project(tmp_path)
        # .pyc has no recognised language, but .py does
        py_files = [f for f in result.files if f.suffix == ".py"]
        assert len(py_files) == 1

    def test_multiple_languages(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "app.js").write_text("const x = 1;\n", encoding="utf-8")
        result = scan_project(tmp_path)
        assert "Python" in result.languages
        assert "JavaScript" in result.languages

    def test_root_is_resolved(self, single_file_project: Path) -> None:
        result = scan_project(single_file_project)
        assert result.root.is_absolute()
