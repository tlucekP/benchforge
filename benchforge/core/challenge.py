"""Challenge engine — compare N implementations and produce a ranked leaderboard.

Accepts 2 or more project paths, runs the full analysis pipeline on each,
and returns a ChallengeResult with all snapshots ranked by BenchForge score.

Business logic only — no CLI or output formatting here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from benchforge.core.comparator import ProjectSnapshot, _label
from benchforge.core.scanner import scan_project
from benchforge.core.analyzer import analyze_project
from benchforge.core.scoring import compute_score
from benchforge.core.config import BenchForgeConfig


@dataclass
class RankedEntry:
    """A single implementation with its rank in the challenge."""

    rank: int                   # 1 = best
    snapshot: ProjectSnapshot
    rank_change: int = 0        # reserved for future use (e.g. trend tracking)


@dataclass
class CategoryRanking:
    """Per-category ranking across all implementations."""

    category: str                           # "performance", "maintainability", etc.
    ranked_labels: list[str] = field(default_factory=list)   # best → worst
    scores: dict[str, float] = field(default_factory=dict)   # label -> value


@dataclass
class ChallengeResult:
    """Full leaderboard for N implementations."""

    entries: list[RankedEntry] = field(default_factory=list)    # rank 1 first
    winner: ProjectSnapshot | None = None
    category_rankings: list[CategoryRanking] = field(default_factory=list)
    is_tie: bool = False


def _analyze_snapshot(path: Path, label: str, cfg: BenchForgeConfig) -> ProjectSnapshot:
    """Run full pipeline on a single path and return a ProjectSnapshot."""
    scan = scan_project(path)
    analysis = analyze_project(scan)
    score = compute_score(analysis, config=cfg)
    return ProjectSnapshot(label=label, path=path, scan=scan, analysis=analysis, score=score)


def _build_category_rankings(snapshots: list[ProjectSnapshot]) -> list[CategoryRanking]:
    """Build per-category rankings (best → worst) across all snapshots."""
    categories = [
        ("performance",     lambda s: s.score.performance,           False),
        ("maintainability", lambda s: s.score.maintainability,       False),
        ("memory",          lambda s: s.score.memory,                False),
        ("issues",          lambda s: s.analysis.total_issues,       True),   # lower = better
        ("complexity",      lambda s: s.analysis.avg_complexity,     True),   # lower = better
    ]

    result: list[CategoryRanking] = []
    for cat_name, value_fn, lower_is_better in categories:
        scores = {s.label: float(value_fn(s)) for s in snapshots}
        ranked = sorted(snapshots, key=lambda s: value_fn(s), reverse=not lower_is_better)
        result.append(CategoryRanking(
            category=cat_name,
            ranked_labels=[s.label for s in ranked],
            scores=scores,
        ))
    return result


def run_challenge(
    paths: list[Path],
    labels: list[str] | None = None,
    config: BenchForgeConfig | None = None,
) -> ChallengeResult:
    """Run the challenge pipeline on N implementations.

    Args:
        paths: List of project directories to compare (minimum 2).
        labels: Optional display labels matching paths in order.
                Defaults to directory names.
        config: Optional shared BenchForgeConfig. Falls back to defaults if None.

    Returns:
        ChallengeResult with ranked entries and per-category rankings.

    Raises:
        ValueError: If fewer than 2 paths are provided.
        NotADirectoryError: If any path does not exist or is not a directory.
    """
    if len(paths) < 2:
        raise ValueError(f"Challenge requires at least 2 implementations, got {len(paths)}.")

    cfg = config if config is not None else BenchForgeConfig()

    resolved_labels: list[str] = []
    for i, path in enumerate(paths):
        if labels and i < len(labels) and labels[i]:
            resolved_labels.append(labels[i])
        else:
            resolved_labels.append(_label(path))

    # Analyze all implementations
    snapshots: list[ProjectSnapshot] = [
        _analyze_snapshot(path, label, cfg)
        for path, label in zip(paths, resolved_labels)
    ]

    # Rank by BenchForge score (descending — higher is better)
    ranked = sorted(snapshots, key=lambda s: s.score.benchforge_score, reverse=True)

    entries: list[RankedEntry] = []
    for rank, snap in enumerate(ranked, start=1):
        entries.append(RankedEntry(rank=rank, snapshot=snap))

    # Tie detection
    top_score = ranked[0].score.benchforge_score
    is_tie = len(ranked) > 1 and ranked[1].score.benchforge_score == top_score

    category_rankings = _build_category_rankings(snapshots)

    return ChallengeResult(
        entries=entries,
        winner=ranked[0] if not is_tie else None,
        category_rankings=category_rankings,
        is_tie=is_tie,
    )
