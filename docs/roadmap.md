# BenchForge Roadmap

This file tracks the main product milestones for BenchForge.
If you want the beginner-friendly product overview first, start with [`../README.md`](../README.md).
If you want the philosophy behind the roadmap, see [`design_rulebook.md`](design_rulebook.md).

## v1 - MVP

- project scanner (`benchforge/core/scanner.py`)
- static analysis (`benchforge/core/analyzer.py`)
- benchmark engine (`benchforge/core/benchmark.py`)
- scoring (`benchforge/core/scoring.py`)
- CLI interface (`benchforge analyze`, `benchforge benchmark`, `benchforge report`)
- HTML report (`benchforge/report/html_report.py`)
- BenchForge score (0-100, three sub-scores: performance, maintainability, memory)
- `--format json` for `analyze`
- progress spinner
- scoring weights configuration (`.benchforge.toml`)

## v1.1

- `benchforge compare PATH_A PATH_B` - side-by-side comparison of two projects
- `benchforge analyze . --heatmap` - file heatmap in CLI + HTML report
- AI interpretation stub (`benchforge/ai/interpreter.py`, Mistral AI, `--ai` flag)

## v1.2

- `benchforge roast .` - fun code insights (deterministic templates + optional AI commentary)

## v1.3

- `benchforge challenge PATH...` - ranked leaderboard for N implementations

## v1.4

- `benchforge ci .` - quality gate, exits with code 1 when score < threshold
  - `--min-score` flag, configurable via `[ci] min_score` in `.benchforge.toml`
  - `--format json` for GitHub Actions / GitLab CI
  - docs: `docs/ci_integration.md`
- `benchforge pr-guard .` - PR regression check
  - `--save-baseline` saves `.benchforge_baseline.json`
  - `--max-drop N` (default 5) - fails if score dropped more than N points
  - `--format json` for CI output

## v1.5

- Badge generator (`benchforge badge .`) - SVG badge for README / CI
  - `--output`, `--style`, `--label`, `--format json`
- Relevance-first scope rules in `.benchforge.toml`
  - `[scope] include = [...]`
  - `[scope] exclude = [...]`
- Lower-noise default analysis
  - test directories excluded from scoring by default
  - `*.egg-info/**` excluded from scoring by default
  - `from __future__ import annotations` ignored in unused-import detection
  - tiny duplicate helpers and pytest fixtures ignored by duplicate detection

## v1.6

- Smarter `nested_loop` detection - inner loops over provably small or static iterables (`range(N<=16)`, literal lists, tuples, and sets) are no longer flagged as false positives
- Smarter `nested_loop` detection (phase 2) - inner loops over attribute access (`obj.attr`) are skipped as structural traversal, not algorithmic complexity
- BOM fix - files saved as UTF-8 with BOM (`U+FEFF`) are parsed correctly via `utf-8-sig`; this previously caused false parse errors in the HTML report

## v1.7

- Mistral AI `--ai` flag fully integrated and end-to-end tested
- AI prompt reframed - output is observations and suggestions, not verdicts
- Fixed `unused_import` false positive for imports inside `if TYPE_CHECKING:` blocks
- `.env` and `.benchforge_baseline.json` added to `.gitignore`
- `load_env.ps1` helper for loading API key on Windows PowerShell

## v1.8

- `benchforge analyze . --show-test-issues` - test file issues hidden by default, opt-in via flag
- Convention-based test file detection (`test_*.py`, `*_test.py`, `tests/`, `test/` directories)
- Footer hint shown when test issues are hidden

## Next

- Plugin routing: `analyze_project()` dispatches to registered plugins by file extension — prerequisite for the first non-Python language
- Improve docs and examples for multi-language and monorepo setups

## Future

- First community language plugin (JavaScript / TypeScript candidate)
- Scoring extensions for non-Python issue categories
