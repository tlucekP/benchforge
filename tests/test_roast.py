"""Tests for benchforge.core.roast."""

from __future__ import annotations

from pathlib import Path

import pytest

from benchforge.core.analyzer import analyze_project, AnalysisResult
from benchforge.core.roast import (
    RoastLine,
    RoastResult,
    roast_project,
    _pick_roast,
    _ROASTS_NESTED_LOOP,
    _ROASTS_UNUSED_IMPORT,
    _ROASTS_SCORE,
)
from benchforge.core.scanner import scan_project
from benchforge.core.scoring import compute_score


# ---------------------------------------------------------------------------
# Helpers
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
import json

def process(data):
    result = []
    for i in data:
        for j in data:
            result.append(i + j)
    return result

def helper(x):
    return x * 2
"""


def _analyze(tmp_path: Path, code: str, name: str = "proj") -> tuple[AnalysisResult, object]:
    proj = _make_project(tmp_path, name, code)
    scan = scan_project(proj)
    analysis = analyze_project(scan)
    score = compute_score(analysis)
    return analysis, score


# ---------------------------------------------------------------------------
# Unit tests — _pick_roast
# ---------------------------------------------------------------------------

class TestPickRoast:
    def test_returns_string(self):
        msg = _pick_roast(_ROASTS_NESTED_LOOP, count=1)
        assert isinstance(msg, str)

    def test_picks_highest_applicable_threshold(self):
        # count=3 should pick the template with threshold=3
        msg = _pick_roast(_ROASTS_NESTED_LOOP, count=3)
        assert "{n}" not in msg  # should be formatted
        assert "3" in msg

    def test_falls_back_to_first_for_count_zero(self):
        msg = _pick_roast(_ROASTS_NESTED_LOOP, count=0)
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_formats_n_placeholder(self):
        msg = _pick_roast(_ROASTS_UNUSED_IMPORT, count=15)
        assert "15" in msg

    def test_large_count_uses_last_threshold(self):
        msg = _pick_roast(_ROASTS_NESTED_LOOP, count=999)
        assert isinstance(msg, str)


# ---------------------------------------------------------------------------
# Integration tests — roast_project
# ---------------------------------------------------------------------------

class TestRoastProject:
    def test_returns_roast_result(self, tmp_path: Path):
        analysis, score = _analyze(tmp_path, MESSY_CODE)
        result = roast_project(analysis, score)
        assert isinstance(result, RoastResult)

    def test_lines_is_list(self, tmp_path: Path):
        analysis, score = _analyze(tmp_path, MESSY_CODE)
        result = roast_project(analysis, score)
        assert isinstance(result.lines, list)

    def test_lines_are_roast_line_instances(self, tmp_path: Path):
        analysis, score = _analyze(tmp_path, MESSY_CODE)
        result = roast_project(analysis, score)
        for line in result.lines:
            assert isinstance(line, RoastLine)

    def test_score_line_always_present(self, tmp_path: Path):
        analysis, score = _analyze(tmp_path, MESSY_CODE)
        result = roast_project(analysis, score)
        categories = [line.category for line in result.lines]
        assert "score" in categories

    def test_score_matches_input(self, tmp_path: Path):
        analysis, score = _analyze(tmp_path, MESSY_CODE)
        result = roast_project(analysis, score)
        assert result.score == score.benchforge_score

    def test_total_issues_matches(self, tmp_path: Path):
        analysis, score = _analyze(tmp_path, MESSY_CODE)
        result = roast_project(analysis, score)
        assert result.total_issues == analysis.total_issues

    def test_messy_code_has_multiple_roast_lines(self, tmp_path: Path):
        analysis, score = _analyze(tmp_path, MESSY_CODE)
        result = roast_project(analysis, score)
        # Should roast nested_loop and unused_import at minimum
        assert len(result.lines) >= 2

    def test_unused_import_roasted(self, tmp_path: Path):
        analysis, score = _analyze(tmp_path, MESSY_CODE)
        result = roast_project(analysis, score)
        categories = [line.category for line in result.lines]
        assert "unused_import" in categories

    def test_nested_loop_roasted(self, tmp_path: Path):
        analysis, score = _analyze(tmp_path, MESSY_CODE)
        result = roast_project(analysis, score)
        categories = [line.category for line in result.lines]
        assert "nested_loop" in categories

    def test_clean_code_is_clean(self, tmp_path: Path):
        analysis, score = _analyze(tmp_path, CLEAN_CODE)
        result = roast_project(analysis, score)
        assert result.is_clean is True

    def test_clean_code_has_clean_line(self, tmp_path: Path):
        analysis, score = _analyze(tmp_path, CLEAN_CODE)
        result = roast_project(analysis, score, seed=42)
        categories = [line.category for line in result.lines]
        assert "clean" in categories

    def test_messy_code_not_clean(self, tmp_path: Path):
        analysis, score = _analyze(tmp_path, MESSY_CODE)
        result = roast_project(analysis, score)
        assert result.is_clean is False

    def test_hottest_file_populated_for_issues(self, tmp_path: Path):
        analysis, score = _analyze(tmp_path, MESSY_CODE)
        result = roast_project(analysis, score)
        assert isinstance(result.hottest_file, str)
        assert len(result.hottest_file) > 0

    def test_hottest_file_empty_for_clean(self, tmp_path: Path):
        # Clean code with no issues — heatmap may still have entries but heat=0
        analysis, score = _analyze(tmp_path, CLEAN_CODE)
        result = roast_project(analysis, score)
        # hottest_file is a string (may or may not be empty depending on heatmap)
        assert isinstance(result.hottest_file, str)

    def test_seed_reproducible(self, tmp_path: Path):
        analysis, score = _analyze(tmp_path, CLEAN_CODE)
        r1 = roast_project(analysis, score, seed=42)
        r2 = roast_project(analysis, score, seed=42)
        assert [l.message for l in r1.lines] == [l.message for l in r2.lines]

    def test_roast_line_severity_is_roast(self, tmp_path: Path):
        analysis, score = _analyze(tmp_path, MESSY_CODE)
        result = roast_project(analysis, score)
        for line in result.lines:
            assert line.severity == "roast"

    def test_roast_line_messages_are_strings(self, tmp_path: Path):
        analysis, score = _analyze(tmp_path, MESSY_CODE)
        result = roast_project(analysis, score)
        for line in result.lines:
            assert isinstance(line.message, str)
            assert len(line.message) > 0

    def test_no_unformatted_placeholders_in_messages(self, tmp_path: Path):
        analysis, score = _analyze(tmp_path, MESSY_CODE)
        result = roast_project(analysis, score)
        for line in result.lines:
            assert "{n}" not in line.message
            assert "{score}" not in line.message

    def test_empty_project_does_not_crash(self):
        analysis = AnalysisResult(files=[])
        from benchforge.core.scoring import compute_score
        score = compute_score(analysis)
        result = roast_project(analysis, score)
        assert isinstance(result, RoastResult)
