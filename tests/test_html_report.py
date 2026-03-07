"""Tests for benchforge.report.html_report."""

from __future__ import annotations

from pathlib import Path

import pytest

from benchforge.core.analyzer import analyze_project
from benchforge.core.scanner import scan_project
from benchforge.core.scoring import compute_score
from benchforge.report.html_report import (
    build_report_data,
    generate_html_report,
    ReportData,
)


def _make_report_data(project_path: Path) -> ReportData:
    scan = scan_project(project_path)
    analysis = analyze_project(scan)
    score = compute_score(analysis)
    scan_summary = {
        "file_count": scan.file_count,
        "primary_language": scan.primary_language,
        "total_size_kb": scan.total_size_kb,
        "modules": scan.modules,
        "languages": scan.languages,
    }
    return build_report_data(
        project_path=project_path,
        scan_summary=scan_summary,
        analysis=analysis,
        score=score,
    )


class TestGenerateHtmlReport:
    def test_creates_file(self, single_file_project: Path, tmp_path: Path) -> None:
        data = _make_report_data(single_file_project)
        output = tmp_path / "report.html"
        result = generate_html_report(data, output)
        assert result.exists()

    def test_returns_path(self, single_file_project: Path, tmp_path: Path) -> None:
        data = _make_report_data(single_file_project)
        output = tmp_path / "report.html"
        result = generate_html_report(data, output)
        assert isinstance(result, Path)

    def test_html_content(self, single_file_project: Path, tmp_path: Path) -> None:
        data = _make_report_data(single_file_project)
        output = tmp_path / "report.html"
        generate_html_report(data, output)
        content = output.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "BenchForge" in content

    def test_contains_score_section(self, single_file_project: Path, tmp_path: Path) -> None:
        data = _make_report_data(single_file_project)
        output = tmp_path / "report.html"
        generate_html_report(data, output)
        content = output.read_text(encoding="utf-8")
        assert "BenchForge Score" in content

    def test_contains_issues_section(self, single_file_project: Path, tmp_path: Path) -> None:
        data = _make_report_data(single_file_project)
        output = tmp_path / "report.html"
        generate_html_report(data, output)
        content = output.read_text(encoding="utf-8")
        assert "Detected Issues" in content

    def test_contains_project_summary(self, single_file_project: Path, tmp_path: Path) -> None:
        data = _make_report_data(single_file_project)
        output = tmp_path / "report.html"
        generate_html_report(data, output)
        content = output.read_text(encoding="utf-8")
        assert "Project Summary" in content

    def test_html_escape_in_project_path(self, tmp_path: Path) -> None:
        """Project path containing HTML special chars must be escaped."""
        # Use a path with angle brackets in the string representation
        proj = tmp_path / "myproject"
        proj.mkdir()
        (proj / "main.py").write_text("x = 1\n", encoding="utf-8")

        scan = scan_project(proj)
        analysis = analyze_project(scan)
        score = compute_score(analysis)
        scan_summary = {
            "file_count": scan.file_count,
            "primary_language": scan.primary_language,
            "total_size_kb": scan.total_size_kb,
            "modules": scan.modules,
            "languages": scan.languages,
        }
        # Inject a path string with HTML-special chars manually for the test
        data = ReportData(
            project_path="<script>alert('xss')</script>",
            scan_summary=scan_summary,
            analysis=analysis,
            score=score,
            all_issues=[],
        )
        output = tmp_path / "report.html"
        generate_html_report(data, output)
        content = output.read_text(encoding="utf-8")
        # The raw <script> tag must NOT appear unescaped
        assert "<script>alert" not in content

    def test_creates_parent_directories(self, single_file_project: Path, tmp_path: Path) -> None:
        data = _make_report_data(single_file_project)
        nested = tmp_path / "a" / "b" / "c" / "report.html"
        generate_html_report(data, nested)
        assert nested.exists()

    def test_empty_project_report(self, empty_dir: Path, tmp_path: Path) -> None:
        data = _make_report_data(empty_dir)
        output = tmp_path / "empty_report.html"
        generate_html_report(data, output)
        assert output.exists()


class TestBuildReportData:
    def test_returns_report_data(self, single_file_project: Path) -> None:
        data = _make_report_data(single_file_project)
        assert isinstance(data, ReportData)

    def test_project_path_is_string(self, single_file_project: Path) -> None:
        data = _make_report_data(single_file_project)
        assert isinstance(data.project_path, str)

    def test_all_issues_is_list(self, single_file_project: Path) -> None:
        data = _make_report_data(single_file_project)
        assert isinstance(data.all_issues, list)
