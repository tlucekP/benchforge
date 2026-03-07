# BenchForge

**BenchForge** is a code quality and benchmarking tool built for the **AI coding era**.

It gives developers — especially **vibecoders** — fast, honest signal about their code:

> *What structural issues does my code have, and where should I look first?*

BenchForge scans your project, detects structural problems via static analysis, optionally measures runtime and memory, and produces a **score with a breakdown of what drove it** — so you can make informed decisions, not just trust a number.

---

## What BenchForge is

- A **signal tool** — it points you toward areas worth reviewing
- A **comparison tool** — it helps you see whether one implementation is cleaner than another
- A **regression guard** — it tells you if a PR made code quality worse
- A **starting point** — issues are listed with file and line so you can investigate

## What BenchForge is not

- A **compiler or linter** — it does not enforce rules or block merges by default
- A **final verdict** — a score of 60 on a large CLI tool is not the same as 60 on a tiny script
- A **replacement for code review** — use it alongside human review, not instead of it
- **Perfect** — static analysis has known limitations (see [Limitations](#limitations) below)

---

# Why BenchForge exists

AI can generate code faster than humans can review it.

That creates a new problem: code may run, look clean, and still be slow, hard to maintain, or structurally fragile.

BenchForge gives you a fast first pass — structural issues with file and line references, a score breakdown, and a heatmap of your most complex files. You decide what matters for your project.

---

# Key Features

### Project Analysis

Scans your repository and detects:

* file structure
* programming language
* project size
* modules

BenchForge scores **production code by default**. Test directories and package metadata are excluded from scoring unless you include them explicitly in `.benchforge.toml`.

---

### Static Code Analysis

Detects common structural issues:

* nested loops
* long functions
* duplicate code
* unused imports

The default rules aim to reduce noise:

* `from __future__ import annotations` is ignored for unused-import detection
* tiny duplicate helpers and pytest fixtures are ignored by duplicate detection
* nested loops over provably structural iterables are not flagged (see below)

#### Nested loop detection

Not all nested loops indicate a performance problem. BenchForge distinguishes
between structural traversal and genuine algorithmic complexity.

**Not flagged** (provably safe):

| Pattern | Example |
|---|---|
| Small fixed range | `for i in range(4):` |
| Literal collection | `for k in ('x', 'y', 'z'):` |
| Attribute access | `for issue in file.issues:` |

**Flagged** (potentially O(n²)):

| Pattern | Example |
|---|---|
| Dynamic range | `for j in range(len(data)):` |
| Plain variable | `for j in items:` |
| Function call | `for node in ast.walk(tree):` |

> **Note:** plain variable iterables (`for x in some_list`) are flagged
> conservatively. Without type information, BenchForge cannot prove that
> `some_list` is independent of the outer loop's collection. If you see
> a false positive, it is safe to review and dismiss it in context.

---

### Performance Benchmarking

BenchForge measures:

* runtime
* CPU usage
* memory usage

---

### BenchForge Score

A composite score (0-100) across three dimensions:

| Sub-score | Weight | What it measures |
|---|---|---|
| Performance | 35% | Nested loops, cyclomatic complexity, or actual benchmark runtime |
| Maintainability | 40% | Radon MI index, long functions, unused imports, duplicate code |
| Memory | 25% | Benchmark peak memory delta, or static proxy from loop analysis |

**Score colors:**

| Score | Color | Signal |
|---|---|---|
| 80-100 | green | Low issue density |
| 50-79 | yellow | Moderate issues — worth reviewing |
| 0-49 | red | High issue density |

These are signal levels. A yellow score means "there are things to look at", not "this code is broken". Use the issue list and heatmap to understand what drove the score.

---

---

# Designed for Vibecoders

BenchForge is built for developers who use AI tools like:

* AI coding assistants
* code generation tools
* automated refactoring

Instead of guessing whether AI-generated code is good, BenchForge gives you **concrete structural data** to act on.

---

# Installation

```bash
pip install benchforge
```

---

# Quick Start

```bash
# Analyze a project
benchforge analyze .

# Run performance benchmarks
benchforge benchmark .

# Generate an HTML report
benchforge report .

# Generate an SVG badge
benchforge badge .

# Show file heatmap
benchforge analyze . --heatmap

# JSON output (for scripts / CI)
benchforge analyze . --format json
```

---

# Commands

| Command | Description |
|---|---|
| `benchforge analyze PATH` | Static analysis + scoring |
| `benchforge benchmark PATH` | Runtime and memory benchmarking |
| `benchforge report PATH` | Full pipeline + HTML report |
| `benchforge badge PATH` | Generate an SVG badge for the current score |
| `benchforge compare PATH_A PATH_B` | Side-by-side comparison of two projects |
| `benchforge challenge PATH...` | Ranked leaderboard for N implementations |
| `benchforge roast PATH` | Fun but honest code insights |
| `benchforge ci PATH` | CI quality gate (exits 1 when score < threshold) |
| `benchforge pr-guard PATH` | PR regression check (exits 1 when score dropped too much) |

### analyze

```bash
benchforge analyze .                        # text output
benchforge analyze . --format json          # JSON output
benchforge analyze . --heatmap              # show file heatmap
benchforge analyze . --heatmap --top 20     # top 20 hottest files
benchforge analyze . --show-test-issues     # include test file issues (hidden by default)
benchforge analyze . --ai                   # add AI insight (requires MISTRAL_API_KEY)
```

### badge

```bash
benchforge badge .
benchforge badge . --output badge.svg
benchforge badge . --style plastic
benchforge badge . --label "code quality"
benchforge badge . --format json
```

### compare

```bash
benchforge compare human/ ai_generated/
benchforge compare human/ ai/ --label-a "Human" --label-b "GPT-4"
benchforge compare human/ ai/ --format json
```

### challenge

```bash
benchforge challenge impl_a/ impl_b/ impl_c/
benchforge challenge impl_a/ impl_b/ --labels "Human,Claude"
benchforge challenge impl_a/ impl_b/ --format json
```

### roast

```bash
benchforge roast .
benchforge roast . --ai          # AI commentary (requires MISTRAL_API_KEY)
benchforge roast . --seed 42     # reproducible output
```

### ci

```bash
benchforge ci .                         # threshold from .benchforge.toml (default 60)
benchforge ci . --min-score 75          # custom threshold
benchforge ci . --format json           # JSON output for GitHub Actions / GitLab CI
```

Configure in `.benchforge.toml`:

```toml
[ci]
min_score = 70
```

### pr-guard

```bash
# On the base branch - save baseline
benchforge pr-guard . --save-baseline

# On the PR branch - check for regression
benchforge pr-guard . --max-drop 5
benchforge pr-guard . --max-drop 5 --format json
```

---

# Example Output

```text
Project: 38 files
Language: Python

Performance Score: 78
Maintainability Score: 83
Memory Score: 71

Detected Issues:
- nested loops
- long function in data_parser.py

BenchForge Score: 77
```

---

# Configuration

Create `.benchforge.toml` in your project root to customize scoring and scope:

```toml
[scope]
exclude = ["tests/**", "dist/**"]
# include = ["src/**"]

[scoring.weights]
performance     = 0.40
maintainability = 0.35
memory          = 0.25

[scoring.penalties]
nested_loop     = 10.0
long_function   = 5.0

[ci]
min_score = 70
```

Default scope excludes common non-production paths such as `tests/**` and `*.egg-info/**`.

**When should you add a `.benchforge.toml`?**

The default thresholds work well for general Python libraries. For other project types, tuning helps:

- **CLI tools** — command handlers are legitimately long and branch-heavy. Consider `long_function = 3.0` and `cc_poor = 20.0`.
- **Data pipelines** — nested iteration over structured data is often structural, not algorithmic. Consider lowering `nested_loop` penalty.
- **Frameworks / engines** — high complexity is architectural. Raise `cc_poor` or lower `high_complexity` penalty.

BenchForge's own `.benchforge.toml` is a working example for a CLI tool. See `docs/scoring.md` for the full scoring reference.

> **Windows / encoding note:** BenchForge reads Python files as UTF-8 with BOM
> stripping (`utf-8-sig`). Files saved as "UTF-8 with BOM" by some editors
> (common on Windows) are handled correctly and will not produce false parse errors.

---

# CI / CD Integration

See `docs/ci_integration.md` for GitHub Actions and GitLab CI examples.

Quick example:

```yaml
- name: BenchForge quality gate
  run: benchforge ci . --min-score 70 --format json
```

---

# Roadmap

## v1 - MVP (done)

* project scanner, static analysis, benchmark engine
* CLI (`analyze`, `benchmark`, `report`)
* HTML report, BenchForge score

## v1.1 (done)

* `compare` - side-by-side project comparison
* file heatmap (`--heatmap`)
* AI interpretation (Mistral AI, `--ai` flag)

## v1.2 (done)

* `roast` - fun code insights

## v1.3 (done)

* `challenge` - ranked leaderboard for N implementations

## v1.4 (done)

* `ci` - quality gate with configurable threshold
* `pr-guard` - PR regression check with baseline file

## v1.5 (done)

* `badge` - SVG badge generator for README / CI
* `scope` config for include / exclude rules
* lower-noise default analysis for production code

## v1.6 (done)

* smarter `nested_loop` detection — structural traversal patterns no longer flagged as false positives
* BOM fix — files saved as UTF-8 with BOM are now parsed correctly

---

# Community

BenchForge is a **community-driven tool**.

We welcome:

* contributors
* benchmark scenarios
* plugins
* optimization experiments

The goal is to build a shared toolkit for **AI-assisted development workflows**.

---

# Philosophy

**Signal over verdict.**
BenchForge gives you data to investigate, not a grade to argue with. A score of 55 on a large CLI tool and a score of 55 on a small utility library mean very different things. The issue list and the breakdown are more useful than the number.

**Deterministic before AI.**
Every score is computed from static analysis rules that are fully auditable. AI interpretation (when enabled) adds commentary on top — it never modifies the underlying score.

**Honest about limitations.**
Static analysis cannot execute your code, infer types, or understand intent. Some detections are conservative by design (see [Limitations](#limitations)). BenchForge tells you what it can see, not what it knows for certain.

**Tunable to your project type.**
Default thresholds are calibrated for general Python libraries. CLI tools, frameworks, and data pipelines have different structural patterns. Use `.benchforge.toml` to adjust penalties and thresholds for your context — BenchForge includes its own config as a working example.

---

# Limitations

BenchForge uses static AST analysis — it reads code without executing it. This means:

**Known false positives:**
- `nested_loop` — plain variable iterables (`for x in items`) are flagged conservatively. Without type information, BenchForge cannot prove that `items` is independent of the outer loop. Review flagged loops in context before acting.
- `long_function` — threshold is 50 lines by default. CLI command handlers, test fixtures, and rendering functions are legitimately longer. Adjust the threshold via `.benchforge.toml` if it creates noise for your project.
- `unused_import` — imports under `TYPE_CHECKING` guards may be reported as unused since they are never resolved at analysis time.

**What static analysis cannot detect:**
- Runtime performance issues that only appear under load
- Logic errors, off-by-one bugs, or incorrect behavior
- Security vulnerabilities
- Issues that require executing the code to observe

For runtime performance, use `benchforge benchmark .` to add actual measurement data to the score.

---

# AI Insight (optional)

The `--ai` flag sends analysis metadata (scores, issue counts, file names) to Mistral AI for a plain-language interpretation. No source code is transmitted — only structured analysis results.

The AI output is framed as observations and suggestions, not verdicts. It interprets the same heuristic signals BenchForge already reports — it does not add new analysis or override scores.

**Setup — one-time per session:**

```bash
export MISTRAL_API_KEY=your_key_here   # Linux / macOS
set MISTRAL_API_KEY=your_key_here      # Windows CMD
$env:MISTRAL_API_KEY="your_key_here"   # Windows PowerShell
```

**Setup — persistent (recommended):**

Create a `.env` file in the project root (never commit it — it is gitignored):

```
MISTRAL_API_KEY=your_key_here
```

On Windows PowerShell, load it with the included helper:

```powershell
. .\load_env.ps1
```

Get a free API key at [console.mistral.ai](https://console.mistral.ai). The tool works fully without it — AI insight is additive, not required.

---

# Contributing

Contributions are welcome. See `CONTRIBUTING.md` for guidelines.

Areas where help is especially valuable:

* scoring improvements and threshold research
* language support beyond Python
* benchmarking strategies
* developer UX and output readability

---

# License

MIT License

---

# The AI Coding Era Needs Better Tools

I created BenchForge out of a love of creativity and a passion for technology. BenchForge exists to help vibecoders/developers **trust their code again** - even when it was written with the help of AI.
