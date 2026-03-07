"""Tests for benchforge.core.analyzer."""

from __future__ import annotations

from pathlib import Path

import pytest

from benchforge.core.analyzer import (
    analyze_file,
    analyze_project,
    AnalysisResult,
    FileAnalysis,
    Issue,
)
from benchforge.core.scanner import scan_project


class TestAnalyzeFile:
    def test_returns_file_analysis(self, clean_file: Path) -> None:
        result = analyze_file(clean_file, root=clean_file.parent)
        assert isinstance(result, FileAnalysis)

    def test_clean_file_no_issues(self, clean_file: Path) -> None:
        result = analyze_file(clean_file, root=clean_file.parent)
        assert result.parse_error is None
        # Clean file should have no nested loops or long functions
        issue_categories = {i.category for i in result.issues}
        assert "nested_loop" not in issue_categories
        assert "long_function" not in issue_categories

    def test_detects_nested_loop(self, issues_file: Path) -> None:
        result = analyze_file(issues_file, root=issues_file.parent)
        categories = [i.category for i in result.issues]
        assert "nested_loop" in categories

    def test_detects_long_function(self, issues_file: Path) -> None:
        result = analyze_file(issues_file, root=issues_file.parent)
        categories = [i.category for i in result.issues]
        assert "long_function" in categories

    def test_detects_unused_imports(self, issues_file: Path) -> None:
        result = analyze_file(issues_file, root=issues_file.parent)
        categories = [i.category for i in result.issues]
        assert "unused_import" in categories

    def test_issue_has_required_fields(self, issues_file: Path) -> None:
        result = analyze_file(issues_file, root=issues_file.parent)
        for issue in result.issues:
            assert isinstance(issue, Issue)
            assert issue.category
            assert issue.description
            assert issue.file
            assert issue.severity in ("warning", "error", "info")

    def test_function_count_positive(self, clean_file: Path) -> None:
        result = analyze_file(clean_file, root=clean_file.parent)
        assert result.function_count > 0

    def test_maintainability_index_range(self, clean_file: Path) -> None:
        result = analyze_file(clean_file, root=clean_file.parent)
        assert 0.0 <= result.maintainability_index <= 100.0

    def test_handles_syntax_error(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def broken(:\n    pass\n", encoding="utf-8")
        result = analyze_file(bad_file, root=tmp_path)
        assert result.parse_error is not None

    def test_handles_missing_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.py"
        result = analyze_file(missing, root=tmp_path)
        assert result.parse_error is not None

    def test_empty_file(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.py"
        empty.write_text("", encoding="utf-8")
        result = analyze_file(empty, root=tmp_path)
        assert result.parse_error is None
        assert result.issues == []

    def test_unused_import_specific_names(self, issues_file: Path) -> None:
        result = analyze_file(issues_file, root=issues_file.parent)
        unused = [i for i in result.issues if i.category == "unused_import"]
        unused_names = [i.description for i in unused]
        # sys and json are unused in sample_issues.py; os is used
        assert any("sys" in d for d in unused_names)
        assert any("json" in d for d in unused_names)
        assert not any("os" in d for d in unused_names)


class TestAnalyzeProject:
    def test_returns_analysis_result(self, single_file_project: Path) -> None:
        scan = scan_project(single_file_project)
        result = analyze_project(scan)
        assert isinstance(result, AnalysisResult)

    def test_files_list_populated(self, single_file_project: Path) -> None:
        scan = scan_project(single_file_project)
        result = analyze_project(scan)
        assert len(result.files) == 1

    def test_total_issues_integer(self, single_file_project: Path) -> None:
        scan = scan_project(single_file_project)
        result = analyze_project(scan)
        assert isinstance(result.total_issues, int)
        assert result.total_issues >= 0

    def test_issue_breakdown_is_dict(self, single_file_project: Path) -> None:
        scan = scan_project(single_file_project)
        result = analyze_project(scan)
        assert isinstance(result.issue_breakdown, dict)

    def test_empty_directory(self, empty_dir: Path) -> None:
        scan = scan_project(empty_dir)
        result = analyze_project(scan)
        assert result.files == []
        assert result.total_issues == 0

    def test_issues_fixture_has_issues(self, fixtures_dir: Path) -> None:
        scan = scan_project(fixtures_dir)
        result = analyze_project(scan)
        # The issues fixture must trigger at least one detected issue
        assert result.total_issues > 0

    def test_avg_complexity_non_negative(self, single_file_project: Path) -> None:
        scan = scan_project(single_file_project)
        result = analyze_project(scan)
        assert result.avg_complexity >= 0.0

    def test_non_python_files_not_analyzed(self, tmp_path: Path) -> None:
        (tmp_path / "readme.md").write_text("# Hello\n", encoding="utf-8")
        (tmp_path / "data.json").write_text("{}\n", encoding="utf-8")
        scan = scan_project(tmp_path)
        result = analyze_project(scan)
        assert result.files == []
