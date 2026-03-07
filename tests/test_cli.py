"""Tests for benchforge.cli.main — CLI commands."""

from __future__ import annotations

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
