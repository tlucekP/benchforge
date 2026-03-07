"""BenchForge PR Guard — regression check for pull requests.

Workflow:
  1. On the base branch (main/master), save a baseline:
         benchforge pr-guard . --save-baseline
     This writes .benchforge_baseline.json to the project root.

  2. On the PR branch, check for regression:
         benchforge pr-guard . --max-drop 5
     Exits with code 1 if the current score dropped by more than max_drop
     points compared to the saved baseline.

Business logic only — no CLI, no rich output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from benchforge.core.scanner import scan_project, ScanResult
from benchforge.core.analyzer import analyze_project, AnalysisResult
from benchforge.core.scoring import compute_score, ScoreResult
from benchforge.core.config import BenchForgeConfig

BASELINE_FILENAME = ".benchforge_baseline.json"

DEFAULT_MAX_DROP = 5


# ---------------------------------------------------------------------------
# Baseline I/O
# ---------------------------------------------------------------------------

@dataclass
class Baseline:
    """Persisted snapshot of a project's scores."""

    benchforge_score: int
    performance: int
    maintainability: int
    memory: int
    saved_at: str  # ISO-8601 timestamp (informational only)

    def to_dict(self) -> dict:
        return {
            "benchforge_score": self.benchforge_score,
            "performance": self.performance,
            "maintainability": self.maintainability,
            "memory": self.memory,
            "saved_at": self.saved_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Baseline":
        return cls(
            benchforge_score=int(data["benchforge_score"]),
            performance=int(data["performance"]),
            maintainability=int(data["maintainability"]),
            memory=int(data["memory"]),
            saved_at=str(data.get("saved_at", "")),
        )


def save_baseline(project_path: Path, score: ScoreResult) -> Path:
    """Write current scores to .benchforge_baseline.json.

    Args:
        project_path: Project root directory.
        score: ScoreResult from the current analysis.

    Returns:
        Path to the written baseline file.
    """
    from datetime import datetime, timezone

    baseline = Baseline(
        benchforge_score=score.benchforge_score,
        performance=score.performance,
        maintainability=score.maintainability,
        memory=score.memory,
        saved_at=datetime.now(timezone.utc).isoformat(),
    )
    baseline_path = project_path / BASELINE_FILENAME
    baseline_path.write_text(
        json.dumps(baseline.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return baseline_path


def load_baseline(project_path: Path) -> Baseline:
    """Load .benchforge_baseline.json from project_path.

    Raises:
        FileNotFoundError: If no baseline file exists.
        ValueError: If the baseline file is malformed.
    """
    baseline_path = project_path / BASELINE_FILENAME
    if not baseline_path.exists():
        raise FileNotFoundError(
            f"No baseline found at {baseline_path}. "
            f"Run 'benchforge pr-guard . --save-baseline' on the base branch first."
        )
    try:
        data = json.loads(baseline_path.read_text(encoding="utf-8"))
        return Baseline.from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError(f"Malformed baseline file {baseline_path}: {exc}") from exc


# ---------------------------------------------------------------------------
# Regression result
# ---------------------------------------------------------------------------

@dataclass
class PrGuardResult:
    """Result of a PR regression check."""

    path: Path
    scan: ScanResult
    analysis: AnalysisResult
    score: ScoreResult
    baseline: Baseline
    max_drop: int
    passed: bool

    @property
    def actual_score(self) -> int:
        return self.score.benchforge_score

    @property
    def baseline_score(self) -> int:
        return self.baseline.benchforge_score

    @property
    def score_delta(self) -> int:
        """Current score minus baseline score. Negative = regression."""
        return self.actual_score - self.baseline_score

    @property
    def regression(self) -> int:
        """Points dropped below baseline (0 if no regression)."""
        return max(0, -self.score_delta)


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

def run_pr_guard(
    project_path: Path,
    config: BenchForgeConfig,
    *,
    max_drop: int = DEFAULT_MAX_DROP,
) -> PrGuardResult:
    """Analyse the project and compare against the saved baseline.

    Args:
        project_path: Directory to analyse.
        config: BenchForge configuration.
        max_drop: Maximum allowed score drop (inclusive). Default 5.

    Returns:
        PrGuardResult with passed=True when regression <= max_drop.

    Raises:
        FileNotFoundError: If no baseline file exists.
        ValueError: If the project has no files or baseline is malformed.
        NotADirectoryError: If project_path is not a directory.
    """
    baseline = load_baseline(project_path)

    scan = scan_project(project_path)
    if scan.file_count == 0:
        raise ValueError(f"No files found in {project_path}")

    analysis = analyze_project(scan)
    score = compute_score(analysis, config=config)

    regression = max(0, baseline.benchforge_score - score.benchforge_score)
    passed = regression <= max_drop

    return PrGuardResult(
        path=project_path,
        scan=scan,
        analysis=analysis,
        score=score,
        baseline=baseline,
        max_drop=max_drop,
        passed=passed,
    )
