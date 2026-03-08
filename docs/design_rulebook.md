# BenchForge Design Rulebook

Version: 0.2  
Status: Draft  
Audience: Core contributors, vibecoders, plugin developers

------------------------------------------------------------------------

# 1. Mission

BenchForge helps developers **objectively evaluate code quality and
performance in the AI coding era**.

AI tools can generate code faster than humans can reliably review it.
BenchForge solves this by providing:

- deterministic analysis
- performance benchmarking
- code quality scoring
- human-readable explanations

BenchForge answers a simple question:

> Is this code actually good, or does it only look good?

------------------------------------------------------------------------

# 2. Target Users

## Primary Users - Vibecoders

Developers who:

- use AI tools to generate or assist with code
- iterate quickly
- need rapid feedback on performance and quality

Typical workflow:

    AI generates code
    ↓
    Developer checks functionality
    ↓
    BenchForge verifies quality and performance

## Secondary Users

- indie developers
- open-source maintainers
- code reviewers
- AI-assisted development teams

------------------------------------------------------------------------

# 3. Core Principles

## 3.1 Truth First

BenchForge prioritizes **deterministic analysis over AI
interpretation**.

Rules:

- measurements must be factual
- static analysis must be reproducible
- AI must never fabricate analysis results

Architecture:

    Code
    ↓
    Deterministic analysis
    ↓
    Structured findings
    ↓
    AI interpretation

AI may **interpret results**, but never generate them.

------------------------------------------------------------------------

## 3.2 Fast Feedback

BenchForge should return useful insights quickly.

Target runtime:

Small project (<100 files)

    < 5 seconds

Large project

    < 20 seconds

Fast feedback encourages adoption.

------------------------------------------------------------------------

## 3.3 One Command UX

BenchForge must be extremely simple to use.

Primary command:

    benchforge analyze .

The tool should work immediately without complex configuration.

------------------------------------------------------------------------

## 3.4 Vibecoder Friendly

Outputs must be:

- concise
- actionable
- readable

Example:

    Problem
    Nested loop detected

    Impact
    O(n^2) complexity

    Suggestion
    Use dictionary lookup instead of repeated list scanning

Avoid academic or overly verbose explanations.

------------------------------------------------------------------------

## 3.5 Relevant By Default

BenchForge should optimize for **signal over noise**.

Default behavior should prioritize production code and avoid letting test
fixtures, metadata directories, or tiny helper utilities dominate the score.

Rules:

- default scoring should focus on in-scope production files
- common non-production paths may be excluded by default
- scope must remain user-configurable through `.benchforge.toml`
- detectors should prefer fewer false positives over noisy but technically correct matches

Examples:

- test directories can be excluded from the default score
- `from __future__ import annotations` should not be flagged as an unused import
- duplicate detection should ignore trivial helpers and pytest fixtures

------------------------------------------------------------------------

## 3.6 Modular Architecture

BenchForge supports plugins via the `AnalyzerPlugin` protocol.

Core system responsibilities:

- project scanning
- benchmark engine
- scoring
- report generation
- plugin loading

Plugins can extend:

- language support
- analysis modules
- benchmark strategies
- AI interpretation

The plugin protocol, registry, and extension routing helper are already in place. See [`plugin_guide.md`](plugin_guide.md) for the full contributor walkthrough.

------------------------------------------------------------------------

# 4. What BenchForge Is NOT

BenchForge is **not**:

- an IDE
- a formatter
- a linter replacement
- a CI/CD platform
- a style checker

BenchForge **is**:

> A benchmarking and code-quality analysis tool.

------------------------------------------------------------------------

# 5. System Architecture

BenchForge follows a layered architecture:

    Scanner
    ↓
    Static Analysis
    ↓
    Benchmark Engine
    ↓
    Scoring
    ↓
    Interpretation
    ↓
    Reporting

Each layer must remain independent.

------------------------------------------------------------------------

# 6. Deterministic Analysis Layer

Produces objective measurements.

Possible tools:

- ast
- radon
- cProfile
- timeit
- memory_profiler

Example structured output:

```json
{
  "runtime": 0.82,
  "memory_mb": 48,
  "complexity": "O(n log n)",
  "issues": ["nested loops", "long function"]
}
```

These findings become the foundation for scoring and interpretation.

------------------------------------------------------------------------

# 7. AI Interpretation Layer

The AI layer converts structured findings into human explanations.

Responsibilities:

- explain detected issues
- describe performance impact
- suggest improvements

AI must **not**:

- fabricate analysis
- invent complexity values
- override deterministic results

Example interpretation:

    This function repeatedly scans a list inside a loop.
    This results in O(n^2) behaviour for large inputs.

    Recommendation:
    Use a dictionary lookup to avoid repeated scanning.

------------------------------------------------------------------------

# 8. BenchForge Scoring System

BenchForge produces a summary score.

Categories:

- Performance
- Maintainability
- Memory Efficiency

Example:

    Performance: 78
    Maintainability: 83
    Memory: 71

    BenchForge Score: 77

Scoring rules must remain deterministic, transparent, and configurable.

------------------------------------------------------------------------

# 9. Reporting System

BenchForge generates several report formats.

## CLI Report

Fast textual summary for developers.

## HTML Report

Contains:

- charts
- detected issues
- benchmark results
- score breakdown

## Badge Output

SVG badge for README files, CI summaries, and project dashboards.

------------------------------------------------------------------------

# 10. Community Philosophy

BenchForge is designed as a **community-driven project**.

Encouraged contributions:

- plugin development
- benchmark scenarios
- optimization experiments
- performance comparisons

Goal:

Create a shared toolkit for **AI-assisted development workflows**.

------------------------------------------------------------------------

# 11. Development Guidelines

## Code Style

- modular architecture
- type hints where possible
- meaningful docstrings
- readable code over clever tricks

## Performance

BenchForge itself must remain lightweight.

Avoid heavy dependencies unless necessary.

------------------------------------------------------------------------

# 12. Current State and Future Evolution

### Completed

- Core benchmarking and static analysis (v1)
- AI interpretation layer — Mistral AI, `--ai` flag (v1.1 / v1.7)
- Implementation comparison tools — `compare`, `challenge`, `roast` (v1.1–v1.3)
- CI and workflow integration — `ci`, `pr-guard`, `badge` (v1.4–v1.5)
- Community ecosystem foundations — plugin protocol, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, issue and PR templates (v1.8+)

### Next

- Plugin routing: `analyze_project()` dispatches to registered plugins by file extension — prerequisite for the first non-Python language
- Multi-language and monorepo examples

### Future

- First community language plugin (JavaScript / TypeScript candidate)
- Scoring extensions for non-Python issue categories
- Benchmark sharing and community scenarios

For detailed version history, see [`roadmap.md`](roadmap.md).

------------------------------------------------------------------------

# 13. Guiding Philosophy

In the AI coding era:

> Code generation is easy.  
> **Objective evaluation becomes the real challenge.**

BenchForge exists to make that evaluation simple, fast, and trustworthy.
