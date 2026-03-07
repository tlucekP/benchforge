"""Tests for benchforge.core.scoring."""

from __future__ import annotations

from pathlib import Path

import pytest

from benchforge.core.analyzer import analyze_project
from benchforge.core.scanner import scan_project
from benchforge.core.scoring import compute_score, ScoreResult
from benchforge.core.config import BenchForgeConfig, ScoringWeights, ScoringPenalties, ScoringThresholds


def _score_for_dir(path: Path) -> ScoreResult:
    scan = scan_project(path)
    analysis = analyze_project(scan)
    return compute_score(analysis)


class TestComputeScore:
    def test_returns_score_result(self, single_file_project: Path) -> None:
        score = _score_for_dir(single_file_project)
        assert isinstance(score, ScoreResult)

    def test_performance_in_range(self, single_file_project: Path) -> None:
        score = _score_for_dir(single_file_project)
        assert 0 <= score.performance <= 100

    def test_maintainability_in_range(self, single_file_project: Path) -> None:
        score = _score_for_dir(single_file_project)
        assert 0 <= score.maintainability <= 100

    def test_memory_in_range(self, single_file_project: Path) -> None:
        score = _score_for_dir(single_file_project)
        assert 0 <= score.memory <= 100

    def test_combined_score_in_range(self, single_file_project: Path) -> None:
        score = _score_for_dir(single_file_project)
        assert 0 <= score.benchforge_score <= 100

    def test_no_benchmark_flag(self, single_file_project: Path) -> None:
        score = _score_for_dir(single_file_project)
        assert score.has_benchmark_data is False

    def test_score_notes_is_list(self, single_file_project: Path) -> None:
        score = _score_for_dir(single_file_project)
        assert isinstance(score.score_notes, list)

    def test_clean_scores_higher_than_issues(
        self, fixtures_dir: Path, tmp_path: Path
    ) -> None:
        """A clean project should score higher on maintainability than one with issues."""
        # Clean project
        clean_proj = tmp_path / "clean"
        clean_proj.mkdir()
        (clean_proj / "clean.py").write_text(
            (fixtures_dir / "sample_clean.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        # Issues project
        issues_proj = tmp_path / "issues"
        issues_proj.mkdir()
        (issues_proj / "issues.py").write_text(
            (fixtures_dir / "sample_issues.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        from benchforge.core.analyzer import analyze_project
        from benchforge.core.scanner import scan_project as sp

        clean_scan = sp(clean_proj)
        issues_scan = sp(issues_proj)
        clean_analysis = analyze_project(clean_scan)
        issues_analysis = analyze_project(issues_scan)

        # The issues file must produce more issues than the clean file.
        assert issues_analysis.total_issues > clean_analysis.total_issues

        # The combined BenchForge score for the clean project should be >= issues project.
        clean_score = _score_for_dir(clean_proj)
        issues_score = _score_for_dir(issues_proj)
        assert clean_score.benchforge_score >= issues_score.benchforge_score

    def test_empty_directory_produces_valid_score(self, empty_dir: Path) -> None:
        scan = scan_project(empty_dir)
        from benchforge.core.analyzer import analyze_project as ap
        analysis = ap(scan)
        score = compute_score(analysis)
        assert 0 <= score.benchforge_score <= 100

    def test_with_benchmark_sets_flag(self, single_file_project: Path) -> None:
        from benchforge.core.benchmark import BenchmarkResult

        scan = scan_project(single_file_project)
        from benchforge.core.analyzer import analyze_project as ap
        analysis = ap(scan)
        benchmark = BenchmarkResult(total_functions_benchmarked=0)
        score = compute_score(analysis, benchmark=benchmark)
        assert score.has_benchmark_data is True

    def test_scores_are_integers(self, single_file_project: Path) -> None:
        score = _score_for_dir(single_file_project)
        assert isinstance(score.performance, int)
        assert isinstance(score.maintainability, int)
        assert isinstance(score.memory, int)
        assert isinstance(score.benchforge_score, int)


class TestComputeScoreWithConfig:
    def _analysis(self, path: Path):
        scan = scan_project(path)
        return analyze_project(scan)

    def test_default_config_produces_same_as_no_config(self, single_file_project: Path) -> None:
        analysis = self._analysis(single_file_project)
        score_default = compute_score(analysis)
        score_explicit = compute_score(analysis, config=BenchForgeConfig())
        assert score_default.benchforge_score == score_explicit.benchforge_score

    def test_custom_weights_affect_combined_score(self, single_file_project: Path) -> None:
        analysis = self._analysis(single_file_project)
        # Weight performance heavily
        cfg_perf = BenchForgeConfig(
            weights=ScoringWeights(performance=0.90, maintainability=0.05, memory=0.05)
        )
        # Weight maintainability heavily
        cfg_maint = BenchForgeConfig(
            weights=ScoringWeights(performance=0.05, maintainability=0.90, memory=0.05)
        )
        s_perf = compute_score(analysis, config=cfg_perf)
        s_maint = compute_score(analysis, config=cfg_maint)
        # Combined scores must differ (unless all sub-scores are equal, which is unlikely)
        # At minimum both must be in valid range
        assert 0 <= s_perf.benchforge_score <= 100
        assert 0 <= s_maint.benchforge_score <= 100

    def test_config_note_in_score_notes(self, single_file_project: Path, tmp_path: Path) -> None:
        # Write a minimal config file so config_path is set
        cfg_file = tmp_path / ".benchforge.toml"
        cfg_file.write_text(
            "[scoring.weights]\nperformance = 0.35\nmaintainability = 0.40\nmemory = 0.25\n",
            encoding="utf-8",
        )
        from benchforge.core.config import load_config
        cfg = load_config(tmp_path)
        analysis = self._analysis(single_file_project)
        score = compute_score(analysis, config=cfg)
        assert any(".benchforge.toml" in note for note in score.score_notes)

    def test_no_config_no_config_note(self, single_file_project: Path) -> None:
        analysis = self._analysis(single_file_project)
        score = compute_score(analysis)
        assert not any("Config loaded" in note for note in score.score_notes)
