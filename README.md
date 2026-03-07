# BenchForge

**BenchForge** is a code benchmarking and quality analysis tool built for the **AI coding era**.

It helps developers — especially **vibecoders** — quickly answer a simple but critical question:

> *Is this code actually good, or does it only look good?*

BenchForge analyzes projects, measures runtime performance, detects structural issues, and produces **human-readable insights about code quality and performance**.

---

# Why BenchForge exists

AI can generate code faster than humans can review it.

That creates a new problem:

* Code may run
* Code may look clean
* But it might still be **slow, inefficient, or hard to maintain**

BenchForge provides **objective feedback** about:

* performance
* complexity
* maintainability
* memory efficiency

---

# Key Features

### Project Analysis

Scans your repository and detects:

* file structure
* programming language
* project size
* modules

---

### Static Code Analysis

Detects common structural issues:

* nested loops
* long functions
* duplicate code
* unused imports

---

### Performance Benchmarking

BenchForge measures:

* runtime
* CPU usage
* memory usage

---

### BenchForge Score

A simple score summarizing code quality:

Performance
Maintainability
Memory efficiency

Example:

Performance: 78
Maintainability: 83
Memory: 71

**Overall Score: 77**

---

### Human-Readable Insights

BenchForge explains results in plain language.

Example:

Problem
Nested loop detected.

Impact
Function scales approximately as O(n²).

Suggestion
Use a dictionary lookup to avoid repeated list scanning.

---

# Designed for Vibecoders

BenchForge is built for developers who use AI tools like:

* AI coding assistants
* code generation tools
* automated refactoring

Instead of guessing whether AI-generated code is good, BenchForge lets you **measure it objectively**.

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
benchforge analyze . --ai                   # add AI insight (requires MISTRAL_API_KEY)
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

```
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

Create `.benchforge.toml` in your project root to customize scoring:

```toml
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

See `docs/scoring.md` for full reference.

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

## v1.5

* `badge` - SVG badge for README

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

BenchForge follows three core principles:

Truth first
Deterministic analysis comes before AI interpretation.

Fast feedback
Developers should get useful insights in seconds.

Developer friendly
Results must be simple, actionable, and human-readable.

---

# Contributing

Contributions are welcome.

Areas where help is especially valuable:

* language plugins
* benchmarking strategies
* scoring improvements
* developer UX

---

# License

MIT License

---

# The AI Coding Era Needs Better Tools

BenchForge exists to help developers **trust their code again** — even when it was written with the help of AI.
