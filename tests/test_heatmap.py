"""Tests for benchforge.core.heatmap."""

from __future__ import annotations

from pathlib import Path

import pytest

from benchforge.core.analyzer import analyze_project
from benchforge.core.heatmap import (
    FileHeatEntry,
    build_heatmap,
    _heat_level,
    _compute_heat,
    HEAT_CRITICAL,
    HEAT_HIGH,
    HEAT_MEDIUM,
)
from benchforge.core.scanner import scan_project
from benchforge.core.analyzer import AnalysisResult, FileAnalysis, Issue


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_project(tmp_path: Path, name: str, content: str) -> Path:
    proj = tmp_path / name
    proj.mkdir()
    (proj / "main.py").write_text(content, encoding="utf-8")
    return proj


CLEAN_CODE = """\
def add(a: int, b: int) -> int:
    return a + b

def greet(name: str) -> str:
    return f"Hello, {name}!"
"""

MESSY_CODE = """\
import os
import sys

def process(data):
    result = []
    for i in data:
        for j in data:
            result.append(i + j)
    return result
"""


# ---------------------------------------------------------------------------
# Unit tests — _heat_level
# ---------------------------------------------------------------------------

class TestHeatLevel:
    def test_critical(self):
        assert _heat_level(HEAT_CRITICAL) == "critical"
        assert _heat_level(100.0) == "critical"

    def test_high(self):
        assert _heat_level(HEAT_HIGH) == "high"
        assert _heat_level(HEAT_CRITICAL - 1) == "high"

    def test_medium(self):
        assert _heat_level(HEAT_MEDIUM) == "medium"
        assert _heat_level(HEAT_HIGH - 1) == "medium"

    def test_low(self):
        assert _heat_level(0.0) == "low"
        assert _heat_level(HEAT_MEDIUM - 1) == "low"


# ---------------------------------------------------------------------------
# Unit tests — _compute_heat
# ---------------------------------------------------------------------------

class TestComputeHeat:
    def _make_fa(self, n_issues: int, complexity: float, mi: float) -> FileAnalysis:
        fa = FileAnalysis(path=Path("dummy.py"))
        fa.avg_complexity = complexity
        fa.maintainability_index = mi
        for i in range(n_issues):
            fa.issues.append(
                Issue(category="test_issue", description="x", file="dummy.py", line=i + 1)
            )
        return fa

    def test_zero_issues_zero_complexity(self):
        fa = self._make_fa(0, 0.0, 100.0)
        score = _compute_heat(fa, max_issues=10, max_complexity=10.0)
        assert score == 0.0

    def test_max_issues_max_complexity_low_mi(self):
        fa = self._make_fa(10, 10.0, 0.0)
        score = _compute_heat(fa, max_issues=10, max_complexity=10.0)
        assert score == 100.0

    def test_score_in_range(self):
        fa = self._make_fa(5, 5.0, 50.0)
        score = _compute_heat(fa, max_issues=10, max_complexity=10.0)
        assert 0.0 <= score <= 100.0

    def test_more_issues_higher_heat(self):
        fa_few = self._make_fa(1, 2.0, 80.0)
        fa_many = self._make_fa(9, 2.0, 80.0)
        score_few = _compute_heat(fa_few, max_issues=10, max_complexity=10.0)
        score_many = _compute_heat(fa_many, max_issues=10, max_complexity=10.0)
        assert score_many > score_few

    def test_max_issues_zero_no_crash(self):
        fa = self._make_fa(0, 0.0, 100.0)
        score = _compute_heat(fa, max_issues=0, max_complexity=0.0)
        assert score == 0.0


# ---------------------------------------------------------------------------
# Integration tests — build_heatmap
# ---------------------------------------------------------------------------

class TestBuildHeatmap:
    def test_returns_list(self, tmp_path: Path):
        proj = _make_project(tmp_path, "proj", CLEAN_CODE)
        scan = scan_project(proj)
        analysis = analyze_project(scan)
        result = build_heatmap(analysis)
        assert isinstance(result, list)

    def test_returns_file_heat_entries(self, tmp_path: Path):
        proj = _make_project(tmp_path, "proj", MESSY_CODE)
        scan = scan_project(proj)
        analysis = analyze_project(scan)
        result = build_heatmap(analysis)
        for entry in result:
            assert isinstance(entry, FileHeatEntry)

    def test_sorted_hottest_first(self, tmp_path: Path):
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "clean.py").write_text(CLEAN_CODE, encoding="utf-8")
        (proj / "messy.py").write_text(MESSY_CODE, encoding="utf-8")
        scan = scan_project(proj)
        analysis = analyze_project(scan)
        result = build_heatmap(analysis)
        scores = [e.heat_score for e in result]
        assert scores == sorted(scores, reverse=True)

    def test_top_n_limits_results(self, tmp_path: Path):
        proj = tmp_path / "proj"
        proj.mkdir()
        for i in range(5):
            (proj / f"mod{i}.py").write_text(MESSY_CODE, encoding="utf-8")
        scan = scan_project(proj)
        analysis = analyze_project(scan)
        result = build_heatmap(analysis, top_n=3)
        assert len(result) <= 3

    def test_top_n_none_returns_all(self, tmp_path: Path):
        proj = tmp_path / "proj"
        proj.mkdir()
        for i in range(4):
            (proj / f"mod{i}.py").write_text(CLEAN_CODE, encoding="utf-8")
        scan = scan_project(proj)
        analysis = analyze_project(scan)
        result_all = build_heatmap(analysis, top_n=None)
        result_limited = build_heatmap(analysis, top_n=2)
        assert len(result_all) >= len(result_limited)

    def test_heat_level_is_valid(self, tmp_path: Path):
        proj = _make_project(tmp_path, "proj", MESSY_CODE)
        scan = scan_project(proj)
        analysis = analyze_project(scan)
        result = build_heatmap(analysis)
        valid_levels = {"critical", "high", "medium", "low"}
        for entry in result:
            assert entry.heat_level in valid_levels

    def test_heat_score_in_range(self, tmp_path: Path):
        proj = _make_project(tmp_path, "proj", MESSY_CODE)
        scan = scan_project(proj)
        analysis = analyze_project(scan)
        result = build_heatmap(analysis)
        for entry in result:
            assert 0.0 <= entry.heat_score <= 100.0

    def test_issue_breakdown_populated(self, tmp_path: Path):
        proj = _make_project(tmp_path, "proj", MESSY_CODE)
        scan = scan_project(proj)
        analysis = analyze_project(scan)
        result = build_heatmap(analysis)
        # messy code has unused imports → breakdown should have entries
        for entry in result:
            if entry.issue_count > 0:
                assert len(entry.issue_breakdown) > 0

    def test_empty_analysis_returns_empty(self):
        analysis = AnalysisResult(files=[])
        result = build_heatmap(analysis)
        assert result == []

    def test_messy_hotter_than_clean(self, tmp_path: Path):
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "clean.py").write_text(CLEAN_CODE, encoding="utf-8")
        (proj / "messy.py").write_text(MESSY_CODE, encoding="utf-8")
        scan = scan_project(proj)
        analysis = analyze_project(scan)
        result = build_heatmap(analysis)
        # hottest file should be the messy one
        hottest = result[0]
        assert "messy" in hottest.rel_path or hottest.issue_count > 0

    def test_rel_path_is_string(self, tmp_path: Path):
        proj = _make_project(tmp_path, "proj", CLEAN_CODE)
        scan = scan_project(proj)
        analysis = analyze_project(scan)
        result = build_heatmap(analysis)
        for entry in result:
            assert isinstance(entry.rel_path, str)
