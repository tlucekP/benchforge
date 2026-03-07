"""Roast engine — generates fun but honest code quality insights.

All roast lines are deterministic (template-based).
No AI required. Optional --ai flag in CLI can enrich roasts via Mistral.

Business logic only — no CLI or output formatting here.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from benchforge.core.analyzer import AnalysisResult
from benchforge.core.heatmap import build_heatmap
from benchforge.core.scoring import ScoreResult


# ---------------------------------------------------------------------------
# Roast templates
# Each entry: (min_count, message_template)
# Use {n} for the issue count, {file} for the hottest file name.
# ---------------------------------------------------------------------------

_ROASTS_NESTED_LOOP: list[tuple[int, str]] = [
    (1,  "Found a nested loop. O(n²) called — it wants its complexity back."),
    (3,  "{n} nested loops detected. Your CPU is already writing its resignation letter."),
    (5,  "{n} nested loops. Are you trying to heat your room with this code?"),
    (10, "{n} nested loops. Congratulations — you've reinvented the heat death of the universe."),
]

_ROASTS_LONG_FUNCTION: list[tuple[int, str]] = [
    (1,  "A function longer than 50 lines. Some call it a function. We call it a novel."),
    (3,  "{n} long functions detected. The Single Responsibility Principle left the chat."),
    (5,  "{n} functions that could double as bedtime stories. Sweet dreams, reviewer."),
    (10, "{n} long functions. Ever heard of the word 'refactor'? Asking for a friend."),
]

_ROASTS_UNUSED_IMPORT: list[tuple[int, str]] = [
    (1,  "Unused import found. You invited it to the party but it just stood in the corner."),
    (5,  "{n} unused imports. Your import section is a graveyard of good intentions."),
    (15, "{n} unused imports. Are you importing the entire Python standard library just in case?"),
    (30, "{n} unused imports. At this point just `import universe` and call it a day."),
]

_ROASTS_HIGH_COMPLEXITY: list[tuple[int, str]] = [
    (1,  "High cyclomatic complexity detected. Spaghetti tastes better than it reads."),
    (3,  "{n} high-complexity functions. The control flow graph needs its own legend."),
    (5,  "{n} functions with high complexity. Even the code doesn't know what it does."),
    (10, "{n} complex functions. Future you is already afraid."),
]

_ROASTS_DUPLICATE_CODE: list[tuple[int, str]] = [
    (1,  "Duplicate code found. Copy-paste is not a design pattern."),
    (3,  "{n} duplicated functions. DRY stands for Don't Repeat Yourself, not Do Repeat Yourself."),
    (5,  "{n} copy-pasted blocks. If you need it twice, abstract it. If you need it three times, you should be embarrassed."),
    (10, "{n} duplicate functions. Your codebase has more copies than a Xerox machine."),
]

_ROASTS_SCORE: list[tuple[int, str]] = [
    (0,  "BenchForge Score: {score}/100. The code has... potential. Theoretical potential."),
    (20, "BenchForge Score: {score}/100. It compiles. That's something."),
    (40, "BenchForge Score: {score}/100. Decent effort. The bar was on the floor and you cleared it."),
    (60, "BenchForge Score: {score}/100. Not bad! There's hope for you yet."),
    (80, "BenchForge Score: {score}/100. Solid work. The reviewer might even smile."),
    (95, "BenchForge Score: {score}/100. This is clean code. Are you even human?"),
]

_ROASTS_CLEAN: list[str] = [
    "No issues detected. Suspicious. Nobody writes perfect code on the first try.",
    "Zero issues found. Either this code is excellent or BenchForge needs better detectors.",
    "Clean as a whistle. We're watching you.",
]

_CATEGORY_MAP = {
    "nested_loop":    _ROASTS_NESTED_LOOP,
    "long_function":  _ROASTS_LONG_FUNCTION,
    "unused_import":  _ROASTS_UNUSED_IMPORT,
    "high_complexity": _ROASTS_HIGH_COMPLEXITY,
    "duplicate_code": _ROASTS_DUPLICATE_CODE,
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RoastLine:
    """A single roast line tied to an issue category."""

    category: str       # e.g. "nested_loop", "score", "clean"
    message: str
    severity: str = "roast"   # always "roast" — no semantic meaning


@dataclass
class RoastResult:
    """Full roast output for a project."""

    lines: list[RoastLine] = field(default_factory=list)
    hottest_file: str = ""      # rel_path of the most problematic file
    score: int = 0
    total_issues: int = 0
    is_clean: bool = False


# ---------------------------------------------------------------------------
# Roast logic
# ---------------------------------------------------------------------------

def _pick_roast(templates: list[tuple[int, str]], count: int, **kwargs: object) -> str:
    """Pick the highest-threshold template that still applies, then format it."""
    chosen = templates[0][1]   # fallback: first entry
    for threshold, template in templates:
        if count >= threshold:
            chosen = template
    return chosen.format(n=count, **kwargs)


def roast_project(
    analysis: AnalysisResult,
    score: ScoreResult,
    seed: int | None = None,
) -> RoastResult:
    """Generate a deterministic roast for the given analysis results.

    Args:
        analysis: Result from analyzer.analyze_project().
        score: Result from scoring.compute_score().
        seed: Optional random seed for reproducible selection when multiple
              templates match the same threshold. Defaults to None (random).

    Returns:
        RoastResult with all roast lines.
    """
    rng = random.Random(seed)
    lines: list[RoastLine] = []
    breakdown = analysis.issue_breakdown

    # --- Per-category roasts ---
    for category, templates in _CATEGORY_MAP.items():
        count = breakdown.get(category, 0)
        if count == 0:
            continue
        msg = _pick_roast(templates, count)
        lines.append(RoastLine(category=category, message=msg))

    # --- Score roast ---
    s = score.benchforge_score
    score_roast = _ROASTS_SCORE[0][1]
    for threshold, template in _ROASTS_SCORE:
        if s >= threshold:
            score_roast = template
    lines.append(RoastLine(category="score", message=score_roast.format(score=s)))

    # --- Hottest file ---
    heatmap = build_heatmap(analysis, top_n=1)
    hottest_file = heatmap[0].rel_path if heatmap else ""

    # --- Clean project ---
    is_clean = analysis.total_issues == 0
    if is_clean:
        msg = rng.choice(_ROASTS_CLEAN)
        lines.append(RoastLine(category="clean", message=msg))

    return RoastResult(
        lines=lines,
        hottest_file=hottest_file,
        score=s,
        total_issues=analysis.total_issues,
        is_clean=is_clean,
    )
