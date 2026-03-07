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

import io
import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich import box

from benchforge.core.scanner import scan_project, ScanResult
from benchforge.core.analyzer import analyze_project, AnalysisResult
from benchforge.core.scoring import compute_score, ScoreResult
from benchforge.core.config import load_config, BenchForgeConfig

# Ensure UTF-8 output on Windows (cp1250 console cannot render many chars).
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

console = Console(highlight=False)
err_console = Console(stderr=True, style="bold red", highlight=False)


# ---------------------------------------------------------------------------
# JSON serialization helpers
# ---------------------------------------------------------------------------

def _scan_to_dict(scan: "ScanResult") -> dict:
    return {
        "root": str(scan.root),
        "file_count": scan.file_count,
        "primary_language": scan.primary_language,
        "total_size_kb": scan.total_size_kb,
        "modules": scan.modules,
        "languages": scan.languages,
    }


def _analysis_to_dict(analysis: "AnalysisResult") -> dict:
    issues = []
    for fa in analysis.files:
        for issue in fa.issues:
            issues.append({
                "category": issue.category,
                "severity": issue.severity,
                "file": issue.file,
                "line": issue.line,
                "description": issue.description,
            })
    return {
        "total_issues": analysis.total_issues,
        "issue_breakdown": analysis.issue_breakdown,
        "avg_complexity": analysis.avg_complexity,
        "avg_maintainability": analysis.avg_maintainability,
        "issues": issues,
    }


def _score_to_dict(score: "ScoreResult") -> dict:
    return {
        "performance": score.performance,
        "maintainability": score.maintainability,
        "memory": score.memory,
        "benchforge_score": score.benchforge_score,
        "has_benchmark_data": score.has_benchmark_data,
        "score_notes": score.score_notes,
    }


