"""Project scanner - collects structural metadata about a directory.

This module performs a single-pass directory walk and produces a ScanResult.
No code is executed; only file system metadata is read.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

from benchforge.core.config import BenchForgeConfig

EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".cpp": "C++",
    ".c": "C",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".sh": "Shell",
}

SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".tox",
        "node_modules",
        ".venv",
        "venv",
        "env",
        ".env",
        "dist",
        "build",
        ".eggs",
    }
)


@dataclass
class ScanResult:
    root: Path
    file_count: int
    total_size_bytes: int
    languages: dict[str, int]
    modules: list[str]
    files: list[Path]

    @property
    def primary_language(self) -> str | None:
        if not self.languages:
            return None
        return max(self.languages, key=lambda lang: self.languages[lang])

    @property
    def total_size_kb(self) -> float:
        return round(self.total_size_bytes / 1024, 2)


def _matches_pattern(rel_path: str, pattern: str) -> bool:
    basename = rel_path.rsplit("/", 1)[-1]
    return fnmatchcase(rel_path, pattern) or fnmatchcase(basename, pattern)


def _is_in_scope(rel_path: Path, config: BenchForgeConfig) -> bool:
    rel = rel_path.as_posix()
    include_patterns = config.scope.include
    exclude_patterns = config.scope.exclude

    included = True if not include_patterns else any(_matches_pattern(rel, pattern) for pattern in include_patterns)
    if not included:
        return False

    return not any(_matches_pattern(rel, pattern) for pattern in exclude_patterns)


def _is_excluded_dir(rel_path: Path, config: BenchForgeConfig) -> bool:
    rel = rel_path.as_posix().rstrip("/")
    if not rel:
        return False
    return any(
        _matches_pattern(rel, pattern) or _matches_pattern(f"{rel}/__placeholder__", pattern)
        for pattern in config.scope.exclude
    )


def scan_project(path: Path, config: BenchForgeConfig | None = None) -> ScanResult:
    """Scan a project directory and return structural metadata."""
    resolved = path.resolve()
    cfg = config if config is not None else BenchForgeConfig()

    if not resolved.exists():
        raise NotADirectoryError(f"Path does not exist: {resolved}")
    if not resolved.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {resolved}")

    file_count = 0
    total_size_bytes = 0
    languages: dict[str, int] = {}
    modules: list[str] = []
    files: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(resolved):
        current_dir = Path(dirpath)

        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS
            and not d.startswith(".")
            and not _is_excluded_dir((current_dir / d).relative_to(resolved), cfg)
        ]

        if "__init__.py" in filenames:
            init_rel = (current_dir / "__init__.py").relative_to(resolved)
            if _is_in_scope(init_rel, cfg):
                rel = current_dir.relative_to(resolved)
                modules.append(str(rel) if str(rel) != "." else resolved.name)

        for filename in filenames:
            filepath = current_dir / filename
            ext = filepath.suffix.lower()

            if filename.startswith("."):
                continue

            rel_path = filepath.relative_to(resolved)
            if not _is_in_scope(rel_path, cfg):
                continue

            try:
                size = filepath.stat().st_size
            except OSError:
                continue

            file_count += 1
            total_size_bytes += size
            files.append(filepath)

            language = EXTENSION_TO_LANGUAGE.get(ext)
            if language:
                languages[language] = languages.get(language, 0) + 1

    return ScanResult(
        root=resolved,
        file_count=file_count,
        total_size_bytes=total_size_bytes,
        languages=languages,
        modules=modules,
        files=files,
    )
