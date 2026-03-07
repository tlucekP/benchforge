"""BenchForge CI Guard — quality gate for CI/CD pipelines.

Runs the standard analysis pipeline and compares the BenchForge score
against a configured threshold. Exits with code 1 when the score is
below the threshold so CI pipelines can fail the build automatically.

Business logic only — no CLI, no rich output.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from benchforge.core.scanner import scan_project, ScanResult
from benchforge.core.analyzer import analyze_project, AnalysisResult
from benchforge.core.scoring import compute_score, ScoreResult
from benchforge.core.config import BenchForgeConfig


@dataclass
class CiResult:
    """Result of a CI quality-gate check."""

    path: Path
    scan: ScanResult
    analysis: AnalysisResult
    score: ScoreResult
    min_score: int
    passed: bool

    @property
    def actual_score(self) -> int:
        return self.score.benchforge_score

    @property
    def score_gap(self) -> int:
        """How many points below threshold (negative = passing)."""
        return self.min_score - self.actual_score


def run_ci_check(
    project_path: Path,
    config: BenchForgeConfig,
    *,
    min_score_override: int | None = None,
) -> CiResult:
    """Run the full analysis pipeline and evaluate the quality gate.

    Args:
        project_path: Directory to analyse.
        config: BenchForge configuration (weights, penalties, thresholds, ci).
        min_score_override: If provided, overrides config.ci.min_score.

    Returns:
        CiResult with passed=True when score >= threshold.

    Raises:
        NotADirectoryError: If project_path is not a directory.
        ValueError: If project_path contains no Python files.
    """
    min_score = min_score_override if min_score_override is not None else config.ci.min_score

    scan = scan_project(project_path)

    if scan.file_count == 0:
        raise ValueError(f"No files found in {project_path}")

    analysis = analyze_project(scan)
    score = compute_score(analysis, config=config)

    passed = score.benchforge_score >= min_score

    return CiResult(
        path=project_path,
        scan=scan,
        analysis=analysis,
        score=score,
        min_score=min_score,
        passed=passed,
    )
