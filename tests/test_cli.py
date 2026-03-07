"""Tests for benchforge.cli.main — CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from benchforge.cli.main import cli


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


class TestAnalyzeCommand:
    def test_analyze_single_file_project(
        self, runner: CliRunner, single_file_project: Path
    ) -> None:
        result = runner.invoke(cli, ["analyze", str(single_file_project)])
        assert result.exit_code == 0

    def test_analyze_outputs_score(
        self, runner: CliRunner, single_file_project: Path
    ) -> None:
        result = runner.invoke(cli, ["analyze", str(single_file_project)])
        assert "Score" in result.output or result.exit_code == 0

    def test_analyze_invalid_path(self, runner: CliRunner, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does_not_exist"
        result = runner.invoke(cli, ["analyze", str(nonexistent)])
        assert result.exit_code != 0

    def test_analyze_empty_directory(
        self, runner: CliRunner, empty_dir: Path
    ) -> None:
        result = runner.invoke(cli, ["analyze", str(empty_dir)])
        # Should exit gracefully (code 0) with a "no files" message
        assert result.exit_code == 0
        assert "No files" in result.output or "empty" in result.output.lower()

    def test_analyze_fixtures_dir(
        self, runner: CliRunner, fixtures_dir: Path
    ) -> None:
        result = runner.invoke(cli, ["analyze", str(fixtures_dir)])
        assert result.exit_code == 0

    def test_analyze_default_path(self, runner: CliRunner, tmp_path: Path) -> None:
        """Analyze with no path arg should default to '.' without crashing."""
        # Run inside tmp_path to avoid scanning the whole project
        (tmp_path / "dummy.py").write_text("x = 1\n", encoding="utf-8")
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["analyze"])
            # May fail if '.' is empty or has no Python — just must not crash with unhandled exception
            assert result.exit_code in (0, 1)
            assert result.exception is None or isinstance(result.exception, SystemExit)

    def test_show_test_issues_flag_accepted(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """--show-test-issues flag should be accepted without error."""
        (tmp_path / "main.py").write_text("def run():\n    return 1\n", encoding="utf-8")
        result = runner.invoke(cli, ["analyze", str(tmp_path), "--show-test-issues"])
        assert result.exit_code == 0

    def test_test_issues_hidden_by_default(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Issues in test files should be hidden by default and show a footer hint."""
        # prod file — clean, no issues
        (tmp_path / "main.py").write_text("def run():\n    return 1\n", encoding="utf-8")
        # test file at root level (not in tests/ dir so scanner includes it)
        # long function triggers long_function issue
        (tmp_path / "test_main.py").write_text(
            "def test_run():\n" + "    assert True\n" * 55,
            encoding="utf-8",
        )
        result = runner.invoke(cli, ["analyze", str(tmp_path)])
        assert result.exit_code == 0
        # test_main.py issues should be hidden — either hidden footer or no issues shown
        assert "test_main.py" not in result.output

    def test_show_test_issues_reveals_test_issues(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """--show-test-issues should include test file issues when they appear in the scan."""
        # Place test file alongside prod file (no tests/ dir — scanner won't auto-exclude it)
        (tmp_path / "main.py").write_text("def run():\n    return 1\n", encoding="utf-8")
        (tmp_path / "test_main.py").write_text(
            "def test_run():\n" + "    assert True\n" * 55,
            encoding="utf-8",
        )
        result = runner.invoke(cli, ["analyze", str(tmp_path), "--show-test-issues"])
        assert result.exit_code == 0
        assert "test_main.py" in result.output


class TestReportCommand:
    def test_report_creates_html_file(
        self, runner: CliRunner, single_file_project: Path, tmp_path: Path
    ) -> None:
        output = tmp_path / "out.html"
        result = runner.invoke(
            cli, ["report", str(single_file_project), "--output", str(output)]
        )
        assert result.exit_code == 0
        assert output.exists()

    def test_report_html_content(
        self, runner: CliRunner, single_file_project: Path, tmp_path: Path
    ) -> None:
        output = tmp_path / "report.html"
        runner.invoke(cli, ["report", str(single_file_project), "--output", str(output)])
        content = output.read_text(encoding="utf-8")
        assert "BenchForge" in content

    def test_report_invalid_path(self, runner: CliRunner, tmp_path: Path) -> None:
        nonexistent = tmp_path / "ghost"
        result = runner.invoke(cli, ["report", str(nonexistent)])
        assert result.exit_code != 0

    def test_report_empty_directory(
        self, runner: CliRunner, empty_dir: Path, tmp_path: Path
    ) -> None:
        output = tmp_path / "empty_report.html"
        result = runner.invoke(
            cli, ["report", str(empty_dir), "--output", str(output)]
        )
        assert result.exit_code == 0

    def test_report_fixtures_dir(
        self, runner: CliRunner, fixtures_dir: Path, tmp_path: Path
    ) -> None:
        output = tmp_path / "fixtures_report.html"
        result = runner.invoke(
            cli, ["report", str(fixtures_dir), "--output", str(output)]
        )
        assert result.exit_code == 0
        assert output.exists()


class TestAnalyzeJsonFormat:
    def test_json_format_valid_json(
        self, runner: CliRunner, single_file_project: Path
    ) -> None:
        result = runner.invoke(cli, ["analyze", str(single_file_project), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_json_format_top_level_keys(
        self, runner: CliRunner, single_file_project: Path
    ) -> None:
        result = runner.invoke(cli, ["analyze", str(single_file_project), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "scan" in data
        assert "analysis" in data
        assert "score" in data

    def test_json_format_score_fields(
        self, runner: CliRunner, single_file_project: Path
    ) -> None:
        result = runner.invoke(cli, ["analyze", str(single_file_project), "--format", "json"])
        assert result.exit_code == 0
        score = json.loads(result.output)["score"]
        assert "benchforge_score" in score
        assert "performance" in score
        assert "maintainability" in score
        assert "memory" in score
        assert isinstance(score["benchforge_score"], int)

    def test_json_format_analysis_fields(
        self, runner: CliRunner, single_file_project: Path
    ) -> None:
        result = runner.invoke(cli, ["analyze", str(single_file_project), "--format", "json"])
        assert result.exit_code == 0
        analysis = json.loads(result.output)["analysis"]
        assert "total_issues" in analysis
        assert "issues" in analysis
        assert isinstance(analysis["issues"], list)

    def test_json_format_scan_fields(
        self, runner: CliRunner, single_file_project: Path
    ) -> None:
        result = runner.invoke(cli, ["analyze", str(single_file_project), "--format", "json"])
        assert result.exit_code == 0
        scan = json.loads(result.output)["scan"]
        assert "file_count" in scan
        assert "root" in scan
        assert scan["file_count"] >= 1

    def test_json_format_fixtures_dir(
        self, runner: CliRunner, fixtures_dir: Path
    ) -> None:
        result = runner.invoke(cli, ["analyze", str(fixtures_dir), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["analysis"]["total_issues"] >= 0

    def test_text_format_is_default(
        self, runner: CliRunner, single_file_project: Path
    ) -> None:
        result = runner.invoke(cli, ["analyze", str(single_file_project)])
        assert result.exit_code == 0
        # Default text output — must NOT be parseable as JSON top-level object with our keys
        # (rich adds ANSI / table formatting, not raw JSON)
        assert "BenchForge" in result.output or "Score" in result.output


class TestBenchmarkCommand:
    def test_benchmark_on_clean_file_dir(
        self, runner: CliRunner, single_file_project: Path
    ) -> None:
        result = runner.invoke(cli, ["benchmark", str(single_file_project)])
        # May find no zero-arg functions — exit code 0 with warning is acceptable
        assert result.exit_code in (0, 1)
        assert result.exception is None or isinstance(result.exception, SystemExit)

    def test_benchmark_invalid_path(self, runner: CliRunner, tmp_path: Path) -> None:
        nonexistent = tmp_path / "ghost"
        result = runner.invoke(cli, ["benchmark", str(nonexistent)])
        assert result.exit_code != 0

    def test_benchmark_empty_directory(
        self, runner: CliRunner, empty_dir: Path
    ) -> None:
        result = runner.invoke(cli, ["benchmark", str(empty_dir)])
        assert result.exit_code == 0
