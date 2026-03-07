"""HTML report generator using Jinja2 with autoescaping enabled.

Security: autoescape=True ensures all dynamic content is HTML-escaped,
preventing XSS from malicious file names, function names, or issue descriptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from benchforge.core.analyzer import AnalysisResult, Issue
from benchforge.core.benchmark import BenchmarkResult
from benchforge.core.scoring import ScoreResult


@dataclass
class ReportData:
    """Aggregated data passed to the HTML report template."""

    project_path: str
    scan_summary: dict[str, object]          # file count, size, languages, modules
    analysis: AnalysisResult
    score: ScoreResult
    benchmark: BenchmarkResult | None = None
    all_issues: list[Issue] = field(default_factory=list)
    ai_insight: object | None = None         # AIInsight | None (optional import)


def _build_jinja_env() -> Environment:
    """Create a Jinja2 environment with autoescaping enabled for HTML."""
    return Environment(
        loader=PackageLoader("benchforge", "report/templates"),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _collect_issues(analysis: AnalysisResult) -> list[Issue]:
    """Flatten all per-file issues into a single sorted list."""
    issues: list[Issue] = []
    for file_analysis in analysis.files:
        issues.extend(file_analysis.issues)
    # Sort by file then line number for consistent output
    return sorted(issues, key=lambda i: (i.file, i.line or 0))


def generate_html_report(
    report_data: ReportData,
    output_path: Path,
) -> Path:
    """Render the HTML report and write it to output_path.

    Args:
        report_data: All data needed by the template.
        output_path: Destination file path (e.g. ./benchforge_report.html).

    Returns:
        The resolved output path.

    Raises:
        OSError: If the output file cannot be written.
    """
    env = _build_jinja_env()
    template = env.get_template("report.html.j2")

    rendered = template.render(
        project_path=report_data.project_path,
        scan=report_data.scan_summary,
        score=report_data.score,
        issues=report_data.all_issues,
        benchmark=report_data.benchmark,
        file_analyses=report_data.analysis.files,
        issue_breakdown=report_data.analysis.issue_breakdown,
        ai_insight=report_data.ai_insight,
    )

    resolved = output_path.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(rendered, encoding="utf-8")

    return resolved


def build_report_data(
    project_path: Path,
    scan_summary: dict[str, object],
    analysis: AnalysisResult,
    score: ScoreResult,
    benchmark: BenchmarkResult | None = None,
) -> ReportData:
    """Construct a ReportData object from pipeline outputs.

    Args:
        project_path: Root path that was analyzed.
        scan_summary: Dict from scanner output.
        analysis: Static analysis result.
        score: Computed quality scores.
        benchmark: Optional benchmark result.

    Returns:
        ReportData ready for generate_html_report().
    """
    return ReportData(
        project_path=str(project_path),
        scan_summary=scan_summary,
        analysis=analysis,
        score=score,
        benchmark=benchmark,
        all_issues=_collect_issues(analysis),
    )