def _print_json_output(scan: "ScanResult", analysis: "AnalysisResult", score: "ScoreResult") -> None:
    """Emit analysis results as a single JSON object to stdout."""
    payload = {
        "scan": _scan_to_dict(scan),
        "analysis": _analysis_to_dict(analysis),
        "score": _score_to_dict(score),
    }
    click.echo(json.dumps(payload, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _load_project_config(project_path: Path) -> BenchForgeConfig:
    """Load .benchforge.toml from project_path. Returns defaults on error."""
    try:
        return load_config(project_path)
    except ValueError as exc:
        err_console.print(f"[yellow]Config warning:[/yellow] {exc} — using defaults.")
        from benchforge.core.config import BenchForgeConfig as _Cfg
        return _Cfg()


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

def _heat_color(level: str) -> str:
    return {"critical": "red", "high": "yellow", "medium": "cyan", "low": "green"}.get(level, "white")


def _print_heatmap(analysis: "AnalysisResult", top_n: int = 10) -> None:
    """Print a file heatmap table ranked by heat score."""
    from benchforge.core.heatmap import build_heatmap

    entries = build_heatmap(analysis, top_n=top_n)
    if not entries:
        console.print("[dim]No files to display in heatmap.[/dim]")
        return

    table = Table(title=f"File Heatmap (top {min(top_n, len(entries))})", box=box.ROUNDED)
    table.add_column("Heat", width=10, justify="center")
    table.add_column("File")
    table.add_column("Issues", justify="right", width=7)
    table.add_column("Complexity", justify="right", width=10)
    table.add_column("MI", justify="right", width=7)
    table.add_column("Top Issues", style="dim")

    for entry in entries:
        color = _heat_color(entry.heat_level)
        heat_cell = f"[{color}]{entry.heat_score:.0f}  {entry.heat_level.upper()}[/{color}]"
        top_cats = sorted(entry.issue_breakdown.items(), key=lambda x: -x[1])[:2]
        top_str = ", ".join(f"{cat}:{n}" for cat, n in top_cats) if top_cats else "—"
        table.add_row(
            heat_cell,
            entry.rel_path,
            str(entry.issue_count),
            str(entry.avg_complexity),
            str(round(entry.maintainability_index, 1)),
            top_str,
        )

    console.print(table)


def _print_ai_insight(insight: object) -> None:
    """Print AI insight panel to the terminal if available."""
    from benchforge.ai.interpreter import AIInsight
    if not isinstance(insight, AIInsight):
        return
    if not insight.available:
        console.print(f"[dim]AI: {insight.summary}[/dim]")
        return
    lines = []
    if insight.summary:
        lines.append(insight.summary)
    if insight.issue_insights:
        lines.append("")
        for item in insight.issue_insights:
            lines.append(f"  -> {item}")
    if insight.top_suggestion:
        lines.append("")
        lines.append(f"[bold]Top suggestion:[/bold] {insight.top_suggestion}")
    lines.append(f"\n[dim]Model: {insight.model}[/dim]")
    console.print(
        Panel(
            "\n".join(lines),
            title="[bold cyan]AI Insight[/bold cyan] [dim](Mistral AI)[/dim]",
            border_style="cyan",
            expand=False,
        )
    )


@cli.command()
@click.argument("path", default=".", metavar="PATH")
@click.option("--ai", "use_ai", is_flag=True, default=False,
              help="Run AI interpretation (requires MISTRAL_API_KEY).")
@click.option(
    "--format", "output_format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format: text (default) or json.",
)
@click.option(
    "--heatmap", "show_heatmap", is_flag=True, default=False,
    help="Show file heatmap ranked by issues and complexity.",
)
@click.option(
    "--top", "heatmap_top", default=10, show_default=True,
    help="Number of files to show in heatmap (used with --heatmap).",
)
def analyze(path: str, use_ai: bool, output_format: str, show_heatmap: bool, heatmap_top: int) -> None:
    """Analyze a project directory for code quality issues.

    PATH defaults to the current directory.
    """
    try:
        project_path = _resolve_path(path)
    except click.BadParameter as exc:
        err_console.print(f"Error: {exc}")
        sys.exit(1)

    if output_format == "text":
        console.print(f"\n[bold]BenchForge[/bold] — analyzing [cyan]{project_path}[/cyan]\n")

    cfg = _load_project_config(project_path)

    if output_format == "json":
        # JSON mode: run pipeline silently, no progress output
        try:
            scan = scan_project(project_path)
        except NotADirectoryError as exc:
            err_console.print(f"Error: {exc}")
            sys.exit(1)
        if scan.file_count == 0:
            click.echo(json.dumps({"error": "No files found in the given directory."}, indent=2))
            sys.exit(0)
        analysis = analyze_project(scan)
        score = compute_score(analysis, config=cfg)
        _print_json_output(scan, analysis, score)
        return

    # --- text mode: show progress spinner ---
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Scanning project...", total=None)

        try:
            scan = scan_project(project_path)
        except NotADirectoryError as exc:
            err_console.print(f"Error: {exc}")
            sys.exit(1)

        if scan.file_count == 0:
            console.print("[yellow]No files found in the given directory.[/yellow]")
            sys.exit(0)

        progress.update(task, description=f"Analyzing {scan.file_count} files...")
        analysis = analyze_project(scan)

        progress.update(task, description="Computing scores...")
        score = compute_score(analysis, config=cfg)

    if cfg.config_path is not None:
        console.print(f"[dim]Config: {cfg.config_path}[/dim]\n")

    _print_scan_summary(scan)
    _print_issues(analysis)
    _print_scores(score)

    if show_heatmap:
        _print_heatmap(analysis, top_n=heatmap_top)

    # Optional AI interpretation
    if use_ai:
        from benchforge.ai.interpreter import interpret, _is_available
        from benchforge.report.html_report import build_report_data
        if not _is_available():
            console.print("[yellow]AI: MISTRAL_API_KEY not set — skipping AI insight.[/yellow]")
        else:
            console.print("[dim]Requesting AI insight...[/dim]")
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
            insight = interpret(report_data)
            if insight:
                _print_ai_insight(insight)


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
    "--output", "-o",
    default="benchforge_report.html",
    show_default=True,
    help="Output HTML file path.",
)
@click.option("--ai", "use_ai", is_flag=True, default=False,
              help="Include AI interpretation in report (requires MISTRAL_API_KEY).")
def report(path: str, output: str, use_ai: bool) -> None:
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

    cfg = _load_project_config(project_path)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Scanning project...", total=None)

        try:
            scan = scan_project(project_path)
        except NotADirectoryError as exc:
            err_console.print(f"Error: {exc}")
            sys.exit(1)

        if scan.file_count == 0:
            console.print("[yellow]No files found — report would be empty.[/yellow]")
            sys.exit(0)

        progress.update(task, description=f"Analyzing {scan.file_count} files...")
        analysis = analyze_project(scan)

        progress.update(task, description="Computing scores...")
        score = compute_score(analysis, config=cfg)

        progress.update(task, description="Building report data...")
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

        # Optional AI interpretation
        if use_ai:
            from benchforge.ai.interpreter import interpret, _is_available
            if not _is_available():
                progress.stop()
                console.print("[yellow]AI: MISTRAL_API_KEY not set — report will not include AI insight.[/yellow]")
            else:
                progress.update(task, description="Requesting AI insight...")
                insight = interpret(report_data)
                if insight:
                    report_data.ai_insight = insight

    output_path = Path(output).resolve()

    try:
        written = generate_html_report(report_data, output_path)
    except OSError as exc:
        err_console.print(f"Error writing report: {exc}")
        sys.exit(1)

    console.print(f"[green]Report generated:[/green] {written}")

    # Quick summary in terminal too
    _print_scores(score)


# ---------------------------------------------------------------------------
# roast command
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("path", default=".", metavar="PATH")
@click.option("--ai", "use_ai", is_flag=True, default=False,
              help="Enrich roast with AI commentary (requires MISTRAL_API_KEY).")
@click.option("--seed", default=None, type=int,
              help="Random seed for reproducible roast output.")
def roast(path: str, use_ai: bool, seed: int | None) -> None:
    """Roast your code — fun but honest quality insights.

    PATH defaults to the current directory.
    """
    from benchforge.core.roast import roast_project, RoastResult

    try:
        project_path = _resolve_path(path)
    except click.BadParameter as exc:
        err_console.print(f"Error: {exc}")
        sys.exit(1)

    console.print(f"\n[bold]BenchForge Roast[/bold] — [cyan]{project_path}[/cyan]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Scanning project...", total=None)

        try:
            scan = scan_project(project_path)
        except NotADirectoryError as exc:
            err_console.print(f"Error: {exc}")
            sys.exit(1)

        if scan.file_count == 0:
            console.print("[yellow]No files found — nothing to roast.[/yellow]")
            sys.exit(0)

        progress.update(task, description=f"Analyzing {scan.file_count} files...")
        analysis = analyze_project(scan)

        progress.update(task, description="Computing scores...")
        cfg = _load_project_config(project_path)
        score = compute_score(analysis, config=cfg)

        progress.update(task, description="Preparing roast...")
        result: RoastResult = roast_project(analysis, score, seed=seed)

    _print_roast(result)

    # Optional AI enrichment
    if use_ai:
        from benchforge.ai.interpreter import interpret, _is_available
        from benchforge.report.html_report import build_report_data
        if not _is_available():
            console.print("[yellow]AI: MISTRAL_API_KEY not set — skipping AI roast.[/yellow]")
        else:
            console.print("\n[dim]Requesting AI commentary...[/dim]")
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
            insight = interpret(report_data)
            if insight:
                _print_ai_insight(insight)


def _print_roast(result: "RoastResult") -> None:
    """Render the roast output to the terminal."""
    from benchforge.core.roast import RoastResult
    assert isinstance(result, RoastResult)

    category_icons = {
        "nested_loop":     "🔁",
        "long_function":   "📜",
        "unused_import":   "👻",
        "high_complexity": "🌀",
        "duplicate_code":  "📋",
        "score":           "🎯",
        "clean":           "✨",
    }

    lines_to_print = [line for line in result.lines if line.category != "score"]
    score_lines = [line for line in result.lines if line.category == "score"]

    if result.is_clean:
        console.print(
            Panel(
                "[green]No issues detected.[/green]\n\n"
                + (result.lines[-1].message if result.lines else ""),
                title="[bold yellow]BenchForge Roast[/bold yellow]",
                border_style="yellow",
                expand=False,
            )
        )
        return

    # Issue roasts
    roast_text_lines = []
    for line in lines_to_print:
        icon = category_icons.get(line.category, "•")
        roast_text_lines.append(f"{icon}  {line.message}")

    if result.hottest_file:
        roast_text_lines.append(f"\n[dim]Hottest file: [bold]{result.hottest_file}[/bold][/dim]")

    console.print(
        Panel(
            "\n".join(roast_text_lines),
            title="[bold yellow]BenchForge Roast[/bold yellow]",
            border_style="yellow",
            expand=False,
        )
    )

    # Score verdict
    if score_lines:
        s = result.score
        color = _score_color(s)
        console.print(
            Panel(
                f"[{color}]{score_lines[0].message}[/{color}]",
                title="[bold]Verdict[/bold]",
                border_style=color,
                expand=False,
            )
        )


# ---------------------------------------------------------------------------
# challenge command
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("paths", nargs=-1, required=True, metavar="PATH...")
@click.option(
    "--labels", default=None,
    help="Comma-separated display labels matching each PATH (e.g. 'human,gpt4,claude').",
)
@click.option(
    "--format", "output_format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format: text (default) or json.",
)
def challenge(paths: tuple[str, ...], labels: str | None, output_format: str) -> None:
    """Compare multiple implementations and produce a ranked leaderboard.

    Provide 2 or more PATH arguments:

        benchforge challenge human/ gpt4/ claude/

    Use --labels for custom display names:

        benchforge challenge human/ gpt4/ --labels "Human,GPT-4"
    """
    from benchforge.core.challenge import run_challenge, ChallengeResult

    if len(paths) < 2:
        err_console.print("Error: challenge requires at least 2 paths.")
        sys.exit(1)

    resolved: list[Path] = []
    for p in paths:
        try:
            resolved.append(_resolve_path(p))
        except click.BadParameter as exc:
            err_console.print(f"Error: {exc}")
            sys.exit(1)

    label_list: list[str] | None = None
    if labels:
        label_list = [l.strip() for l in labels.split(",")]

    if output_format == "text":
        label_str = " vs ".join(
            label_list[i] if label_list and i < len(label_list) else resolved[i].name
            for i in range(len(resolved))
        )
        console.print(f"\n[bold]BenchForge Challenge[/bold] — {label_str}\n")

    cfg = _load_project_config(resolved[0])

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
        disable=(output_format == "json"),
    ) as progress:
        task = progress.add_task(f"Analyzing {len(resolved)} implementations...", total=None)
        try:
            result: ChallengeResult = run_challenge(resolved, labels=label_list, config=cfg)
        except (ValueError, NotADirectoryError) as exc:
            err_console.print(f"Error: {exc}")
            sys.exit(1)
        progress.update(task, description="Done.")

    if output_format == "json":
        def _snap_to_dict(snap: object) -> dict:
            from benchforge.core.comparator import ProjectSnapshot
            assert isinstance(snap, ProjectSnapshot)
            return {
                "label": snap.label,
                "path": str(snap.path),
                "scan": _scan_to_dict(snap.scan),
                "analysis": _analysis_to_dict(snap.analysis),
                "score": _score_to_dict(snap.score),
            }
        payload = {
            "entries": [
                {"rank": e.rank, "snapshot": _snap_to_dict(e.snapshot)}
                for e in result.entries
            ],
            "winner": result.winner.label if result.winner else None,
            "is_tie": result.is_tie,
            "category_rankings": [
                {
                    "category": cr.category,
                    "ranked": cr.ranked_labels,
                    "scores": cr.scores,
                }
                for cr in result.category_rankings
            ],
        }
        click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    _print_challenge(result)


