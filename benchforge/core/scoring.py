"""Scoring engine — converts analysis and benchmark results into quality scores.

All scoring is deterministic and transparent.
Weights and thresholds are documented inline for easy auditing.
User overrides are loaded from .benchforge.toml via BenchForgeConfig.
"""

from __future__ import annotations

from dataclasses import dataclass

from benchforge.core.analyzer import AnalysisResult
from benchforge.core.benchmark import BenchmarkResult
from benchforge.core.config import BenchForgeConfig


@dataclass
class ScoreResult:
    """BenchForge quality scores."""

    performance: int        # 0–100
    maintainability: int    # 0–100
    memory: int             # 0–100
    benchforge_score: int   # 0–100 combined weighted score
    has_benchmark_data: bool = False
    score_notes: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.score_notes is None:
            self.score_notes = []


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _linear_scale(value: float, low: float, high: float, invert: bool = False) -> float:
    """Map value linearly from [low, high] to [0, 100].

    Args:
        invert: If True, lower values score higher (e.g. complexity → score).
    """
    if high == low:
        return 100.0 if not invert else 0.0
    ratio = (value - low) / (high - low)
    ratio = _clamp(ratio, 0.0, 1.0)
    return round((1.0 - ratio if invert else ratio) * 100, 2)


def _score_performance_static(
    analysis: AnalysisResult, cfg: BenchForgeConfig
) -> tuple[float, list[str]]:
    """Derive performance score from static analysis when no benchmark data exists."""
    notes: list[str] = []
    score = 100.0
    p = cfg.penalties
    t = cfg.thresholds

    # Penalize nested loops (strongest performance indicator)
    nested = analysis.issue_breakdown.get("nested_loop", 0)
    if nested:
        penalty = min(nested * p.nested_loop, 40.0)
        score -= penalty
        notes.append(f"Nested loops detected ({nested}): -{penalty:.0f} pts")

    # Penalize high complexity
    high_cc = analysis.issue_breakdown.get("high_complexity", 0)
    if high_cc:
        penalty = min(high_cc * p.high_complexity, 30.0)
        score -= penalty
        notes.append(f"High complexity functions ({high_cc}): -{penalty:.0f} pts")

    # Use avg complexity for fine-grained adjustment
    if analysis.avg_complexity > 0:
        cc_score = _linear_scale(analysis.avg_complexity, t.cc_excellent, t.cc_poor, invert=True)
        # Blend: 60% issue-based, 40% complexity-based
        score = score * 0.6 + cc_score * 0.4

    return _clamp(score), notes


def _score_performance_benchmark(
    benchmark: BenchmarkResult, cfg: BenchForgeConfig
) -> tuple[float, list[str]]:
    """Derive performance score from actual benchmark runtime data."""
    notes: list[str] = []
    t = cfg.thresholds
    successful = [f for f in benchmark.functions if f.error is None]

    if not successful:
        notes.append("No successful benchmark results.")
        return 50.0, notes

    avg_runtime = sum(f.mean_runtime_ms for f in successful) / len(successful)
    score = _linear_scale(avg_runtime, t.runtime_fast_ms, t.runtime_slow_ms, invert=True)
    notes.append(f"Average runtime: {avg_runtime:.2f}ms")
    return score, notes


def _score_maintainability(
    analysis: AnalysisResult, cfg: BenchForgeConfig
) -> tuple[float, list[str]]:
    """Score maintainability based on MI index and issue counts."""
    notes: list[str] = []
    score = 100.0
    p = cfg.penalties
    t = cfg.thresholds

    # MI-based base score
    if analysis.avg_maintainability > 0:
        mi_score = _linear_scale(analysis.avg_maintainability, t.mi_poor, t.mi_excellent)
        score = mi_score

    # Apply issue penalties
    for category, penalty_value in [
        ("long_function", p.long_function),
        ("unused_import", p.unused_import),
        ("duplicate_code", p.duplicate_code),
    ]:
        count = analysis.issue_breakdown.get(category, 0)
        if count:
            penalty = min(count * penalty_value, 25.0)
            score -= penalty
            notes.append(f"{category} issues ({count}): -{penalty:.0f} pts")

    return _clamp(score), notes


def _score_memory(
    analysis: AnalysisResult,
    benchmark: BenchmarkResult | None,
    cfg: BenchForgeConfig,
) -> tuple[float, list[str]]:
    """Score memory efficiency from benchmark data or static proxy."""
    notes: list[str] = []
    t = cfg.thresholds

    if benchmark is not None:
        successful = [f for f in benchmark.functions if f.error is None and f.peak_memory_mb > 0]
        if successful:
            avg_mem = sum(f.peak_memory_mb for f in successful) / len(successful)
            score = _linear_scale(avg_mem, t.memory_small_mb, t.memory_large_mb, invert=True)
            notes.append(f"Average memory delta: {avg_mem:.2f}MB")
            return _clamp(score), notes

    # No benchmark memory data — use static proxy (penalize nested loops as memory risk)
    score = 80.0  # conservative default
    nested = analysis.issue_breakdown.get("nested_loop", 0)
    if nested:
        penalty = min(nested * 5.0, 20.0)
        score -= penalty
        notes.append(f"Static proxy: nested loops suggest memory risk: -{penalty:.0f} pts")
    notes.append("Memory score derived from static analysis (no benchmark data).")

    return _clamp(score), notes


def compute_score(
    analysis: AnalysisResult,
    benchmark: BenchmarkResult | None = None,
    config: BenchForgeConfig | None = None,
) -> ScoreResult:
    """Compute the BenchForge quality score.

    Args:
        analysis: Result from analyzer.analyze_project().
        benchmark: Optional result from benchmark engine. If None, performance
                   and memory scores are derived from static analysis only.
        config: Optional BenchForgeConfig with user-defined weights/penalties/thresholds.
                Falls back to built-in defaults if None.

    Returns:
        ScoreResult with sub-scores and a combined BenchForge score.
    """
    cfg = config if config is not None else BenchForgeConfig()
    has_benchmark = benchmark is not None
    all_notes: list[str] = []

    if cfg.config_path is not None:
        all_notes.append(f"Config loaded from: {cfg.config_path.name}")

    # Performance
    if has_benchmark:
        perf_raw, perf_notes = _score_performance_benchmark(benchmark, cfg)  # type: ignore[arg-type]
    else:
        perf_raw, perf_notes = _score_performance_static(analysis, cfg)
    all_notes.extend(perf_notes)

    # Maintainability
    maint_raw, maint_notes = _score_maintainability(analysis, cfg)
    all_notes.extend(maint_notes)

    # Memory
    mem_raw, mem_notes = _score_memory(analysis, benchmark, cfg)
    all_notes.extend(mem_notes)

    # Combined weighted score using user-defined (or default) weights
    w = cfg.weights
    combined = (
        perf_raw * w.performance
        + maint_raw * w.maintainability
        + mem_raw * w.memory
    )

    return ScoreResult(
        performance=int(round(perf_raw)),
        maintainability=int(round(maint_raw)),
        memory=int(round(mem_raw)),
        benchforge_score=int(round(combined)),
        has_benchmark_data=has_benchmark,
        score_notes=all_notes,
    )
