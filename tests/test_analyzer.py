"""Tests for benchforge.core.analyzer."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from benchforge.core.analyzer import (
    _is_safe_inner_iterable,
    _is_test_file,
    analyze_file,
    analyze_project,
    AnalysisResult,
    FileAnalysis,
    Issue,
)
from benchforge.core.scanner import scan_project


class TestIsSafeInnerIterable:
    """Unit tests for the _is_safe_inner_iterable helper."""

    def _parse_expr(self, src: str) -> ast.expr:
        return ast.parse(src, mode="eval").body

    def test_small_range_is_safe(self) -> None:
        assert _is_safe_inner_iterable(self._parse_expr("range(4)")) is True

    def test_range_at_limit_is_safe(self) -> None:
        assert _is_safe_inner_iterable(self._parse_expr("range(16)")) is True

    def test_range_over_limit_is_not_safe(self) -> None:
        assert _is_safe_inner_iterable(self._parse_expr("range(17)")) is False

    def test_range_with_dynamic_arg_is_not_safe(self) -> None:
        assert _is_safe_inner_iterable(self._parse_expr("range(n)")) is False

    def test_range_len_is_not_safe(self) -> None:
        assert _is_safe_inner_iterable(self._parse_expr("range(len(items))")) is False

    def test_literal_tuple_is_safe(self) -> None:
        assert _is_safe_inner_iterable(self._parse_expr("('a', 'b', 'c')")) is True

    def test_literal_list_is_safe(self) -> None:
        assert _is_safe_inner_iterable(self._parse_expr("[1, 2, 3]")) is True

    def test_mixed_tuple_with_variable_is_not_safe(self) -> None:
        assert _is_safe_inner_iterable(self._parse_expr("('a', x)")) is False

    def test_variable_is_not_safe(self) -> None:
        assert _is_safe_inner_iterable(self._parse_expr("items")) is False

    def test_attribute_access_is_safe(self) -> None:
        assert _is_safe_inner_iterable(self._parse_expr("fa.issues")) is True

    def test_nested_attribute_access_is_safe(self) -> None:
        assert _is_safe_inner_iterable(self._parse_expr("node.children")) is True


class TestIsTestFile:
    def test_test_prefix_filename(self) -> None:
        assert _is_test_file("test_main.py") is True

    def test_test_suffix_filename(self) -> None:
        assert _is_test_file("main_test.py") is True

    def test_tests_directory(self) -> None:
        assert _is_test_file("tests/test_main.py") is True

    def test_test_directory(self) -> None:
        assert _is_test_file("test/test_main.py") is True

    def test_windows_path_separator(self) -> None:
        assert _is_test_file("tests\\test_main.py") is True

    def test_nested_tests_directory(self) -> None:
        assert _is_test_file("src/tests/test_utils.py") is True

    def test_prod_file_not_detected(self) -> None:
        assert _is_test_file("main.py") is False

    def test_prod_file_in_src(self) -> None:
        assert _is_test_file("src/core/analyzer.py") is False

    def test_file_with_test_in_name_but_not_prefix(self) -> None:
        assert _is_test_file("context.py") is False


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

    def test_ignores_future_annotations_import(self, tmp_path: Path) -> None:
        file = tmp_path / "future_annotations.py"
        file.write_text(
            "from __future__ import annotations\n\n"
            "def greet(name: str) -> str:\n"
            "    return name\n",
            encoding="utf-8",
        )
        result = analyze_file(file, root=tmp_path)
        unused = [i.description for i in result.issues if i.category == "unused_import"]
        assert not any("annotations" in description for description in unused)

    def test_ignores_imports_inside_type_checking_block(self, tmp_path: Path) -> None:
        file = tmp_path / "type_checking.py"
        file.write_text(
            "from __future__ import annotations\n"
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    from pathlib import Path\n"
            "    from collections import OrderedDict\n"
            "\n"
            "def greet(name: str) -> str:\n"
            "    return name\n",
            encoding="utf-8",
        )
        result = analyze_file(file, root=tmp_path)
        unused = [i.description for i in result.issues if i.category == "unused_import"]
        assert not any("Path" in d for d in unused)
        assert not any("OrderedDict" in d for d in unused)

    def test_short_duplicate_helpers_are_ignored(self, tmp_path: Path) -> None:
        left = tmp_path / "left.py"
        right = tmp_path / "right.py"
        left.write_text("def helper():\n    return 1\n", encoding="utf-8")
        right.write_text("def helper2():\n    return 1\n", encoding="utf-8")
        scan = scan_project(tmp_path)
        result = analyze_project(scan)
        assert result.issue_breakdown.get("duplicate_code", 0) == 0

    def test_nested_loop_small_range_not_flagged(self, tmp_path: Path) -> None:
        f = tmp_path / "small_range.py"
        f.write_text(
            "def process(data):\n"
            "    for item in data:\n"
            "        for i in range(4):\n"
            "            print(item, i)\n",
            encoding="utf-8",
        )
        result = analyze_file(f, root=tmp_path)
        categories = [i.category for i in result.issues]
        assert "nested_loop" not in categories

    def test_nested_loop_large_range_flagged(self, tmp_path: Path) -> None:
        f = tmp_path / "large_range.py"
        f.write_text(
            "def process(data):\n"
            "    for item in data:\n"
            "        for i in range(len(data)):\n"
            "            print(item, i)\n",
            encoding="utf-8",
        )
        result = analyze_file(f, root=tmp_path)
        categories = [i.category for i in result.issues]
        assert "nested_loop" in categories

    def test_nested_loop_literal_tuple_not_flagged(self, tmp_path: Path) -> None:
        f = tmp_path / "literal_tuple.py"
        f.write_text(
            "def process(sections):\n"
            "    for section in sections:\n"
            "        for key in ('a', 'b', 'c'):\n"
            "            print(section, key)\n",
            encoding="utf-8",
        )
        result = analyze_file(f, root=tmp_path)
        categories = [i.category for i in result.issues]
        assert "nested_loop" not in categories

    def test_nested_loop_dynamic_iterable_flagged(self, tmp_path: Path) -> None:
        f = tmp_path / "dynamic.py"
        f.write_text(
            "def find_pairs(items):\n"
            "    for i in items:\n"
            "        for j in items:\n"
            "            print(i, j)\n",
            encoding="utf-8",
        )
        result = analyze_file(f, root=tmp_path)
        categories = [i.category for i in result.issues]
        assert "nested_loop" in categories

    def test_nested_loop_attribute_access_not_flagged(self, tmp_path: Path) -> None:
        f = tmp_path / "attr_traversal.py"
        f.write_text(
            "def process(files):\n"
            "    for fa in files:\n"
            "        for issue in fa.issues:\n"
            "            print(issue)\n",
            encoding="utf-8",
        )
        result = analyze_file(f, root=tmp_path)
        categories = [i.category for i in result.issues]
        assert "nested_loop" not in categories

    def test_meaningful_duplicate_functions_are_detected(self, tmp_path: Path) -> None:
        left = tmp_path / "left.py"
        right = tmp_path / "right.py"
        body = (
            "def transform(items):\n"
            "    data = []\n"
            "    for item in items:\n"
            "        data.append(item * 2)\n"
            "    return data\n"
        )
        left.write_text(body, encoding="utf-8")
        right.write_text(body.replace("transform", "transform_again"), encoding="utf-8")
        scan = scan_project(tmp_path)
        result = analyze_project(scan)
        assert result.issue_breakdown.get("duplicate_code", 0) == 2