def _print_challenge(result: "ChallengeResult") -> None:
    """Render the challenge leaderboard to the terminal."""
    from benchforge.core.challenge import ChallengeResult
    assert isinstance(result, ChallengeResult)

    # --- Leaderboard table ---
    table = Table(title="Challenge Leaderboard", box=box.ROUNDED, show_lines=True)
    table.add_column("Rank", width=6, justify="center")
    table.add_column("Implementation")
    table.add_column("Score", justify="center", width=7)
    table.add_column("Performance", justify="center", width=12)
    table.add_column("Maintainability", justify="center", width=15)
    table.add_column("Memory", justify="center", width=8)
    table.add_column("Issues", justify="right", width=7)
    table.add_column("Complexity", justify="right", width=10)

    rank_styles = {1: "bold gold1", 2: "bold silver", 3: "bold orange3"}

    for entry in result.entries:
        snap = entry.snapshot
        rank_style = rank_styles.get(entry.rank, "dim")
        rank_cell = f"[{rank_style}]#{entry.rank}[/{rank_style}]"

        sc = snap.score
        bc = _score_color(sc.benchforge_score)
        score_cell = f"[bold {bc}]{sc.benchforge_score}[/bold {bc}]"

        table.add_row(
            rank_cell,
            snap.label,
            score_cell,
            f"[{_score_color(sc.performance)}]{sc.performance}[/{_score_color(sc.performance)}]",
            f"[{_score_color(sc.maintainability)}]{sc.maintainability}[/{_score_color(sc.maintainability)}]",
            f"[{_score_color(sc.memory)}]{sc.memory}[/{_score_color(sc.memory)}]",
            str(snap.analysis.total_issues),
            str(snap.analysis.avg_complexity),
        )

    console.print(table)

    # --- Category rankings ---
    cat_table = Table(title="Category Rankings (best -> worst)", box=box.ROUNDED)
    cat_table.add_column("Category", style="dim")
    cat_table.add_column("Ranking")

    for cr in result.category_rankings:
        ranked_str = " > ".join(cr.ranked_labels)
        cat_table.add_row(cr.category, ranked_str)

    console.print(cat_table)

    # --- Winner banner ---
    if result.is_tie:
        console.print(
            Panel(
                "[yellow]It's a tie![/yellow] Multiple implementations share the top score.",
                title="[bold]Result[/bold]",
                border_style="yellow",
                expand=False,
            )
        )
    elif result.winner:
        w = result.winner
        top_score = w.score.benchforge_score
        color = _score_color(top_score)
        console.print(
            Panel(
                f"[bold {color}]{w.label}[/bold {color}] wins with score "
                f"[bold {color}]{top_score}[/bold {color}]/100",
                title="[bold]Winner[/bold]",
                border_style=color,
                expand=False,
            )
        )


