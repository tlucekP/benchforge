"""Static code analyzer - detects structural issues using AST and radon.

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

LONG_FUNCTION_THRESHOLD = 50
HIGH_COMPLEXITY_THRESHOLD = 10
MIN_DUPLICATE_BODY_LINES = 3


@dataclass
class Issue:
    """A single detected code issue."""

    category: str
    description: str
    file: str
    line: int | None = None
    severity: str = "warning"


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


_TEST_PATH_SEGMENTS = {"tests", "test"}
_TEST_FILE_PREFIXES = ("test_",)
_TEST_FILE_SUFFIXES = ("_test.py",)


def _is_test_file(path: str) -> bool:
    """Return True if the file path matches common test file conventions.

    Checks:
    - filename starts with 'test_' or ends with '_test.py'
    - any parent directory segment is 'tests' or 'test'
    """
    from pathlib import PurePosixPath, PureWindowsPath
    parts = PurePosixPath(path.replace("\\", "/")).parts
    name = parts[-1] if parts else ""
    if any(name.startswith(p) for p in _TEST_FILE_PREFIXES):
        return True
    if any(name.endswith(s) for s in _TEST_FILE_SUFFIXES):
        return True
    if any(seg in _TEST_PATH_SEGMENTS for seg in parts[:-1]):
        return True
    return False


_SMALL_STATIC_ITERABLE_LIMIT = 16


def _is_safe_inner_iterable(node: ast.expr) -> bool:
    """Return True if the inner loop iterable is safe to skip flagging.

    Covers patterns that do not indicate algorithmic O(n^2) complexity:

    - range(N) where N is a small integer literal
    - literal list/tuple/set where all elements are constants
    - attribute access (e.g. fa.issues, node.children) — sub-collection
      of the outer loop's element, structural traversal not a cross-product
    """
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id == "range" and len(node.args) == 1:
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, int):
                return arg.value <= _SMALL_STATIC_ITERABLE_LIMIT
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(isinstance(elt, ast.Constant) for elt in node.elts)
    if isinstance(node, ast.Attribute):
        return True
    return False


class _NestedLoopVisitor(ast.NodeVisitor):
    """Detects for/while loops nested inside other for/while loops.

    Skips inner loops whose iterable is provably small and static,
    as these do not indicate algorithmic complexity issues.
    """

    def __init__(self, rel_path: str) -> None:
        self.issues: list[Issue] = []
        self._rel_path = rel_path
        self._loop_depth = 0

    def _visit_loop(self, node: ast.AST) -> None:
        if self._loop_depth >= 1:
            iterable = getattr(node, "iter", None)
            if iterable is None or not _is_safe_inner_iterable(iterable):
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


def _collect_type_checking_lines(tree: ast.AST) -> set[int]:
    """Return line numbers of imports guarded by 'if TYPE_CHECKING:'.

    Imports inside these blocks are type-annotation-only and should not
    be flagged as unused — they are never executed at runtime.
    """
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        is_type_checking = (
            (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING")
            or (
                isinstance(test, ast.Attribute)
                and test.attr == "TYPE_CHECKING"
            )
        )
        if not is_type_checking:
            continue
        for child in ast.walk(node):
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                guarded.add(child.lineno)
    return guarded


class _UnusedImportVisitor(ast.NodeVisitor):
    """Detect imported names that are never referenced in the module body."""

    def __init__(self, rel_path: str, type_checking_lines: set[int]) -> None:
        self.issues: list[Issue] = []
        self._rel_path = rel_path
        self._imported: dict[str, int] = {}
        self._used: set[str] = set()
        self._type_checking_lines = type_checking_lines

    def visit_Import(self, node: ast.Import) -> None:
        if node.lineno in self._type_checking_lines:
            return
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name.split(".")[0]
            self._imported[name] = node.lineno

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.lineno in self._type_checking_lines:
            return
        for alias in node.names:
            if alias.name == "*":
                return
            if node.module == "__future__" and alias.name == "annotations":
                continue
            name = alias.asname if alias.asname else alias.name
            self._imported[name] = node.lineno

    def visit_Name(self, node: ast.Name) -> None:
        self._used.add(node.id)

    def visit_Attribute(self, node: ast.Attribute) -> None:
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


def _detect_long_functions(tree: ast.AST, rel_path: str) -> list[Issue]:
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

    return issues, round(total / len(results), 2)


def _get_maintainability_index(source: str) -> float:
    try:
        mi = mi_visit(source, multi=True)
        return round(float(mi), 2)
    except Exception:
        return 100.0


def analyze_file(path: Path, root: Path) -> FileAnalysis:
    """Analyze a single Python file for structural issues."""
    try:
        rel_path = str(path.relative_to(root))
    except ValueError:
        rel_path = path.name

    result = FileAnalysis(path=path)

    try:
        source = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        result.parse_error = f"Cannot read file: {exc}"
        return result

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        result.parse_error = f"Syntax error: {exc}"
        return result

    loop_visitor = _NestedLoopVisitor(rel_path)
    loop_visitor.visit(tree)
    result.issues.extend(loop_visitor.issues)

    result.issues.extend(_detect_long_functions(tree, rel_path))

    tc_lines = _collect_type_checking_lines(tree)
    import_visitor = _UnusedImportVisitor(rel_path, tc_lines)
    import_visitor.visit(tree)
    import_visitor.finalize()
    result.issues.extend(import_visitor.issues)

    complexity_issues, avg_cc = _detect_high_complexity(source, rel_path)
    result.issues.extend(complexity_issues)
    result.avg_complexity = avg_cc

    result.function_count = sum(
        1 for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    result.maintainability_index = _get_maintainability_index(source)
    return result


def _hash_function_body(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Produce a stable hash of a function body, ignoring names and whitespace."""
    try:
        source = ast.unparse(node.body)
    except Exception:
        return ""
    normalized = textwrap.dedent(source).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()


