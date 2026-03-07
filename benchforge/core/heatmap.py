"""Heatmap engine — ranks files by their combined quality heat score.

Heat score is a deterministic composite of:
  - issue count (primary driver)
  - average cyclomatic complexity
  - maintainability index (inverted — lower MI = hotter)

Higher heat = more problematic file.
Business logic only — no CLI or formatting here.
"""

from __future__ import annotations

from dataclasses import dataclass

from benchforge.core.analyzer import AnalysisResult, FileAnalysis


# Heat level thresholds (based on heat score 0–100)
HEAT_CRITICAL = 70
HEAT_HIGH = 40
HEAT_MEDIUM = 15


@dataclass
class FileHeatEntry:
    """Heat metrics for a single file."""

    rel_path: str           # display path relative to project root
    issue_count: int
    avg_complexity: float
    maintainability_index: float
    heat_score: float       # 0–100, higher = more problematic
    heat_level: str         # "critical" | "high" | "medium" | "low"
    issue_breakdown: dict[str, int]   # category -> count for this file


def _heat_level(score: float) -> str:
    if score >= HEAT_CRITICAL:
        return "critical"
    if score >= HEAT_HIGH:
        return "high"
    if score >= HEAT_MEDIUM:
        return "medium"
    return "low"


def _compute_heat(fa: FileAnalysis, max_issues: int, max_complexity: float) -> float:
    """Compute a 0–100 heat score for a single file.

    Weights:
      60% — issue count (normalized against project max)
      25% — cyclomatic complexity (normalized against project max)
      15% — maintainability index (inverted: lower MI = hotter)
    """
    # Issue component (0–100)
    issue_component = (fa.issues.__len__() / max_issues * 100) if max_issues > 0 else 0.0

    # Complexity component (0–100)
    if max_complexity > 0:
        complexity_component = min(fa.avg_complexity / max_complexity * 100, 100.0)
    else:
        complexity_component = 0.0

    # Maintainability component: MI range 0–100, invert so bad MI → high heat
    # MI=0 → heat=100, MI=100 → heat=0
    mi_component = max(0.0, 100.0 - fa.maintainability_index)

    heat = (
        issue_component * 0.60
        + complexity_component * 0.25
        + mi_component * 0.15
    )
    return round(min(heat, 100.0), 2)


def _issue_breakdown_for_file(fa: FileAnalysis) -> dict[str, int]:
    breakdown: dict[str, int] = {}
    for issue in fa.issues:
        breakdown[issue.category] = breakdown.get(issue.category, 0) + 1
    return breakdown


def build_heatmap(
    analysis: AnalysisResult,
    top_n: int | None = None,
) -> list[FileHeatEntry]:
    """Build a ranked heatmap from an AnalysisResult.

    Args:
        analysis: Result from analyzer.analyze_project().
        top_n: If given, return only the top N hottest files.
                If None, return all files.

    Returns:
        List of FileHeatEntry sorted by heat_score descending (hottest first).
    """
    py_files = [fa for fa in analysis.files if not fa.parse_error]

    if not py_files:
        return []

    max_issues = max((len(fa.issues) for fa in py_files), default=0)
    max_complexity = max((fa.avg_complexity for fa in py_files), default=0.0)

    entries: list[FileHeatEntry] = []
    for fa in py_files:
        try:
            rel_path = fa.path.name  # fallback; real rel_path set by analyze_file
        except Exception:
            rel_path = str(fa.path)

        # Use the rel_path from issues if available (issues carry the rel_path string)
        if fa.issues:
            rel_path = fa.issues[0].file
        else:
            # derive from path — best effort
            rel_path = fa.path.name

        heat = _compute_heat(fa, max_issues, max_complexity)
        entries.append(
            FileHeatEntry(
                rel_path=rel_path,
                issue_count=len(fa.issues),
                avg_complexity=fa.avg_complexity,
                maintainability_index=fa.maintainability_index,
                heat_score=heat,
                heat_level=_heat_level(heat),
                issue_breakdown=_issue_breakdown_for_file(fa),
            )
        )

    entries.sort(key=lambda e: e.heat_score, reverse=True)

    if top_n is not None:
        return entries[:top_n]
    return entries