# ---------------------------------------------------------------------------
# compare command
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("path_a", metavar="PATH_A")
@click.argument("path_b", metavar="PATH_B")
@click.option("--label-a", default=None, help="Display label for PATH_A (default: directory name).")
@click.option("--label-b", default=None, help="Display label for PATH_B (default: directory name).")
@click.option(
    "--format", "output_format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format: text (default) or json.",
)
def compare(
    path_a: str,
    path_b: str,
    label_a: str | None,
    label_b: str | None,
    output_format: str,
) -> None:
    """Compare two project directories side-by-side.

    PATH_A is typically the human implementation,
    PATH_B is typically the AI-generated implementation.
    """
    from benchforge.core.comparator import compare_projects

    try:
        proj_a = _resolve_path(path_a)
        proj_b = _resolve_path(path_b)
    except click.BadParameter as exc:
        err_console.print(f"Error: {exc}")
        sys.exit(1)

    if output_format == "text":
        console.print(
            f"\n[bold]BenchForge Compare[/bold] — "
            f"[cyan]{label_a or proj_a.name}[/cyan] vs "
            f"[cyan]{label_b or proj_b.name}[/cyan]\n"
        )

    cfg_a = _load_project_config(proj_a)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
        disable=(output_format == "json"),
    ) as progress:
        task = progress.add_task(f"Analyzing {label_a or proj_a.name}...", total=None)

        try:
            result = compare_projects(
                proj_a, proj_b,
                label_left=label_a,
                label_right=label_b,
                config=cfg_a,
            )
        except NotADirectoryError as exc:
            err_console.print(f"Error: {exc}")
            sys.exit(1)

        progress.update(task, description="Done.")

    if output_format == "json":
        payload = {
            "left": {
                "label": result.left.label,
                "path": str(result.left.path),
                "scan": _scan_to_dict(result.left.scan),
                "analysis": _analysis_to_dict(result.left.analysis),
                "score": _score_to_dict(result.left.score),
            },
            "right": {
                "label": result.right.label,
                "path": str(result.right.path),
                "scan": _scan_to_dict(result.right.scan),
                "analysis": _analysis_to_dict(result.right.analysis),
                "score": _score_to_dict(result.right.score),
            },
            "winner": result.winner,
            "score_delta": result.score_delta,
            "category_winners": result.category_winners,
        }
        click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    _print_compare_table(result)


