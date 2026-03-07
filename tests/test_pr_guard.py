"""Tests for benchforge.core.pr_guard and the `benchforge pr-guard` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from benchforge.cli.main import cli
from benchforge.core.pr_guard import (
    Baseline,
    PrGuardResult,
    BASELINE_FILENAME,
    DEFAULT_MAX_DROP,
    load_baseline,
    save_baseline,
    run_pr_guard,
)
from benchforge.core.config import BenchForgeConfig
from benchforge.core.scanner import scan_project
from benchforge.core.analyzer import analyze_project
from benchforge.core.scoring import compute_score


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CLEAN_CODE = """\
def add(a: int, b: int) -> int:
    return a + b

def greet(name: str) -> str:
    return f"Hello, {name}!"
"""


def _make_project(tmp_path: Path, name: str, content: str) -> Path:
    proj = tmp_path / name
    proj.mkdir()
    (proj / "main.py").write_text(content, encoding="utf-8")
    return proj


def _write_baseline(project_path: Path, score: int) -> Path:
    """Write a minimal baseline JSON directly (bypass save_baseline)."""
    data = {
        "benchforge_score": score,
        "performance": score,
        "maintainability": score,
        "memory": score,
        "saved_at": "2025-01-01T00:00:00+00:00",
    }
    p = project_path / BASELINE_FILENAME
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def clean_project(tmp_path: Path) -> Path:
    return _make_project(tmp_path, "clean", CLEAN_CODE)


# ---------------------------------------------------------------------------
# Baseline dataclass
# ---------------------------------------------------------------------------

class TestBaseline:
    def test_to_dict_roundtrip(self) -> None:
        b = Baseline(benchforge_score=75, performance=80, maintainability=70,
                     memory=75, saved_at="2025-01-01T00:00:00+00:00")
        restored = Baseline.from_dict(b.to_dict())
        assert restored.benchforge_score == 75
        assert restored.performance == 80
        assert restored.saved_at == "2025-01-01T00:00:00+00:00"

    def test_from_dict_missing_saved_at_defaults(self) -> None:
        data = {"benchforge_score": 60, "performance": 60,
                "maintainability": 60, "memory": 60}
        b = Baseline.from_dict(data)
        assert b.saved_at == ""

    def test_from_dict_type_coercion(self) -> None:
        data = {"benchforge_score": "70", "performance": "70",
                "maintainability": "70", "memory": "70", "saved_at": ""}
        b = Baseline.from_dict(data)
        assert isinstance(b.benchforge_score, int)


# ---------------------------------------------------------------------------
# save_baseline / load_baseline
# ---------------------------------------------------------------------------

class TestBaselineIO:
    def test_save_creates_file(self, clean_project: Path) -> None:
        cfg = BenchForgeConfig()
        scan = scan_project(clean_project)
        analysis = analyze_project(scan)
        score = compute_score(analysis, config=cfg)
        path = save_baseline(clean_project, score)
        assert path.exists()

    def test_save_filename(self, clean_project: Path) -> None:
        cfg = BenchForgeConfig()
        scan = scan_project(clean_project)
        score = compute_score(analyze_project(scan), config=cfg)
        path = save_baseline(clean_project, score)
        assert path.name == BASELINE_FILENAME

    def test_save_contains_valid_json(self, clean_project: Path) -> None:
        cfg = BenchForgeConfig()
        scan = scan_project(clean_project)
        score = compute_score(analyze_project(scan), config=cfg)
        save_baseline(clean_project, score)
        data = json.loads((clean_project / BASELINE_FILENAME).read_text(encoding="utf-8"))
        assert "benchforge_score" in data

    def test_load_returns_baseline(self, clean_project: Path) -> None:
        _write_baseline(clean_project, 75)
        b = load_baseline(clean_project)
        assert isinstance(b, Baseline)
        assert b.benchforge_score == 75

    def test_load_missing_raises_file_not_found(self, tmp_path: Path) -> None:
        empty = tmp_path / "no_baseline"
        empty.mkdir()
        with pytest.raises(FileNotFoundError):
            load_baseline(empty)

    def test_load_malformed_raises_value_error(self, clean_project: Path) -> None:
        (clean_project / BASELINE_FILENAME).write_text("not-json{{{", encoding="utf-8")
        with pytest.raises(ValueError, match="Malformed"):
            load_baseline(clean_project)

    def test_save_load_roundtrip_score(self, clean_project: Path) -> None:
        cfg = BenchForgeConfig()
        scan = scan_project(clean_project)
        score = compute_score(analyze_project(scan), config=cfg)
        save_baseline(clean_project, score)
        b = load_baseline(clean_project)
        assert b.benchforge_score == score.benchforge_score


# ---------------------------------------------------------------------------
# run_pr_guard — core logic
# ---------------------------------------------------------------------------

class TestRunPrGuard:
    def test_returns_pr_guard_result(self, clean_project: Path) -> None:
        _write_baseline(clean_project, 0)
        cfg = BenchForgeConfig()
        result = run_pr_guard(clean_project, cfg, max_drop=100)
        assert isinstance(result, PrGuardResult)

    def test_passes_when_no_regression(self, clean_project: Path) -> None:
        _write_baseline(clean_project, 0)
        cfg = BenchForgeConfig()
        result = run_pr_guard(clean_project, cfg, max_drop=5)
        assert result.passed is True

    def test_fails_when_baseline_too_high(self, clean_project: Path) -> None:
        _write_baseline(clean_project, 100)
        cfg = BenchForgeConfig()
        result = run_pr_guard(clean_project, cfg, max_drop=0)
        assert result.passed is False

    def test_score_delta_positive_when_improving(self, clean_project: Path) -> None:
        _write_baseline(clean_project, 0)
        cfg = BenchForgeConfig()
        result = run_pr_guard(clean_project, cfg, max_drop=5)
        assert result.score_delta >= 0

    def test_regression_zero_when_passing(self, clean_project: Path) -> None:
        _write_baseline(clean_project, 0)
        cfg = BenchForgeConfig()
        result = run_pr_guard(clean_project, cfg, max_drop=100)
        assert result.regression == 0

    def test_regression_positive_when_failing(self, clean_project: Path) -> None:
        _write_baseline(clean_project, 100)
        cfg = BenchForgeConfig()
        result = run_pr_guard(clean_project, cfg, max_drop=0)
        assert result.regression > 0

    def test_max_drop_stored_in_result(self, clean_project: Path) -> None:
        _write_baseline(clean_project, 0)
        cfg = BenchForgeConfig()
        result = run_pr_guard(clean_project, cfg, max_drop=7)
        assert result.max_drop == 7

    def test_baseline_score_in_result(self, clean_project: Path) -> None:
        _write_baseline(clean_project, 42)
        cfg = BenchForgeConfig()
        result = run_pr_guard(clean_project, cfg, max_drop=100)
        assert result.baseline_score == 42

    def test_no_baseline_raises_file_not_found(self, tmp_path: Path) -> None:
        proj = tmp_path / "no_baseline"
        proj.mkdir()
        (proj / "main.py").write_text("x = 1\n", encoding="utf-8")
        cfg = BenchForgeConfig()
        with pytest.raises(FileNotFoundError):
            run_pr_guard(proj, cfg)

    def test_empty_project_raises_value_error(self, tmp_path: Path) -> None:
        proj = tmp_path / "empty"
        proj.mkdir()
        _write_baseline(proj, 50)
        cfg = BenchForgeConfig()
        with pytest.raises(ValueError, match="No files"):
            run_pr_guard(proj, cfg)

    def test_path_stored_in_result(self, clean_project: Path) -> None:
        _write_baseline(clean_project, 0)
        cfg = BenchForgeConfig()
        result = run_pr_guard(clean_project, cfg, max_drop=100)
        assert result.path == clean_project

    def test_default_max_drop_is_5(self) -> None:
        assert DEFAULT_MAX_DROP == 5


# ---------------------------------------------------------------------------
# CLI — pr-guard --save-baseline (text)
# ---------------------------------------------------------------------------

class TestCliPrGuardSaveBaseline:
    def test_save_baseline_exit_0(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["pr-guard", str(clean_project), "--save-baseline"])
        assert result.exit_code == 0

    def test_save_baseline_creates_file(self, runner: CliRunner, clean_project: Path) -> None:
        runner.invoke(cli, ["pr-guard", str(clean_project), "--save-baseline"])
        assert (clean_project / BASELINE_FILENAME).exists()

    def test_save_baseline_json_output(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["pr-guard", str(clean_project), "--save-baseline", "--format", "json"])
        data = json.loads(result.output)
        assert data["action"] == "baseline_saved"
        assert "score" in data

    def test_save_baseline_invalid_path(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(cli, ["pr-guard", str(tmp_path / "no_such"), "--save-baseline"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# CLI — pr-guard check (text)
# ---------------------------------------------------------------------------

class TestCliPrGuardCheck:
    def test_passes_with_zero_baseline(self, runner: CliRunner, clean_project: Path) -> None:
        _write_baseline(clean_project, 0)
        result = runner.invoke(cli, ["pr-guard", str(clean_project), "--max-drop", "100"])
        assert result.exit_code == 0

    def test_fails_with_100_baseline_0_drop(self, runner: CliRunner, clean_project: Path) -> None:
        _write_baseline(clean_project, 100)
        result = runner.invoke(cli, ["pr-guard", str(clean_project), "--max-drop", "0"])
        assert result.exit_code == 1

    def test_passed_in_output(self, runner: CliRunner, clean_project: Path) -> None:
        _write_baseline(clean_project, 0)
        result = runner.invoke(cli, ["pr-guard", str(clean_project), "--max-drop", "100"])
        assert "PASSED" in result.output

    def test_failed_in_output(self, runner: CliRunner, clean_project: Path) -> None:
        _write_baseline(clean_project, 100)
        result = runner.invoke(cli, ["pr-guard", str(clean_project), "--max-drop", "0"])
        assert "FAILED" in result.output

    def test_no_baseline_exits_1(self, runner: CliRunner, tmp_path: Path) -> None:
        proj = tmp_path / "no_baseline"
        proj.mkdir()
        (proj / "main.py").write_text("x = 1\n", encoding="utf-8")
        result = runner.invoke(cli, ["pr-guard", str(proj)])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# CLI — pr-guard --format json
# ---------------------------------------------------------------------------

class TestCliPrGuardJson:
    def test_json_valid(self, runner: CliRunner, clean_project: Path) -> None:
        _write_baseline(clean_project, 0)
        result = runner.invoke(cli, ["pr-guard", str(clean_project), "--format", "json", "--max-drop", "100"])
        data = json.loads(result.output)
        assert "passed" in data

    def test_json_passed_true(self, runner: CliRunner, clean_project: Path) -> None:
        _write_baseline(clean_project, 0)
        result = runner.invoke(cli, ["pr-guard", str(clean_project), "--format", "json", "--max-drop", "100"])
        data = json.loads(result.output)
        assert data["passed"] is True

    def test_json_passed_false(self, runner: CliRunner, clean_project: Path) -> None:
        _write_baseline(clean_project, 100)
        result = runner.invoke(cli, ["pr-guard", str(clean_project), "--format", "json", "--max-drop", "0"])
        data = json.loads(result.output)
        assert data["passed"] is False

    def test_json_contains_delta_fields(self, runner: CliRunner, clean_project: Path) -> None:
        _write_baseline(clean_project, 0)
        result = runner.invoke(cli, ["pr-guard", str(clean_project), "--format", "json", "--max-drop", "100"])
        data = json.loads(result.output)
        for key in ("actual_score", "baseline_score", "score_delta", "regression", "max_drop"):
            assert key in data

    def test_json_no_baseline_has_error(self, runner: CliRunner, tmp_path: Path) -> None:
        proj = tmp_path / "no_baseline"
        proj.mkdir()
        (proj / "main.py").write_text("x = 1\n", encoding="utf-8")
        result = runner.invoke(cli, ["pr-guard", str(proj), "--format", "json"])
        data = json.loads(result.output)
        assert "error" in data
        assert result.exit_code == 1

    def test_json_exit_0_on_pass(self, runner: CliRunner, clean_project: Path) -> None:
        _write_baseline(clean_project, 0)
        result = runner.invoke(cli, ["pr-guard", str(clean_project), "--format", "json", "--max-drop", "100"])
        assert result.exit_code == 0

    def test_json_exit_1_on_fail(self, runner: CliRunner, clean_project: Path) -> None:
        _write_baseline(clean_project, 100)
        result = runner.invoke(cli, ["pr-guard", str(clean_project), "--format", "json", "--max-drop", "0"])
        assert result.exit_code == 1
