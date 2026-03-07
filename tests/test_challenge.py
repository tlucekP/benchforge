"""Tests for benchforge.core.challenge."""

from __future__ import annotations

from pathlib import Path

import pytest

from benchforge.core.challenge import (
    ChallengeResult,
    RankedEntry,
    CategoryRanking,
    run_challenge,
    _build_category_rankings,
)
from benchforge.core.comparator import ProjectSnapshot
from benchforge.core.analyzer import analyze_project, AnalysisResult
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
"""

MEDIUM_CODE = """\
import os

def run(items):
    result = []
    for item in items:
        result.append(item * 2)
    return result
"""


# ---------------------------------------------------------------------------
# Unit tests — run_challenge errors
# ---------------------------------------------------------------------------

class TestRunChallengeValidation:
    def test_raises_for_single_path(self, tmp_path: Path):
        proj = _make_project(tmp_path, "a", CLEAN_CODE)
        with pytest.raises(ValueError, match="at least 2"):
            run_challenge([proj])

    def test_raises_for_empty_paths(self):
        with pytest.raises(ValueError, match="at least 2"):
            run_challenge([])

    def test_raises_for_nonexistent_path(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        bad = tmp_path / "nonexistent"
        with pytest.raises(NotADirectoryError):
            run_challenge([a, bad])


# ---------------------------------------------------------------------------
# Integration tests — run_challenge
# ---------------------------------------------------------------------------

class TestRunChallenge:
    def test_returns_challenge_result(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", MESSY_CODE)
        result = run_challenge([a, b])
        assert isinstance(result, ChallengeResult)

    def test_entries_count_matches_paths(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", MESSY_CODE)
        c = _make_project(tmp_path, "c", MEDIUM_CODE)
        result = run_challenge([a, b, c])
        assert len(result.entries) == 3

    def test_entries_are_ranked_entry_instances(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", MESSY_CODE)
        result = run_challenge([a, b])
        for entry in result.entries:
            assert isinstance(entry, RankedEntry)

    def test_ranks_start_at_one(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", MESSY_CODE)
        result = run_challenge([a, b])
        ranks = [e.rank for e in result.entries]
        assert min(ranks) == 1

    def test_ranks_are_consecutive(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", MESSY_CODE)
        c = _make_project(tmp_path, "c", MEDIUM_CODE)
        result = run_challenge([a, b, c])
        ranks = sorted(e.rank for e in result.entries)
        assert ranks == [1, 2, 3]

    def test_entries_sorted_by_score_descending(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", MESSY_CODE)
        result = run_challenge([a, b])
        scores = [e.snapshot.score.benchforge_score for e in result.entries]
        assert scores == sorted(scores, reverse=True)

    def test_clean_beats_messy(self, tmp_path: Path):
        clean = _make_project(tmp_path, "clean", CLEAN_CODE)
        messy = _make_project(tmp_path, "messy", MESSY_CODE)
        result = run_challenge([clean, messy])
        assert result.entries[0].snapshot.label == "clean"

    def test_winner_is_first_entry_snapshot(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", MESSY_CODE)
        result = run_challenge([a, b])
        if not result.is_tie:
            assert result.winner is result.entries[0].snapshot

    def test_identical_projects_produce_tie(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", CLEAN_CODE)
        result = run_challenge([a, b])
        assert result.is_tie is True
        assert result.winner is None

    def test_custom_labels_applied(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", MESSY_CODE)
        result = run_challenge([a, b], labels=["Human", "AI"])
        labels = {e.snapshot.label for e in result.entries}
        assert "Human" in labels
        assert "AI" in labels

    def test_default_labels_are_dir_names(self, tmp_path: Path):
        a = _make_project(tmp_path, "human_impl", CLEAN_CODE)
        b = _make_project(tmp_path, "ai_impl", MESSY_CODE)
        result = run_challenge([a, b])
        labels = {e.snapshot.label for e in result.entries}
        assert "human_impl" in labels
        assert "ai_impl" in labels

    def test_category_rankings_present(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", MESSY_CODE)
        result = run_challenge([a, b])
        assert len(result.category_rankings) > 0

    def test_category_ranking_names(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", MESSY_CODE)
        result = run_challenge([a, b])
        cats = {cr.category for cr in result.category_rankings}
        assert "performance" in cats
        assert "maintainability" in cats
        assert "issues" in cats

    def test_category_rankings_have_all_labels(self, tmp_path: Path):
        a = _make_project(tmp_path, "alpha", CLEAN_CODE)
        b = _make_project(tmp_path, "beta", MESSY_CODE)
        c = _make_project(tmp_path, "gamma", MEDIUM_CODE)
        result = run_challenge([a, b, c])
        for cr in result.category_rankings:
            assert len(cr.ranked_labels) == 3

    def test_three_implementations_ranked(self, tmp_path: Path):
        a = _make_project(tmp_path, "clean", CLEAN_CODE)
        b = _make_project(tmp_path, "medium", MEDIUM_CODE)
        c = _make_project(tmp_path, "messy", MESSY_CODE)
        result = run_challenge([a, b, c])
        assert len(result.entries) == 3
        # clean should win
        assert result.entries[0].snapshot.label == "clean"

    def test_snapshot_paths_stored(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", MESSY_CODE)
        result = run_challenge([a, b])
        paths = {e.snapshot.path for e in result.entries}
        assert a in paths
        assert b in paths

    def test_scores_in_range(self, tmp_path: Path):
        a = _make_project(tmp_path, "a", CLEAN_CODE)
        b = _make_project(tmp_path, "b", MESSY_CODE)
        result = run_challenge([a, b])
        for entry in result.entries:
            assert 0 <= entry.snapshot.score.benchforge_score <= 100