def _winner_marker(category: str, category_winners: dict[str, str], side: str) -> str:
    """Return a checkmark if this side won the category, else empty string."""
    winner = category_winners.get(category, "tie")
    if winner == side:
        return " [green]✓[/green]"
    if winner == "tie":
        return " [dim]=[/dim]"
    return ""


def _print_compare_table(result: object) -> None:
    """Render a rich side-by-side comparison table."""
    from benchforge.core.comparator import CompareResult
    assert isinstance(result, CompareResult)

    l = result.left
    r = result.right
    cw = result.category_winners

    table = Table(
        title="BenchForge Compare",
        box=box.ROUNDED,
        show_lines=True,
    )
    table.add_column("Category", style="dim", min_width=20)
    table.add_column(l.label, justify="right", min_width=14)
    table.add_column(r.label, justify="right", min_width=14)

    def row(label: str, lval: str, rval: str, category: str) -> None:
        lmark = _winner_marker(category, cw, "left")
        rmark = _winner_marker(category, cw, "right")
        table.add_row(label, f"{lval}{lmark}", f"{rval}{rmark}")

    # Scan info
    table.add_row("[bold]--- Project ---[/bold]", "", "")
    table.add_row("Files", str(l.scan.file_count), str(r.scan.file_count))
    table.add_row("Size (KB)", str(l.scan.total_size_kb), str(r.scan.total_size_kb))

    # Analysis
    table.add_row("[bold]--- Analysis ---[/bold]", "", "")
    row("Total Issues", str(l.analysis.total_issues), str(r.analysis.total_issues), "issues")
    row("Avg Complexity", str(l.analysis.avg_complexity), str(r.analysis.avg_complexity), "complexity")
    table.add_row(
        "Avg Maintainability",
        str(l.analysis.avg_maintainability),
        str(r.analysis.avg_maintainability),
    )

    # Scores
    table.add_row("[bold]--- Scores ---[/bold]", "", "")

    def score_cell(val: int, category: str, side: str) -> str:
        color = _score_color(val)
        mark = _winner_marker(category, cw, side)
        return f"[{color}]{val}[/{color}]{mark}"

    table.add_row(
        "Performance",
        score_cell(l.score.performance, "performance", "left"),
        score_cell(r.score.performance, "performance", "right"),
    )
    table.add_row(
        "Maintainability",
        score_cell(l.score.maintainability, "maintainability", "left"),
        score_cell(r.score.maintainability, "maintainability", "right"),
    )
    table.add_row(
        "Memory",
        score_cell(l.score.memory, "memory", "left"),
        score_cell(r.score.memory, "memory", "right"),
    )

    lbs = l.score.benchforge_score
    rbs = r.score.benchforge_score
    lbc = _score_color(lbs)
    rbc = _score_color(rbs)
    table.add_row(
        "[bold]BenchForge Score[/bold]",
        f"[bold][{lbc}]{lbs}[/{lbc}][/bold]",
        f"[bold][{rbc}]{rbs}[/{rbc}][/bold]",
    )

    console.print(table)

    # Winner banner
    if result.winner == "left":
        winner_label = l.label
        loser_score = rbs
        winner_score = lbs
    elif result.winner == "right":
        winner_label = r.label
        loser_score = lbs
        winner_score = rbs
    else:
        winner_label = None

    if winner_label:
        delta = abs(result.score_delta)
        console.print(
            Panel(
                f"[bold green]{winner_label}[/bold green] wins "
                f"([green]{winner_score}[/green] vs [red]{loser_score}[/red], "
                f"delta: +{delta})",
                title="[bold]Winner[/bold]",
                border_style="green",
                expand=False,
            )
        )
    else:
        console.print(
            Panel(
                f"[yellow]Tie![/yellow] Both projects scored [bold]{lbs}[/bold]",
                title="[bold]Result[/bold]",
                border_style="yellow",
                expand=False,
            )
        )


