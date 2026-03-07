"""BenchForge CLI — entry point for all user-facing commands.

Commands:
  benchforge analyze <path>   — static analysis + scoring
  benchforge benchmark <path> — runtime benchmarking
  benchforge report <path>    — full pipeline + HTML report

Business logic lives in core modules. This file handles only:
  - argument parsing and validation
  - output formatting (rich)
  - error surfacing
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from benchforge.core.scanner import scan_project, ScanResult
from benchforge.core.analyzer import analyze_project, AnalysisResult
from benchforge.core.scoring import compute_score, ScoreResult

# Force UTF-8 output on Windows to handle non-ASCII characters in rich output.
console = Console(highlight=False)
err_console = Console(stderr=True, style="bold red", highlight=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_path(path_str: str) -> Path:
    """Resolve and validate an input path.

    Raises:
        click.BadParameter: If the path does not exist or is not a directory.
    """
    p = Path(path_str).resolve()
    if not p.exists():
        raise click.BadParameter(f"Path does not exist: {p}", param_hint="PATH")
    if not p.is_dir():
        raise click.BadParameter(f"Path is not a directory: {p}", param_hint="PATH")
    return p


def _score_color(score: int) -> str:
    if score >= 80:
        return "green"
    if score >= 55:
        return "yellow"
    return "red"


def _print_scan_summary(scan: ScanResult) -> None:
    table = Table(title="Project Summary", box=box.ROUNDED, show_header=False)
    table.add_column("Key", style="dim")
    table.add_column("Value", style="bold white")
    table.add_row("Root", str(scan.root))
    table.add_row("Files", str(scan.file_count))
    table.add_row("Primary Language", scan.primary_language or "Unknown")
    table.add_row("Total Size", f"{scan.total_size_kb} KB")
    table.add_row("Python Packages", str(len(scan.modules)))
    if scan.languages:
        lang_str = ", ".join(f"{lang}: {count}" for lang, count in sorted(scan.languages.items()))
        table.add_row("Languages", lang_str)
    console.print(table)


def _print_scores(score: ScoreResult) -> None:
    table = Table(title="BenchForge Scores", box=box.ROUNDED)
    table.add_column("Category", style="dim")
    table.add_column("Score", justify="center")

    for label, value in [
        ("Performance", score.performance),
        ("Maintainability", score.maintainability),
        ("Memory", score.memory),
    ]:
        color = _score_color(value)
        table.add_row(label, f"[{color}]{value}[/{color}]")

    console.print(table)

    color = _score_color(score.benchforge_score)
    console.print(
        Panel(
            f"[{color}]{score.benchforge_score}[/{color}] / 100",
            title="[bold]BenchForge Score[/bold]",
            expand=False,
        )
    )

    if not score.has_benchmark_data:
        console.print(
            "[dim]Tip: Run [bold]benchforge benchmark .[/bold] for measurement-based scores.[/dim]"
        )


def _print_issues(analysis: AnalysisResult) -> None:
    all_issues = [issue for fa in analysis.files for issue in fa.issues]

    if not all_issues:
        console.print("[green]No issues detected.[/green]")
        return

    table = Table(title=f"Detected Issues ({len(all_issues)})", box=box.ROUNDED)
    table.add_column("Severity", width=8)
    table.add_column("Category")
    table.add_column("File")
    table.add_column("Line", justify="right", width=6)
    table.add_column("Description")

    severity_colors = {"error": "red", "warning": "yellow", "info": "blue"}

    for issue in sorted(all_issues, key=lambda i: (i.file, i.line or 0)):
        color = severity_colors.get(issue.severity, "white")
        table.add_row(
            f"[{color}]{issue.severity}[/{color}]",
            issue.category,
            issue.file,
            str(issue.line) if issue.line else "—",
            issue.description,
        )

    console.print(table)


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(package_name="benchforge")
def cli() -> None:
    """BenchForge — code quality analysis for the AI coding era."""


# ---------------------------------------------------------------------------
# analyze command
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("path", default=".", metavar="PATH")
def analyze(path: str) -> None:
    """Analyze a project directory for code quality issues.

    PATH defaults to the current directory.
    """
    try:
        project_path = _resolve_path(path)
    except click.BadParameter as exc:
        err_console.print(f"Error: {exc}")
        sys.exit(1)

    console.print(f"\n[bold]BenchForge[/bold] — analyzing [cyan]{project_path}[/cyan]\n")

    # Scanner
    try:
        scan = scan_project(project_path)
    except NotADirectoryError as exc:
        err_console.print(f"Error: {exc}")
        sys.exit(1)

    if scan.file_count == 0:
        console.print("[yellow]No files found in the given directory.[/yellow]")
        sys.exit(0)

    _print_scan_summary(scan)

    # Analyzer
    analysis = analyze_project(scan)

    _print_issues(analysis)

    # Scoring
    score = compute_score(analysis)
    _print_scores(score)


# ---------------------------------------------------------------------------
# benchmark command
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("path", default=".", metavar="PATH")
@click.option("--runs", default=5, show_default=True, help="Number of timing repetitions.")
@click.option(
    "--file",
    "target_file",
    default=None,
    help="Benchmark a specific Python file instead of the whole project.",
)
def benchmark(path: str, runs: int, target_file: str | None) -> None:
    """Benchmark Python functions in a project directory.

    PATH defaults to the current directory.
    """
    from benchforge.core.benchmark import benchmark_file, BenchmarkResult
    from rich.table import Table

    try:
        project_path = _resolve_path(path)
    except click.BadParameter as exc:
        err_console.print(f"Error: {exc}")
        sys.exit(1)

    console.print(f"\n[bold]BenchForge[/bold] — benchmarking [cyan]{project_path}[/cyan]\n")

    if target_file:
        target = Path(target_file).resolve()
        if not target.exists():
            err_console.print(f"Error: File not found: {target}")
            sys.exit(1)
        py_files = [target]
    else:
        try:
            scan = scan_project(project_path)
        except NotADirectoryError as exc:
            err_console.print(f"Error: {exc}")
            sys.exit(1)
        py_files = [f for f in scan.files if f.suffix.lower() == ".py"]

    if not py_files:
        console.print("[yellow]No Python files found to benchmark.[/yellow]")
        sys.exit(0)

    all_results: list = []
    all_errors: list[str] = []

    for py_file in py_files:
        result: BenchmarkResult = benchmark_file(py_file, runs=runs)
        all_results.extend(result.functions)
        all_errors.extend(result.errors)

    if all_errors:
        for err in all_errors:
            console.print(f"[yellow]Warning:[/yellow] {err}")

    if not all_results:
        console.print(
            "[yellow]No zero-argument functions found to benchmark automatically.[/yellow]\n"
            "Provide explicit callables via the Python API: benchmark_callables([(func, args, kwargs)])."
        )
        sys.exit(0)

    table = Table(title="Benchmark Results", box=box.ROUNDED)
    table.add_column("Function")
    table.add_column("Mean (ms)", justify="right")
    table.add_column("Min (ms)", justify="right")
    table.add_column("Max (ms)", justify="right")
    table.add_column("Mem ΔMB", justify="right")
    table.add_column("Runs", justify="right")

    for fn in all_results:
        status = "[red]Error[/red]" if fn.error else fn.name
        table.add_row(
            status,
            f"{fn.mean_runtime_ms:.3f}",
            f"{fn.min_runtime_ms:.3f}",
            f"{fn.max_runtime_ms:.3f}",
            f"{fn.peak_memory_mb:.3f}",
            str(fn.runs),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# report command
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("path", default=".", metavar="PATH")
@click.option(
    "--output",
    "-o",
    default="benchforge_report.html",
    show_default=True,
    help="Output HTML file path.",
)
def report(path: str, output: str) -> None:
    """Run full analysis and generate an HTML report.

    PATH defaults to the current directory.
    """
    from benchforge.report.html_report import build_report_data, generate_html_report

    try:
        project_path = _resolve_path(path)
    except click.BadParameter as exc:
        err_console.print(f"Error: {exc}")
        sys.exit(1)

    console.print(f"\n[bold]BenchForge[/bold] — generating report for [cyan]{project_path}[/cyan]\n")

    # Pipeline
    try:
        scan = scan_project(project_path)
    except NotADirectoryError as exc:
        err_console.print(f"Error: {exc}")
        sys.exit(1)

    if scan.file_count == 0:
        console.print("[yellow]No files found — report would be empty.[/yellow]")
        sys.exit(0)

    analysis = analyze_project(scan)
    score = compute_score(analysis)

    scan_summary = {
        "file_count": scan.file_count,
        "primary_language": scan.primary_language,
        "total_size_kb": scan.total_size_kb,
        "modules": scan.modules,
        "languages": scan.languages,
    }

    report_data = build_report_data(
        project_path=project_path,
        scan_summary=scan_summary,
        analysis=analysis,
        score=score,
    )

    output_path = Path(output).resolve()

    try:
        written = generate_html_report(report_data, output_path)
    except OSError as exc:
        err_console.print(f"Error writing report: {exc}")
        sys.exit(1)

    console.print(f"[green]Report generated:[/green] {written}")

    # Quick summary in terminal too
    _print_scores(score)
