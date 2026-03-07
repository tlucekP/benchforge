"""Static code analyzer — detects structural issues using AST and radon.

Security note: this module NEVER executes user code.
All analysis is performed via read-only AST parsing.
"""

from __future__ import annotations

import ast
import hashlib
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

from radon.complexity import cc_visit
from radon.metrics import mi_visit

from benchforge.core.scanner import ScanResult

# Functions longer than this line count are flagged.
LONG_FUNCTION_THRESHOLD = 50

# Cyclomatic complexity above this is flagged as high.
HIGH_COMPLEXITY_THRESHOLD = 10


@dataclass
class Issue:
    """A single detected code issue."""

    category: str        # e.g. "nested_loop", "long_function"
    description: str
    file: str            # relative path string for display
    line: int | None = None
    severity: str = "warning"   # "warning" | "error" | "info"


@dataclass
class FileAnalysis:
    """Analysis result for a single Python file."""

    path: Path
    issues: list[Issue] = field(default_factory=list)
    function_count: int = 0
    avg_complexity: float = 0.0
    maintainability_index: float = 100.0
    parse_error: str | None = None


@dataclass
class AnalysisResult:
    """Aggregated analysis result for an entire project."""

    files: list[FileAnalysis] = field(default_factory=list)
    total_issues: int = 0
    issue_breakdown: dict[str, int] = field(default_factory=dict)
    avg_complexity: float = 0.0
    avg_maintainability: float = 100.0
    duplicate_groups: list[list[str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal AST visitors
# ---------------------------------------------------------------------------

class _NestedLoopVisitor(ast.NodeVisitor):
    """Detects for/while loops nested inside other for/while loops."""

    def __init__(self, rel_path: str) -> None:
        self.issues: list[Issue] = []
        self._rel_path = rel_path
        self._loop_depth = 0

    def _visit_loop(self, node: ast.AST) -> None:
        if self._loop_depth >= 1:
            self.issues.append(
                Issue(
                    category="nested_loop",
                    description="Nested loop detected - may indicate O(n^2) or worse complexity.",
                    file=self._rel_path,
                    line=getattr(node, "lineno", None),
                    severity="warning",
                )
            )
        self._loop_depth += 1
        self.generic_visit(node)
        self._loop_depth -= 1

    visit_For = _visit_loop
    visit_While = _visit_loop


class _UnusedImportVisitor(ast.NodeVisitor):
    """Detects imported names that are never referenced in the module body."""

    def __init__(self, rel_path: str) -> None:
        self.issues: list[Issue] = []
        self._rel_path = rel_path
        self._imported: dict[str, int] = {}   # name -> line number
        self._used: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name.split(".")[0]
            self._imported[name] = node.lineno

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name == "*":
                return  # Star imports: skip — can't reliably detect usage
            name = alias.asname if alias.asname else alias.name
            self._imported[name] = node.lineno

    def visit_Name(self, node: ast.Name) -> None:
        self._used.add(node.id)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # Walk down to root Name node to capture module usage like `os.path`.
        root = node
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name):
            self._used.add(root.id)
        self.generic_visit(node)

    def finalize(self) -> None:
        for name, lineno in self._imported.items():
            if name not in self._used:
                self.issues.append(
                    Issue(
                        category="unused_import",
                        description=f"Import '{name}' appears unused.",
                        file=self._rel_path,
                        line=lineno,
                        severity="warning",
                    )
                )


# ---------------------------------------------------------------------------
# Per-file analysis
# ---------------------------------------------------------------------------

def _detect_long_functions(tree: ast.AST, rel_path: str) -> list[Issue]:
    """Return issues for functions/methods exceeding LONG_FUNCTION_THRESHOLD lines."""
    issues: list[Issue] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno
            end = node.end_lineno or start
            length = end - start + 1
            if length > LONG_FUNCTION_THRESHOLD:
                issues.append(
                    Issue(
                        category="long_function",
                        description=(
                            f"Function '{node.name}' is {length} lines long "
                            f"(threshold: {LONG_FUNCTION_THRESHOLD})."
                        ),
                        file=rel_path,
                        line=start,
                        severity="warning",
                    )
                )
    return issues


def _detect_high_complexity(source: str, rel_path: str) -> tuple[list[Issue], float]:
    """Use radon to detect high cyclomatic complexity. Returns (issues, avg_complexity)."""
    issues: list[Issue] = []
    try:
        results = cc_visit(source)
    except Exception:
        return issues, 0.0

    if not results:
        return issues, 0.0

    total = 0.0
    for block in results:
        total += block.complexity
        if block.complexity > HIGH_COMPLEXITY_THRESHOLD:
            issues.append(
                Issue(
                    category="high_complexity",
                    description=(
                        f"'{block.name}' has cyclomatic complexity {block.complexity} "
                        f"(threshold: {HIGH_COMPLEXITY_THRESHOLD})."
                    ),
                    file=rel_path,
                    line=block.lineno,
                    severity="warning",
                )
            )

    avg = round(total / len(results), 2)
    return issues, avg


def _get_maintainability_index(source: str) -> float:
    """Return radon maintainability index (0-100). Returns 100.0 on failure."""
    try:
        mi = mi_visit(source, multi=True)
        return round(float(mi), 2)
    except Exception:
        return 100.0


def analyze_file(path: Path, root: Path) -> FileAnalysis:
    """Analyze a single Python file for structural issues.

    Args:
        path: Absolute path to the Python file.
        root: Project root, used to compute relative paths for display.

    Returns:
        FileAnalysis with all detected issues and metrics.
    """
    try:
        rel_path = str(path.relative_to(root))
    except ValueError:
        rel_path = path.name

    result = FileAnalysis(path=path)

    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        result.parse_error = f"Cannot read file: {exc}"
        return result

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        result.parse_error = f"Syntax error: {exc}"
        return result

    # Nested loops
    loop_visitor = _NestedLoopVisitor(rel_path)
    loop_visitor.visit(tree)
    result.issues.extend(loop_visitor.issues)

    # Long functions
    result.issues.extend(_detect_long_functions(tree, rel_path))

    # Unused imports
    import_visitor = _UnusedImportVisitor(rel_path)
    import_visitor.visit(tree)
    import_visitor.finalize()
    result.issues.extend(import_visitor.issues)

    # Cyclomatic complexity (radon)
    complexity_issues, avg_cc = _detect_high_complexity(source, rel_path)
    result.issues.extend(complexity_issues)
    result.avg_complexity = avg_cc

    # Count functions
    result.function_count = sum(
        1 for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )

    # Maintainability index (radon)
    result.maintainability_index = _get_maintainability_index(source)

    return result


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def _hash_function_body(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Produce a stable hash of a function's body, ignoring names and whitespace."""
    try:
        source = ast.unparse(node.body)
    except Exception:
        return ""
    normalized = textwrap.dedent(source).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()


def _find_duplicate_functions(py_files: list[FileAnalysis], root: Path) -> list[list[str]]:
    """Detect functions with identical bodies across all analyzed files.

    Returns a list of duplicate groups, each group being a list of
    'file:line:function_name' strings.
    """
    body_map: dict[str, list[str]] = {}

    for file_analysis in py_files:
        if file_analysis.parse_error:
            continue
        try:
            source = file_analysis.path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except (OSError, SyntaxError):
            continue

        try:
            rel = str(file_analysis.path.relative_to(root))
        except ValueError:
            rel = file_analysis.path.name

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body_hash = _hash_function_body(node)
                if not body_hash:
                    continue
                key = f"{rel}:{node.lineno}:{node.name}"
                body_map.setdefault(body_hash, []).append(key)

    return [group for group in body_map.values() if len(group) > 1]


# ---------------------------------------------------------------------------
# Project-level analysis
# ---------------------------------------------------------------------------

def analyze_project(scan_result: ScanResult) -> AnalysisResult:
    """Analyze all Python files discovered in a ScanResult.

    Args:
        scan_result: Output from scanner.scan_project().

    Returns:
        AnalysisResult aggregating findings across all files.
    """
    py_files = [f for f in scan_result.files if f.suffix.lower() == ".py"]

    file_analyses: list[FileAnalysis] = [
        analyze_file(f, scan_result.root) for f in py_files
    ]

    # Aggregate metrics
    total_issues = sum(len(fa.issues) for fa in file_analyses)
    issue_breakdown: dict[str, int] = {}
    for fa in file_analyses:
        for issue in fa.issues:
            issue_breakdown[issue.category] = issue_breakdown.get(issue.category, 0) + 1

    complexities = [fa.avg_complexity for fa in file_analyses if fa.avg_complexity > 0]
    avg_complexity = round(sum(complexities) / len(complexities), 2) if complexities else 0.0

    maintainabilities = [fa.maintainability_index for fa in file_analyses]
    avg_maintainability = (
        round(sum(maintainabilities) / len(maintainabilities), 2)
        if maintainabilities else 100.0
    )

    duplicate_groups = _find_duplicate_functions(file_analyses, scan_result.root)

    # Add duplicate issues to the relevant FileAnalysis objects
    for group in duplicate_groups:
        for entry in group:
            # entry format: "rel/path.py:line:name"
            parts = entry.rsplit(":", 2)
            if len(parts) == 3:
                rel_path, lineno_str, func_name = parts
                try:
                    lineno = int(lineno_str)
                except ValueError:
                    lineno = None
                # Find the matching FileAnalysis and append issue
                for fa in file_analyses:
                    try:
                        fa_rel = str(fa.path.relative_to(scan_result.root))
                    except ValueError:
                        fa_rel = fa.path.name
                    if fa_rel == rel_path:
                        fa.issues.append(
                            Issue(
                                category="duplicate_code",
                                description=(
                                    f"Function '{func_name}' appears to be a duplicate "
                                    f"(identical body found in {len(group) - 1} other location(s))."
                                ),
                                file=rel_path,
                                line=lineno,
                                severity="info",
                            )
                        )
                        break

    # Recount after duplicate issues are added
    total_issues = sum(len(fa.issues) for fa in file_analyses)
    issue_breakdown = {}
    for fa in file_analyses:
        for issue in fa.issues:
            issue_breakdown[issue.category] = issue_breakdown.get(issue.category, 0) + 1

    return AnalysisResult(
        files=file_analyses,
        total_issues=total_issues,
        issue_breakdown=issue_breakdown,
        avg_complexity=avg_complexity,
        avg_maintainability=avg_maintainability,
        duplicate_groups=duplicate_groups,
    )