# ---------------------------------------------------------------------------
# ci command
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("path", default=".", metavar="PATH")
@click.option(
    "--min-score", "min_score", default=None, type=int,
    help="Minimum BenchForge score required (default: 60 or value from .benchforge.toml).",
)
@click.option(
    "--format", "output_format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format: text (default) or json.",
)
def ci(path: str, min_score: int | None, output_format: str) -> None:
    """Run quality gate check for CI/CD pipelines.

    Exits with code 1 when the BenchForge score is below --min-score
    (default 60). Use --format json for machine-readable output
    (GitHub Actions, GitLab CI, etc.).

    Example GitHub Actions step:

        - name: BenchForge quality gate
          run: benchforge ci . --min-score 70 --format json
    """
    from benchforge.core.ci_guard import run_ci_check

    try:
        project_path = _resolve_path(path)
    except click.BadParameter as exc:
        err_console.print(f"Error: {exc}")
        sys.exit(1)

    cfg = _load_project_config(project_path)

    try:
        result = run_ci_check(project_path, cfg, min_score_override=min_score)
    except (NotADirectoryError, ValueError) as exc:
        if output_format == "json":
            click.echo(json.dumps({"error": str(exc)}, indent=2))
        else:
            err_console.print(f"Error: {exc}")
        sys.exit(1)

    if output_format == "json":
        payload = {
            "passed": result.passed,
            "actual_score": result.actual_score,
            "min_score": result.min_score,
            "score_gap": result.score_gap,
            "path": str(result.path),
            "scan": _scan_to_dict(result.scan),
            "analysis": _analysis_to_dict(result.analysis),
            "score": _score_to_dict(result.score),
        }
        click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        sys.exit(0 if result.passed else 1)

    # --- text mode ---
    console.print(f"\n[bold]BenchForge CI[/bold] — [cyan]{project_path}[/cyan]\n")

    _print_scores(result.score)

    threshold_color = "green" if result.passed else "red"
    console.print(
        f"\nThreshold: [{threshold_color}]{result.min_score}[/{threshold_color}]  "
        f"Actual: [{threshold_color}]{result.actual_score}[/{threshold_color}]"
    )

    if result.passed:
        console.print(
            Panel(
                f"[green]PASSED[/green] — score {result.actual_score} >= {result.min_score}",
                title="[bold]CI Quality Gate[/bold]",
                border_style="green",
                expand=False,
            )
        )
    else:
        gap = result.score_gap
        console.print(
            Panel(
                f"[red]FAILED[/red] — score {result.actual_score} < {result.min_score} "
                f"(need +{gap} points)",
                title="[bold]CI Quality Gate[/bold]",
                border_style="red",
                expand=False,
            )
        )

    sys.exit(0 if result.passed else 1)


