"""Optional AI interpretation layer — stub implementation for MVP.

This module is intentionally a no-op in v0.1.0.

Design intent:
  - AI must NEVER generate or fabricate analysis results.
  - AI may only interpret structured findings produced by the deterministic layer.
  - This module receives a ReportData object and returns a human-readable explanation.

Phase 2 integration plan:
  - Use the Anthropic Claude API to interpret ScoreResult and AnalysisResult.
  - Wrap in a feature flag so it remains optional (no API key = silent skip).
  - See docs/roadmap.md for timeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from benchforge.report.html_report import ReportData


def interpret(report_data: "ReportData") -> str | None:
    """Interpret analysis results and produce a human-readable explanation.

    In MVP this is a no-op stub. It returns None to signal that no AI
    interpretation is available. Callers must handle None gracefully.

    Args:
        report_data: The structured analysis output.

    Returns:
        A plain-text explanation string, or None if interpretation is unavailable.
    """
    # Stub: Phase 2 will call the Claude API here.
    return None
