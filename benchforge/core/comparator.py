"""Comparator — side-by-side comparison of two projects or files.

Runs the full analysis pipeline on two targets independently
and produces a CompareResult for display or export.

Business logic only — no CLI or output formatting here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from benchforge.core.scanner import scan_project, ScanResult
from benchforge.core.analyzer import analyze_project, AnalysisResult
from benchforge.core.scoring import compute_score, ScoreResult
from benchforge.core.config import BenchForgeConfig


@dataclass
class ProjectSnapshot:
    """Analysis snapshot for a single project/file target."""

    label: str              # Display name (e.g. "human/" or "ai_solution.py")
    path: Path
    scan: ScanResult
    analysis: AnalysisResult
    score: ScoreResult


@dataclass
class CompareResult:
    """Side-by-side comparison of two project snapshots."""

    left: ProjectSnapshot
    right: ProjectSnapshot

    # Derived fields — computed by compare_projects()
    winner: str = ""            # "left", "right", or "tie"
    score_delta: int = 0        # right.score - left.score (positive = right wins)
    category_winners: dict[str, str] = field(default_factory=dict)
    # keys: "performance", "maintainability", "memory", "issues", "complexity"
    # values: "left", "right", "tie"


def _label(path: Path) -> str:
    """Human-friendly display label for a path."""
    return path.name if path.name else str(path)


def _category_winner(left_val: float, right_val: float, lower_is_better: bool = False) -> str:
    """Return 'left', 'right', or 'tie' based on which value is better."""
    if left_val == right_val:
        return "tie"
    if lower_is_better:
        return "left" if left_val < right_val else "right"
    return "left" if left_val > right_val else "right"


def compare_projects(
    path_left: Path,
    path_right: Path,
    label_left: str | None = None,
    label_right: str | None = None,
    config: BenchForgeConfig | None = None,
) -> CompareResult:
    """Run analysis on two targets and return a CompareResult.

    Args:
        path_left: Directory or file for the first target (e.g. human implementation).
        path_right: Directory or file for the second target (e.g. AI implementation).
        label_left: Optional display label for left target.
        label_right: Optional display label for right target.
        config: Optional shared BenchForgeConfig (scoring weights/penalties).
                If None, uses built-in defaults.

    Returns:
        CompareResult with both snapshots and derived winner info.

    Raises:
        NotADirectoryError: If either path does not exist or is not a directory.
    """
    cfg = config if config is not None else BenchForgeConfig()

    left_label = label_left or _label(path_left)
    right_label = label_right or _label(path_right)

    # --- Left side ---
    scan_l = scan_project(path_left)
    analysis_l = analyze_project(scan_l)
    score_l = compute_score(analysis_l, config=cfg)

    # --- Right side ---
    scan_r = scan_project(path_right)
    analysis_r = analyze_project(scan_r)
    score_r = compute_score(analysis_r, config=cfg)

    left = ProjectSnapshot(
        label=left_label,
        path=path_left,
        scan=scan_l,
        analysis=analysis_l,
        score=score_l,
    )
    right = ProjectSnapshot(
        label=right_label,
        path=path_right,
        scan=scan_r,
        analysis=analysis_r,
        score=score_r,
    )

    # --- Determine category winners ---
    category_winners = {
        "performance": _category_winner(score_l.performance, score_r.performance),
        "maintainability": _category_winner(score_l.maintainability, score_r.maintainability),
        "memory": _category_winner(score_l.memory, score_r.memory),
        "issues": _category_winner(
            analysis_l.total_issues, analysis_r.total_issues, lower_is_better=True
        ),
        "complexity": _category_winner(
            analysis_l.avg_complexity, analysis_r.avg_complexity, lower_is_better=True
        ),
    }

    # --- Overall winner ---
    score_delta = score_r.benchforge_score - score_l.benchforge_score
    if score_delta > 0:
        winner = "right"
    elif score_delta < 0:
        winner = "left"
    else:
        winner = "tie"

    return CompareResult(
        left=left,
        right=right,
        winner=winner,
        score_delta=score_delta,
        category_winners=category_winners,
    )