# ---------------------------------------------------------------------------
# pr-guard command
# ---------------------------------------------------------------------------

@cli.command("pr-guard")
@click.argument("path", default=".", metavar="PATH")
@click.option(
    "--save-baseline", "save_baseline_flag", is_flag=True, default=False,
    help="Analyse the project and save scores as the new baseline (.benchforge_baseline.json).",
)
@click.option(
    "--max-drop", "max_drop", default=None, type=int,
    help="Maximum allowed score drop from baseline (default: 5).",
)
@click.option(
    "--format", "output_format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format: text (default) or json.",
)
def pr_guard(path: str, save_baseline_flag: bool, max_drop: int | None, output_format: str) -> None:
    """PR performance guard — detect score regressions between branches.

    Two-step workflow:

    \b
    1. On the base branch, save a baseline:
           benchforge pr-guard . --save-baseline

    \b
    2. On the PR branch, check for regression:
           benchforge pr-guard . --max-drop 5

    Exits with code 1 when the score dropped more than --max-drop points
    compared to the saved baseline. Use --format json for CI output.

    Example GitHub Actions workflow:

    \b
        - name: Save baseline (runs on main)
          if: github.ref == 'refs/heads/main'
          run: benchforge pr-guard . --save-baseline

        - name: PR regression check
          if: github.event_name == 'pull_request'
          run: benchforge pr-guard . --max-drop 5 --format json
    """
    from benchforge.core.pr_guard import (
        run_pr_guard, save_baseline, DEFAULT_MAX_DROP,
        BASELINE_FILENAME,
    )

    try:
        project_path = _resolve_path(path)
    except click.BadParameter as exc:
        err_console.print(f"Error: {exc}")
        sys.exit(1)

    cfg = _load_project_config(project_path)

    # --save-baseline mode
    if save_baseline_flag:
        if output_format == "text":
            console.print(f"\n[bold]BenchForge PR Guard[/bold] — saving baseline for [cyan]{project_path}[/cyan]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
            disable=(output_format == "json"),
        ) as progress:
            task = progress.add_task("Scanning project...", total=None)
            try:
                scan = scan_project(project_path)
            except NotADirectoryError as exc:
                if output_format == "json":
                    click.echo(json.dumps({"error": str(exc)}, indent=2))
                else:
                    err_console.print(f"Error: {exc}")
                sys.exit(1)

            if scan.file_count == 0:
                if output_format == "json":
                    click.echo(json.dumps({"error": "No files found."}, indent=2))
                else:
                    console.print("[yellow]No files found — cannot save baseline.[/yellow]")
                sys.exit(1)

            progress.update(task, description=f"Analyzing {scan.file_count} files...")
            analysis = analyze_project(scan)
            progress.update(task, description="Computing scores...")
            score = compute_score(analysis, config=cfg)

        baseline_path = save_baseline(project_path, score)

        if output_format == "json":
            click.echo(json.dumps({
                "action": "baseline_saved",
                "baseline_file": str(baseline_path),
                "score": _score_to_dict(score),
            }, indent=2, ensure_ascii=False))
        else:
            _print_scores(score)
            console.print(
                Panel(
                    f"[green]Baseline saved[/green] -> {baseline_path.name}\n"
                    f"BenchForge Score: [bold]{score.benchforge_score}[/bold]/100",
                    title="[bold]PR Guard -- Baseline[/bold]",
                    border_style="green",
                    expand=False,
                )
            )
        sys.exit(0)

    # --check mode (default)
    effective_max_drop = max_drop if max_drop is not None else DEFAULT_MAX_DROP

    if output_format == "text":
        console.print(f"\n[bold]BenchForge PR Guard[/bold] — [cyan]{project_path}[/cyan]\n")

    try:
        result = run_pr_guard(project_path, cfg, max_drop=effective_max_drop)
    except FileNotFoundError as exc:
        if output_format == "json":
            click.echo(json.dumps({"error": str(exc)}, indent=2))
        else:
            err_console.print(f"Error: {exc}")
        sys.exit(1)
    except (NotADirectoryError, ValueError) as exc:
        if output_format == "json":
            click.echo(json.dumps({"error": str(exc)}, indent=2))
        else:
            err_console.print(f"Error: {exc}")
        sys.exit(1)

    if output_format == "json":
        payload = {
            "passed": result.passed,
            "actual_score": result.actual_score,
            "baseline_score": result.baseline_score,
            "score_delta": result.score_delta,
            "regression": result.regression,
            "max_drop": result.max_drop,
            "baseline_saved_at": result.baseline.saved_at,
            "path": str(result.path),
            "score": _score_to_dict(result.score),
            "scan": _scan_to_dict(result.scan),
            "analysis": _analysis_to_dict(result.analysis),
        }
        click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        sys.exit(0 if result.passed else 1)

    # text mode
    _print_scores(result.score)

    delta = result.score_delta
    delta_sign = "+" if delta >= 0 else ""
    delta_color = "green" if delta >= 0 else "red"
    console.print(
        f"\nBaseline: [bold]{result.baseline_score}[/bold]  "
        f"Current: [bold]{result.actual_score}[/bold]  "
        f"Delta: [{delta_color}]{delta_sign}{delta}[/{delta_color}]  "
        f"Max drop: {result.max_drop}"
    )

    if result.passed:
        msg = (
            f"[green]PASSED[/green] — score {result.actual_score} "
            f"(baseline {result.baseline_score}, delta {delta_sign}{delta})"
        )
        border = "green"
    else:
        msg = (
            f"[red]FAILED[/red] — score dropped by {result.regression} points "
            f"({result.baseline_score} -> {result.actual_score}, max allowed: {result.max_drop})"
        )
        border = "red"

    console.print(
        Panel(
            msg,
            title="[bold]PR Performance Guard[/bold]",
            border_style=border,
            expand=False,
        )
    )

    sys.exit(0 if result.passed else 1)