def _has_fixture_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Name) and target.id == "fixture":
            return True
        if isinstance(target, ast.Attribute) and target.attr == "fixture":
            return True
    return False


def _is_duplicate_candidate(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    if _has_fixture_decorator(node) or not node.body:
        return False
    start = getattr(node.body[0], "lineno", node.lineno)
    last = node.body[-1]
    end = getattr(last, "end_lineno", getattr(last, "lineno", start))
    return (end - start + 1) > MIN_DUPLICATE_BODY_LINES


def _find_duplicate_functions(py_files: list[FileAnalysis], root: Path) -> list[list[str]]:
    """Detect functions with identical bodies across all analyzed files."""
    body_map: dict[str, list[str]] = {}

    for file_analysis in py_files:
        if file_analysis.parse_error:
            continue
        try:
            source = file_analysis.path.read_text(encoding="utf-8-sig", errors="replace")
            tree = ast.parse(source)
        except (OSError, SyntaxError):
            continue

        try:
            rel = str(file_analysis.path.relative_to(root))
        except ValueError:
            rel = file_analysis.path.name

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not _is_duplicate_candidate(node):
                    continue
                body_hash = _hash_function_body(node)
                if not body_hash:
                    continue
                key = f"{rel}:{node.lineno}:{node.name}"
                body_map.setdefault(body_hash, []).append(key)

    return [group for group in body_map.values() if len(group) > 1]


def analyze_project(scan_result: ScanResult) -> AnalysisResult:
    """Analyze all Python files discovered in a ScanResult."""
    py_files = [f for f in scan_result.files if f.suffix.lower() == ".py"]
    file_analyses: list[FileAnalysis] = [analyze_file(f, scan_result.root) for f in py_files]

    issue_breakdown: dict[str, int] = {}
    for file_analysis in file_analyses:
        for issue in file_analysis.issues:
            issue_breakdown[issue.category] = issue_breakdown.get(issue.category, 0) + 1

    complexities = [fa.avg_complexity for fa in file_analyses if fa.avg_complexity > 0]
    avg_complexity = round(sum(complexities) / len(complexities), 2) if complexities else 0.0

    maintainabilities = [fa.maintainability_index for fa in file_analyses]
    avg_maintainability = round(sum(maintainabilities) / len(maintainabilities), 2) if maintainabilities else 100.0

    duplicate_groups = _find_duplicate_functions(file_analyses, scan_result.root)

    for group in duplicate_groups:
        for entry in group:
            parts = entry.rsplit(":", 2)
            if len(parts) != 3:
                continue
            rel_path, lineno_str, func_name = parts
            try:
                lineno = int(lineno_str)
            except ValueError:
                lineno = None
            for file_analysis in file_analyses:
                try:
                    file_rel = str(file_analysis.path.relative_to(scan_result.root))
                except ValueError:
                    file_rel = file_analysis.path.name
                if file_rel == rel_path:
                    file_analysis.issues.append(
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

    total_issues = sum(len(file_analysis.issues) for file_analysis in file_analyses)
    issue_breakdown = {}
    for file_analysis in file_analyses:
        for issue in file_analysis.issues:
            issue_breakdown[issue.category] = issue_breakdown.get(issue.category, 0) + 1

    return AnalysisResult(
        files=file_analyses,
        total_issues=total_issues,
        issue_breakdown=issue_breakdown,
        avg_complexity=avg_complexity,
        avg_maintainability=avg_maintainability,
        duplicate_groups=duplicate_groups,
    )
