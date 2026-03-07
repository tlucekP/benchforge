"""Tests for benchforge.core.comparator."""

from __future__ import annotations

from pathlib import Path

import pytest

from benchforge.core.comparator import (
    CompareResult,
    ProjectSnapshot,
    compare_projects,
    _category_winner,
    _label,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(tmp_path: Path, name: str, content: str) -> Path:
    """Create a temporary project directory with a single Python file."""
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
            for k in data:
                result.append(i + j + k)
    return result

def helper(x):
    return x * 2
"""


# ---------------------------------------------------------------------------
# Unit tests — helpers
# ---------------------------------------------------------------------------

class TestCategoryWinner:
    def test_higher_is_better_left_wins(self):
        assert _category_winner(80.0, 60.0) == "left"

    def test_higher_is_better_right_wins(self):
        assert _category_winner(40.0, 70.0) == "right"

    def test_higher_is_better_tie(self):
        assert _category_winner(55.0, 55.0) == "tie"

    def test_lower_is_better_left_wins(self):
        assert _category_winner(5.0, 20.0, lower_is_better=True) == "left"

    def test_lower_is_better_right_wins(self):
        assert _category_winner(30.0, 10.0, lower_is_better=True) == "right"

    def test_lower_is_better_tie(self):
        assert _category_winner(7.0, 7.0, lower_is_better=True) == "tie"


class TestLabel:
    def test_returns_name(self, tmp_path: Path):
        p = tmp_path / "my_project"
        p.mkdir()
        assert _label(p) == "my_project"

    def test_returns_file_name(self, tmp_path: Path):
        f = tmp_path / "solution.py"
        f.write_text("x = 1")
        assert _label(f) == "solution.py"


# ---------------------------------------------------------------------------
# Integration tests — compare_projects()
# ---------------------------------------------------------------------------

class TestCompareProjects:
    def test_returns_compare_result(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", CLEAN_CODE)
        result = compare_projects(a, b)
        assert isinstance(result, CompareResult)

    def test_snapshots_have_correct_labels(self, tmp_path: Path):
        a = _make_project(tmp_path, "human", CLEAN_CODE)
        b = _make_project(tmp_path, "ai", CLEAN_CODE)
        result = compare_projects(a, b)
        assert result.left.label == "human"
        assert result.right.label == "ai"

    def test_custom_labels(self, tmp_path: Path):
        a = _make_project(tmp_path, "proj_a", CLEAN_CODE)
        b = _make_project(tmp_path, "proj_b", CLEAN_CODE)
        result = compare_projects(a, b, label_left="Human v1", label_right="GPT-4")
        assert result.left.label == "Human v1"
        assert result.right.label == "GPT-4"

    def test_snapshots_are_project_snapshots(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", CLEAN_CODE)
        result = compare_projects(a, b)
        assert isinstance(result.left, ProjectSnapshot)
        assert isinstance(result.right, ProjectSnapshot)

    def test_identical_projects_tie(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", CLEAN_CODE)
        result = compare_projects(a, b)
        assert result.winner == "tie"
        assert result.score_delta == 0

    def test_clean_vs_messy_clean_wins(self, tmp_path: Path):
        clean = _make_project(tmp_path, "clean", CLEAN_CODE)
        messy = _make_project(tmp_path, "messy", MESSY_CODE)
        result = compare_projects(clean, messy)
        # Clean code should beat messy code overall
        assert result.winner == "left"
        assert result.score_delta < 0  # right score - left score is negative

    def test_messy_vs_clean_right_loses(self, tmp_path: Path):
        messy = _make_project(tmp_path, "messy", MESSY_CODE)
        clean = _make_project(tmp_path, "clean", CLEAN_CODE)
        result = compare_projects(messy, clean)
        assert result.winner == "right"
        assert result.score_delta > 0

    def test_category_winners_present(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", CLEAN_CODE)
        result = compare_projects(a, b)
        expected_keys = {"performance", "maintainability", "memory", "issues", "complexity"}
        assert set(result.category_winners.keys()) == expected_keys

    def test_category_winner_values_valid(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", MESSY_CODE)
        result = compare_projects(a, b)
        valid = {"left", "right", "tie"}
        for val in result.category_winners.values():
            assert val in valid

    def test_issues_winner_favors_fewer_issues(self, tmp_path: Path):
        clean = _make_project(tmp_path, "clean", CLEAN_CODE)
        messy = _make_project(tmp_path, "messy", MESSY_CODE)
        result = compare_projects(clean, messy)
        # clean has fewer issues → issues winner should be "left"
        assert result.category_winners["issues"] == "left"

    def test_score_delta_is_right_minus_left(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", MESSY_CODE)
        result = compare_projects(a, b)
        expected_delta = (
            result.right.score.benchforge_score - result.left.score.benchforge_score
        )
        assert result.score_delta == expected_delta

    def test_scan_results_populated(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", CLEAN_CODE)
        result = compare_projects(a, b)
        assert result.left.scan.file_count >= 1
        assert result.right.scan.file_count >= 1

    def test_scores_in_range(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", MESSY_CODE)
        result = compare_projects(a, b)
        for snap in (result.left, result.right):
            assert 0 <= snap.score.benchforge_score <= 100
            assert 0 <= snap.score.performance <= 100
            assert 0 <= snap.score.maintainability <= 100
            assert 0 <= snap.score.memory <= 100

    def test_paths_stored(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", CLEAN_CODE)
        result = compare_projects(a, b)
        assert result.left.path == a
        assert result.right.path == b

    def test_nonexistent_path_raises(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        bad = tmp_path / "nonexistent"
        with pytest.raises(NotADirectoryError):
            compare_projects(a, bad)


# ---------------------------------------------------------------------------
# Multi-file project
# ---------------------------------------------------------------------------

class TestCompareMultiFile:
    def test_multi_file_projects(self, tmp_path: Path):
        """Both projects with multiple files should compare correctly."""
        a = tmp_path / "proj_a"
        a.mkdir()
        (a / "mod1.py").write_text(CLEAN_CODE, encoding="utf-8")
        (a / "mod2.py").write_text(CLEAN_CODE, encoding="utf-8")

        b = tmp_path / "proj_b"
        b.mkdir()
        (b / "mod1.py").write_text(MESSY_CODE, encoding="utf-8")
        (b / "mod2.py").write_text(MESSY_CODE, encoding="utf-8")

        result = compare_projects(a, b)
        assert result.winner == "left"  # clean should win
        assert result.left.scan.file_count == 2
        assert result.right.scan.file_count == 2
