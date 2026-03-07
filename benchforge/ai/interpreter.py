"""AI interpretation layer — converts deterministic findings into human insights.

Uses Mistral AI API (mistral-small-latest) to explain detected issues and
suggest concrete improvements.

Design rules (from design_rulebook.md):
  - AI NEVER generates analysis results — it only interprets them.
  - AI NEVER overrides deterministic scores.
  - If MISTRAL_API_KEY is not set, the module silently returns None.
  - All input to the API is structured data — no raw user file content is sent.

Usage:
    Set environment variable MISTRAL_API_KEY before running.
    Install: pip install "benchforge[ai]"
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from benchforge.report.html_report import ReportData

MISTRAL_MODEL = "mistral-small-latest"
_MAX_ISSUES_IN_PROMPT = 10   # cap to keep prompt size reasonable


@dataclass
class AIInsight:
    """Structured result from the AI interpretation layer."""

    summary: str              # 2-3 sentence overall assessment
    issue_insights: list[str] # per-issue explanations
    top_suggestion: str       # single most impactful improvement
    model: str                # model used
    available: bool = True    # False if API key missing or call failed


def _is_available() -> bool:
    """Return True if Mistral API key is configured."""
    return bool(os.environ.get("MISTRAL_API_KEY", "").strip())


def _build_prompt(report_data: "ReportData") -> str:
    """Build a concise, structured prompt from deterministic analysis results.

    Only structured metadata is sent — no raw source code from user files.
    """
    score = report_data.score
    issues = report_data.all_issues[:_MAX_ISSUES_IN_PROMPT]
    scan = report_data.scan_summary

    issue_lines = "\n".join(
        f"  - [{i.severity.upper()}] {i.category} in {i.file}"
        f"{f' (line {i.line})' if i.line else ''}: {i.description}"
        for i in issues
    )
    if not issue_lines:
        issue_lines = "  (no issues detected)"

    remaining = len(report_data.all_issues) - len(issues)
    if remaining > 0:
        issue_lines += f"\n  ... and {remaining} more issues"

    prompt = f"""You are a senior software engineer interpreting signals from a static analysis tool.
These are heuristic scores and pattern detections — not a final verdict on code quality.

PROJECT STATS:
- Files: {scan.get('file_count', '?')}
- Primary language: {scan.get('primary_language', 'Unknown')}
- Size: {scan.get('total_size_kb', '?')} KB

BENCHFORGE SCORES (0-100, deterministic):
- Performance: {score.performance}
- Maintainability: {score.maintainability}
- Memory: {score.memory}
- Overall: {score.benchforge_score}
- Based on benchmark data: {score.has_benchmark_data}

DETECTED ISSUES:
{issue_lines}

Your task:
1. Write a 2-3 sentence interpretation of what these signals suggest, not a verdict.
2. For the top 3 most important issues, give a one-line actionable suggestion each.
3. Suggest the single most impactful improvement the developer might consider first.

Rules:
- Be concise and developer-friendly (vibecoder audience).
- Do NOT make definitive quality judgments — frame everything as observations or suggestions, not verdicts.
- Use suggestive language ("consider", "you might", "it could help to") rather than commands.
- Do NOT invent issues not listed above.
- Do NOT comment on style or formatting.
- Output plain text only, no markdown headers or bullet symbols.
- Keep total response under 200 words.

Format your response exactly like this:
SUMMARY: <your 2-3 sentence interpretation>
INSIGHTS:
<issue category>: <one-line suggestion>
<issue category>: <one-line suggestion>
<issue category>: <one-line suggestion>
TOP SUGGESTION: <single most impactful thing to consider, phrased as a suggestion>"""

    return prompt


def _parse_response(text: str) -> tuple[str, list[str], str]:
    """Parse the structured AI response into (summary, insights, top_suggestion)."""
    summary = ""
    insights: list[str] = []
    top_suggestion = ""

    lines = text.strip().splitlines()
    mode = None

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("SUMMARY:"):
            summary = line[len("SUMMARY:"):].strip()
            mode = None
        elif line.startswith("INSIGHTS:"):
            mode = "insights"
        elif line.startswith("TOP SUGGESTION:"):
            top_suggestion = line[len("TOP SUGGESTION:"):].strip()
            mode = None
        elif mode == "insights" and ":" in line:
            insights.append(line)

    # Fallback: if parsing fails, use raw text as summary
    if not summary and text:
        summary = text[:300]

    return summary, insights, top_suggestion


def interpret(report_data: "ReportData") -> AIInsight | None:
    """Interpret analysis results using Mistral AI.

    Returns None if the API key is not configured or the call fails.
    Callers must always handle None gracefully.

    Args:
        report_data: Structured output from the deterministic analysis pipeline.

    Returns:
        AIInsight with human-readable explanations, or None on failure/unavailability.
    """
    if not _is_available():
        return None

    try:
        from mistralai import Mistral  # type: ignore[import]
    except ImportError:
        return None

    api_key = os.environ["MISTRAL_API_KEY"]
    prompt = _build_prompt(report_data)

    try:
        client = Mistral(api_key=api_key)
        response = client.chat.complete(
            model=MISTRAL_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.3,   # low temp = more deterministic, factual output
        )
        raw_text = response.choices[0].message.content or ""
    except Exception as exc:
        # Surface the error type but not internal details in the returned object.
        return AIInsight(
            summary=f"AI interpretation unavailable: {type(exc).__name__}.",
            issue_insights=[],
            top_suggestion="",
            model=MISTRAL_MODEL,
            available=False,
        )

    summary, insights, top_suggestion = _parse_response(raw_text)

    return AIInsight(
        summary=summary,
        issue_insights=insights,
        top_suggestion=top_suggestion,
        model=MISTRAL_MODEL,
        available=True,
    )
