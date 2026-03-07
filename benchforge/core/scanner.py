"""Project scanner — collects structural metadata about a directory.

This module performs a single-pass directory walk and produces a ScanResult.
No code is executed; only file system metadata is read.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Maps file extensions to language names.
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

# Directories to skip during scanning.
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
    """Structured result of a project directory scan."""

    root: Path
    file_count: int
    total_size_bytes: int
    languages: dict[str, int]  # language -> file count
    modules: list[str]         # relative paths of Python packages (dirs with __init__.py)
    files: list[Path]          # absolute paths of all non-skipped files

    @property
    def primary_language(self) -> str | None:
        """Return the most common language, or None if no files found."""
        if not self.languages:
            return None
        return max(self.languages, key=lambda lang: self.languages[lang])

    @property
    def total_size_kb(self) -> float:
        return round(self.total_size_bytes / 1024, 2)


def scan_project(path: Path) -> ScanResult:
    """Scan a project directory and return structural metadata.

    Args:
        path: Absolute or relative path to the project root.

    Returns:
        ScanResult with file counts, language breakdown, size, and modules.

    Raises:
        NotADirectoryError: If path does not exist or is not a directory.
    """
    resolved = path.resolve()

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

        # Prune hidden and ignorable directories in-place (modifies walk).
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith(".")
        ]

        # Detect Python packages.
        if "__init__.py" in filenames:
            rel = current_dir.relative_to(resolved)
            modules.append(str(rel) if str(rel) != "." else resolved.name)

        for filename in filenames:
            filepath = current_dir / filename
            ext = filepath.suffix.lower()

            # Skip hidden files.
            if filename.startswith("."):
                continue

            try:
                size = filepath.stat().st_size
            except OSError:
                # File might have been removed or be inaccessible — skip safely.
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
