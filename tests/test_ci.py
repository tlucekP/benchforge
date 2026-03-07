"""Tests for benchforge.core.ci_guard and the `benchforge ci` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from benchforge.cli.main import cli
from benchforge.core.ci_guard import run_ci_check, CiResult
from benchforge.core.config import BenchForgeConfig, CiConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CLEAN_CODE = """\
def add(a: int, b: int) -> int:
    return a + b

def greet(name: str) -> str:
    return f"Hello, {name}!"
"""

MESSY_CODE = """\
import os
import sys
import json
import re
import math

def do_stuff(items):
    result = []
    for i in items:
        for j in items:
            for k in items:
                if i == j == k:
                    result.append(i)
    return result

def another_long_function(a, b, c, d, e, f, g, h):
    x1 = a + b
    x2 = b + c
    x3 = c + d
    x4 = d + e
    x5 = e + f
    x6 = f + g
    x7 = g + h
    x8 = x1 + x2
    x9 = x3 + x4
    x10 = x5 + x6
    x11 = x7 + x8
    x12 = x9 + x10
    x13 = x11 + x12
    return x13
"""


def _make_project(tmp_path: Path, name: str, content: str) -> Path:
    proj = tmp_path / name
    proj.mkdir()
    (proj / "main.py").write_text(content, encoding="utf-8")
    return proj


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def clean_project(tmp_path: Path) -> Path:
    return _make_project(tmp_path, "clean", CLEAN_CODE)


@pytest.fixture()
def messy_project(tmp_path: Path) -> Path:
    return _make_project(tmp_path, "messy", MESSY_CODE)


# ---------------------------------------------------------------------------
# CiConfig tests
# ---------------------------------------------------------------------------

class TestCiConfig:
    def test_default_min_score(self) -> None:
        cfg = CiConfig()
        assert cfg.min_score == 60

    def test_custom_min_score(self) -> None:
        cfg = CiConfig(min_score=75)
        assert cfg.min_score == 75

    def test_validate_valid(self) -> None:
        CiConfig(min_score=0).validate()
        CiConfig(min_score=60).validate()
        CiConfig(min_score=100).validate()

    def test_validate_negative(self) -> None:
        with pytest.raises(ValueError, match="min_score"):
            CiConfig(min_score=-1).validate()

    def test_validate_above_100(self) -> None:
        with pytest.raises(ValueError, match="min_score"):
            CiConfig(min_score=101).validate()


# ---------------------------------------------------------------------------
# BenchForgeConfig — ci field
# ---------------------------------------------------------------------------

class TestBenchForgeConfigCi:
    def test_default_ci_field(self) -> None:
        cfg = BenchForgeConfig()
        assert isinstance(cfg.ci, CiConfig)
        assert cfg.ci.min_score == 60

    def test_config_toml_ci_section(self, tmp_path: Path) -> None:
        toml_content = "[ci]\nmin_score = 80\n"
        (tmp_path / ".benchforge.toml").write_text(toml_content, encoding="utf-8")
        (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
        from benchforge.core.config import load_config
        cfg = load_config(tmp_path)
        assert cfg.ci.min_score == 80

    def test_config_toml_invalid_min_score(self, tmp_path: Path) -> None:
        toml_content = "[ci]\nmin_score = 150\n"
        (tmp_path / ".benchforge.toml").write_text(toml_content, encoding="utf-8")
        from benchforge.core.config import load_config
        with pytest.raises(ValueError, match="min_score"):
            load_config(tmp_path)


# ---------------------------------------------------------------------------
# run_ci_check — core logic
# ---------------------------------------------------------------------------

class TestRunCiCheck:
    def test_returns_ci_result(self, clean_project: Path) -> None:
        cfg = BenchForgeConfig()
        result = run_ci_check(clean_project, cfg)
        assert isinstance(result, CiResult)

    def test_passes_with_low_threshold(self, clean_project: Path) -> None:
        cfg = BenchForgeConfig()
        result = run_ci_check(clean_project, cfg, min_score_override=0)
        assert result.passed is True

    def test_fails_with_high_threshold(self, clean_project: Path) -> None:
        cfg = BenchForgeConfig()
        result = run_ci_check(clean_project, cfg, min_score_override=100)
        assert result.passed is False

    def test_actual_score_matches_score_result(self, clean_project: Path) -> None:
        cfg = BenchForgeConfig()
        result = run_ci_check(clean_project, cfg)
        assert result.actual_score == result.score.benchforge_score

    def test_min_score_from_config(self, clean_project: Path) -> None:
        cfg = BenchForgeConfig(ci=CiConfig(min_score=0))
        result = run_ci_check(clean_project, cfg)
        assert result.min_score == 0
        assert result.passed is True

    def test_min_score_override_beats_config(self, clean_project: Path) -> None:
        cfg = BenchForgeConfig(ci=CiConfig(min_score=0))
        result = run_ci_check(clean_project, cfg, min_score_override=100)
        assert result.min_score == 100
        assert result.passed is False

    def test_score_gap_positive_when_failing(self, clean_project: Path) -> None:
        cfg = BenchForgeConfig()
        result = run_ci_check(clean_project, cfg, min_score_override=100)
        assert result.score_gap > 0

    def test_score_gap_non_positive_when_passing(self, clean_project: Path) -> None:
        cfg = BenchForgeConfig()
        result = run_ci_check(clean_project, cfg, min_score_override=0)
        assert result.score_gap <= 0

    def test_empty_project_raises(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        cfg = BenchForgeConfig()
        with pytest.raises(ValueError, match="No files"):
            run_ci_check(empty, cfg)

    def test_path_in_result(self, clean_project: Path) -> None:
        cfg = BenchForgeConfig()
        result = run_ci_check(clean_project, cfg)
        assert result.path == clean_project

    def test_scan_attached(self, clean_project: Path) -> None:
        cfg = BenchForgeConfig()
        result = run_ci_check(clean_project, cfg)
        assert result.scan.file_count >= 1

    def test_analysis_attached(self, clean_project: Path) -> None:
        cfg = BenchForgeConfig()
        result = run_ci_check(clean_project, cfg)
        assert result.analysis is not None


# ---------------------------------------------------------------------------
# CLI — benchforge ci (text mode)
# ---------------------------------------------------------------------------

class TestCliCiText:
    def test_passes_exit_0(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["ci", str(clean_project), "--min-score", "0"])
        assert result.exit_code == 0

    def test_fails_exit_1(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["ci", str(clean_project), "--min-score", "100"])
        assert result.exit_code == 1

    def test_passed_in_output(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["ci", str(clean_project), "--min-score", "0"])
        assert "PASSED" in result.output

    def test_failed_in_output(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["ci", str(clean_project), "--min-score", "100"])
        assert "FAILED" in result.output

    def test_invalid_path_exit_nonzero(self, runner: CliRunner, tmp_path: Path) -> None:
        nonexistent = tmp_path / "no_such_dir"
        result = runner.invoke(cli, ["ci", str(nonexistent)])
        assert result.exit_code != 0

    def test_default_threshold_shown(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["ci", str(clean_project)])
        # threshold or score must be present in output
        assert "60" in result.output or "Score" in result.output


# ---------------------------------------------------------------------------
# CLI — benchforge ci --format json
# ---------------------------------------------------------------------------

class TestCliCiJson:
    def test_json_output_is_valid(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["ci", str(clean_project), "--format", "json", "--min-score", "0"])
        data = json.loads(result.output)
        assert "passed" in data

    def test_json_passed_true_when_threshold_0(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["ci", str(clean_project), "--format", "json", "--min-score", "0"])
        data = json.loads(result.output)
        assert data["passed"] is True

    def test_json_passed_false_when_threshold_100(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["ci", str(clean_project), "--format", "json", "--min-score", "100"])
        data = json.loads(result.output)
        assert data["passed"] is False

    def test_json_exit_0_on_pass(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["ci", str(clean_project), "--format", "json", "--min-score", "0"])
        assert result.exit_code == 0

    def test_json_exit_1_on_fail(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["ci", str(clean_project), "--format", "json", "--min-score", "100"])
        assert result.exit_code == 1

    def test_json_contains_score_fields(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["ci", str(clean_project), "--format", "json", "--min-score", "0"])
        data = json.loads(result.output)
        assert "actual_score" in data
        assert "min_score" in data
        assert "score_gap" in data

    def test_json_contains_nested_score(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["ci", str(clean_project), "--format", "json", "--min-score", "0"])
        data = json.loads(result.output)
        assert "score" in data
        assert "benchforge_score" in data["score"]

    def test_json_contains_scan(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["ci", str(clean_project), "--format", "json", "--min-score", "0"])
        data = json.loads(result.output)
        assert "scan" in data
        assert data["scan"]["file_count"] >= 1

    def test_json_actual_score_consistent(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["ci", str(clean_project), "--format", "json", "--min-score", "0"])
        data = json.loads(result.output)
        assert data["actual_score"] == data["score"]["benchforge_score"]

    def test_json_min_score_reflects_override(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["ci", str(clean_project), "--format", "json", "--min-score", "42"])
        data = json.loads(result.output)
        assert data["min_score"] == 42
