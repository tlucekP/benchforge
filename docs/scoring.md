# BenchForge Scoring Methodology

Version: 1.3  
Status: Reference  
Source of truth: `benchforge/core/scoring.py`, `benchforge/core/config.py`, `benchforge/core/scanner.py`, `benchforge/core/analyzer.py`

---

## Start Here

This document explains how BenchForge turns analysis results into a **BenchForge Score** from 0 to 100.

That score exists to give you a fast, repeatable signal:

- where code may deserve review
- whether one version looks healthier than another
- whether a pull request may have made quality worse

What it does **not** claim to do:

- it does not prove code is correct
- it does not replace profiling real workloads
- it does not produce a universal, scientific truth about code quality
- it is not the final judgment on whether code is "good"

BenchForge scoring is **deterministic**. That means the same code and the same configuration produce the same score every time. Optional AI commentary can explain the result, but it never changes the result.

If you want onboarding and quick-start usage first, see [`../README.md`](../README.md).
If you want the product philosophy behind the scoring system, see [`design_rulebook.md`](design_rulebook.md).
If you want future product direction, see [`roadmap.md`](roadmap.md).

---

## The Short Version

BenchForge builds one final score from **three sub-scores**:

| Sub-score | Default weight | Main input |
|---|---|---|
| Performance | 35% | static analysis or benchmark runtime |
| Maintainability | 40% | Maintainability Index plus issue penalties |
| Memory | 25% | benchmark memory data or static proxy |

Simple flow:

1. BenchForge scans the files that are in scope.
2. It runs static analysis to detect structural issues.
3. If benchmark data exists, it uses measurement where it can.
4. It computes the three sub-scores.
5. It combines them using the weights above.

Important mental model:

- some parts are based on **measured runtime or memory**
- some parts are based on **static analysis heuristics**
- some parts use established external metrics such as **Maintainability Index**
- the final BenchForge score is BenchForge's own product-calibrated scoring system built on top of those inputs

That means the score is useful, but it is still a tool for review and comparison, not a universal truth machine.

---

## Plain-English Terms

These terms show up a lot in the scoring rules.

- **Deterministic**: BenchForge is not guessing differently from run to run. If the code and config stay the same, the score stays the same.
- **Static analysis**: BenchForge reads your code without running it. It looks for patterns such as nested loops, long functions, and unused imports.
- **Benchmark data**: actual runtime or memory measurements collected by `benchforge benchmark .`.
- **Cyclomatic complexity**: a rough "how many branches do I have to think about?" number for a function. More `if`, `elif`, loops, and branches usually means the number goes up.
- **Maintainability Index (MI)**: an existing metric from the broader code-analysis world that tries to estimate how hard code may be to maintain. BenchForge uses it as one input, not as the whole truth.
- **Proxy**: a stand-in signal. When BenchForge does not have memory measurements, it uses a proxy instead of pretending it knows exact memory usage.
- **Penalty**: points removed from a score when BenchForge sees a pattern it considers risky.
- **Cap**: the maximum amount one issue type can subtract. Caps stop one category from wiping out the whole score by itself.
- **Threshold**: the cutoff where BenchForge starts treating a metric as excellent, poor, fast, slow, and so on.
- **O(n^2)**: work that can grow very fast because a growing loop contains another growing loop.

---

## How the Score Is Built

### Step 1: choose the files to score

BenchForge does not always score every file in the repository. It first decides which files are **in scope**.

In plain English, "in scope" means: these are the files that count toward the score.

By default, BenchForge focuses on production code and excludes common non-production paths such as tests and `*.egg-info/**`.

Why this matters:

- test code often has different patterns than production code
- fixtures and helpers can be repetitive on purpose
- letting those files dominate the score can make the score less fair

BenchForge is trying to answer, "How does the main codebase look?" not "How tidy is every support file in the repo?"

### Step 2: gather signals

BenchForge gathers signals from two places:

- **Static analysis**: nested loops, long functions, unused imports, duplicate code, complexity, maintainability index
- **Benchmark data**: measured runtime and measured memory, if you ran benchmarks

### Step 3: compute three sub-scores

- **Performance**
- **Maintainability**
- **Memory**

### Step 4: combine them with weights

```text
BenchForge Score = Performance * 0.35
                 + Maintainability * 0.40
                 + Memory * 0.25
```

Result is rounded to the nearest integer.

---

## Measured vs Estimated Signals

This distinction is important.

### Measured signals

These come from actual benchmark runs:

- runtime used in the **Performance** score when benchmark data exists
- memory delta used in the **Memory** score when benchmark data exists

Measured signals are usually more realistic because they come from code that actually ran.

### Estimated signals

These come from static analysis or BenchForge-specific heuristics:

- nested-loop detection
- long-function detection
- unused-import detection
- duplicate-code detection
- complexity-based scoring
- the static-proxy memory score when no benchmark memory data exists

Estimated signals are still useful, but they are not direct proof of real runtime or memory behavior.

### Why the distinction matters

If you only run `benchforge analyze .`, BenchForge can still give you a strong structural signal. But some of that signal is based on pattern matching and scoring rules, not measurement.

If you also run `benchforge benchmark .`, the performance and memory scores can become more grounded in actual behavior.

---

## Scope Rules

Before any score is computed, BenchForge builds the set of files that are in scope for analysis.

### Default scope

If `.benchforge.toml` does not define scope rules, BenchForge uses:

```toml
[scope]
exclude = [
  "tests/**",
  "test/**",
  "testing/**",
  "**/tests/**",
  "**/test/**",
  "**/testing/**",
  "*.egg-info/**",
  "**/*.egg-info/**",
]
```

Practical meaning:

- application and library code count toward the score by default
- common test paths do not count toward the score by default
- package metadata does not count toward the score by default

This keeps the default score focused on the code that usually matters most in production.

### Custom scope

You can override scope per project:

```toml
[scope]
include = ["src/**", "scripts/**"]
exclude = ["src/legacy/**", "scripts/tmp/**"]
```

Rules:

- If `include` is empty, all files are eligible before exclusions.
- `exclude` always wins over `include`.
- Scope rules affect scanning, analysis, score computation, CI checks, compare, challenge, PR guard, badge generation, and benchmark file discovery.

---

## Weights, Penalties, Caps, and Thresholds

BenchForge uses a few different scoring building blocks.

### Weights

Weights decide how much each sub-score matters in the final result.

Current defaults:

- Performance: `0.35`
- Maintainability: `0.40`
- Memory: `0.25`

This means maintainability has the biggest influence by default.

### Penalties

Penalties remove points when BenchForge sees certain issue types.

Example:

- one `long_function` issue removes `5` points from the maintainability score before caps are considered

A penalty does **not** mean BenchForge has proven your code is bad. It means BenchForge treats that pattern as a review signal worth weighting.

### Caps

Caps limit how much one issue type can hurt a score.

Why caps exist:

- they prevent one category from overwhelming everything else
- they make the scoring less punitive
- they reflect that repeated issues matter, but not infinitely

Example:

- `long_function` has a `5` point penalty and a `25` point cap
- 2 long functions subtract `10`
- 10 long functions would mathematically subtract `50`
- but the cap stops that at `25`

### Thresholds

Thresholds define what BenchForge treats as excellent, poor, fast, slow, small, or large.

Example:

- average complexity `<= 3.0` maps to a performance complexity score of `100`
- average complexity `>= 15.0` maps to `0`

Thresholds are not universal laws of software engineering. They are BenchForge's documented defaults, and they can be tuned for your project.

---

## 1. Performance Score (0-100)

Performance can come from either **static estimates** or **measured benchmark runtime**.

### Without benchmark data

When no benchmark result is supplied, BenchForge estimates performance from static analysis in two steps.

#### Step 1: issue penalties

Start from `100` and subtract penalties.

| Issue | Penalty per occurrence | Cap |
|---|---|---|
| `nested_loop` | 8 pts | 40 pts total |
| `high_complexity` | 6 pts | 30 pts total |

Tiny example:

```python
for user in users:
    for order in orders:
        if order.user_id == user.id:
            ...
```

BenchForge may flag the inner loop as `nested_loop` because the work can grow quickly as the data grows.

#### Step 2: complexity blend

If average cyclomatic complexity is available, BenchForge blends the issue-based score with a complexity-based score:

```text
final = issue_score * 0.60 + complexity_score * 0.40
```

Complexity score is linearly mapped between these thresholds:

| Avg complexity | Complexity score |
|---|---|
| <= 3.0 | 100 |
| >= 15.0 | 0 |

In plain English: lower average complexity helps, higher average complexity hurts.

### With benchmark data

If benchmark results exist, BenchForge uses **measured runtime** instead of the static performance estimate.

Average mean runtime across all successfully benchmarked zero-argument functions is mapped linearly:

| Runtime | Score |
|---|---|
| <= 10 ms | 100 |
| >= 1000 ms | 0 |

This is more realistic than guessing from structure alone, because it uses real execution data.

### Edge case: benchmarks ran, but none succeeded

If benchmark mode ran but there were **no successful benchmark results**, BenchForge returns a neutral performance score of `50` and notes that no successful runtime data was available.

---

## 2. Maintainability Score (0-100)

Maintainability is the most heavily weighted sub-score by default.

It combines:

- an external metric, **Maintainability Index (MI)**
- BenchForge-specific issue penalties

### Base score from Maintainability Index

BenchForge uses Radon's Maintainability Index as the starting point.

| MI value | Score |
|---|---|
| >= 90 | 100 |
| <= 20 | 0 |

Important: MI is not a perfect truth detector. It is an established metric that BenchForge uses as one signal about readability and changeability.

### Issue penalties

After the MI-based starting score, BenchForge subtracts issue penalties.

| Issue | Penalty per occurrence | Cap |
|---|---|---|
| `long_function` | 5 pts | 25 pts |
| `unused_import` | 2 pts | 25 pts |
| `duplicate_code` | 4 pts | 25 pts |

Tiny examples:

Long function:

```python
def handle_cli_command(...):
    # 80+ lines of branching, formatting, and side effects
    ...
```

Unused import:

```python
import json

print("hello")
```

If `json` is never used, BenchForge may flag it as `unused_import`.

Duplicate code:

- two functions with effectively identical normalized bodies can be flagged as `duplicate_code`
- tiny helpers and pytest fixtures are intentionally ignored to reduce noise

Penalty example:

- suppose MI maps to `82`
- suppose BenchForge finds `2` long functions
- penalty is `2 * 5 = 10`
- maintainability becomes `72`

---

## 3. Memory Score (0-100)

Memory can come from either **measured benchmark memory data** or a **static proxy**.

### With benchmark data

Average peak memory delta across successful benchmarks is mapped linearly:

| Memory delta | Score |
|---|---|
| <= 5 MB | 100 |
| >= 200 MB | 0 |

This is the measured version of the memory score.

### Without benchmark data

If no usable benchmark memory data exists, BenchForge falls back to a static proxy.

BenchForge starts from a conservative default of `80`, then reduces it based on nested-loop risk:

| Nested loops | Penalty | Cap |
|---|---|---|
| n | n * 5 pts | 20 pts |

Important:

- this is **not direct memory measurement**
- this is a **risk signal**
- BenchForge is being honest that it cannot know real memory usage from static analysis alone

### Edge case: benchmark object exists, but usable memory data does not

If benchmark mode ran but there were no successful functions with positive memory data, BenchForge falls back to the same static proxy described above.

---

## Worked Example

This is a simplified example for illustration.

Imagine a small project where BenchForge finds:

- `2` nested loops
- `1` high-complexity function
- average cyclomatic complexity: `6.0`
- average Maintainability Index: `78`
- `1` long function
- `1` unused import
- no benchmark data

### Performance

Issue penalties:

- `2` nested loops -> `2 * 8 = 16`
- `1` high-complexity function -> `1 * 6 = 6`
- issue-based score so far: `100 - 16 - 6 = 78`

Complexity blend:

- average complexity `6.0` maps somewhere between the "excellent" and "poor" thresholds
- BenchForge blends that complexity score with the issue-based score
- suppose the final performance score becomes `73`

### Maintainability

- MI `78` maps to a maintainability base score somewhere above the middle
- `1` long function -> `-5`
- `1` unused import -> `-2`
- suppose final maintainability becomes `68`

### Memory

- no benchmark data exists
- start from static proxy `80`
- `2` nested loops -> `2 * 5 = 10`
- memory score becomes `70`

### Final BenchForge Score

```text
BenchForge Score = 73 * 0.35
                 + 68 * 0.40
                 + 70 * 0.25
                 = 25.55 + 27.2 + 17.5
                 = 70.25
```

Rounded result: **70**

This example is intentionally simplified. The point is to show how sub-scores and weights work together, not to claim that every project should land in a certain range.

---

## 4. Combined BenchForge Score

The final score is the weighted sum of the three sub-scores:

```text
BenchForge Score = Performance * 0.35
                 + Maintainability * 0.40
                 + Memory * 0.25
```

Result is rounded to the nearest integer.

### Interpretation guide

| Score | Color | Meaning |
|---|---|---|
| 80-100 | green | Low issue density |
| 50-79 | yellow | Moderate issues, worth reviewing |
| 0-49 | red | High issue density, significant structural concerns |

Important:

- these are signal bands, not verdicts
- a `55` in one kind of project is not automatically equal to a `55` in another
- the issue breakdown is often more useful than the final number by itself

If the defaults feel wrong for your project type, such as CLI tools, frameworks, or data pipelines, use `.benchforge.toml` to tune the system.

---

## 5. Issue Detection

BenchForge issue detection is based on **static AST analysis**. It does not execute user code.

| Issue category | Detector | Severity | Notes |
|---|---|---|---|
| `nested_loop` | AST loop depth visitor | warning | skips inner loops that are provably structural |
| `long_function` | AST line count (threshold: 50 lines) | warning | applies to functions and methods |
| `unused_import` | AST import/name visitor | warning | ignores `from __future__ import annotations` |
| `high_complexity` | radon cyclomatic complexity (threshold: > 10) | warning | per function or method |
| `duplicate_code` | SHA-256 hash of normalized function bodies | info | ignores pytest fixtures and very short helpers |

### Nested-loop detection detail

The `nested_loop` detector flags `for` and `while` loops nested inside another loop. But not all nested loops are treated as risky.

**Skipped (not flagged)**

| Pattern | Example | Reason |
|---|---|---|
| `range(N)` where `N <= 16` | `for i in range(4)` | small fixed bound |
| Literal collection | `for k in ('x', 'y', 'z')` | constant-size collection |
| Attribute access | `for issue in file.issues` | structural traversal of child data |

**Still flagged**

| Pattern | Example | Reason |
|---|---|---|
| `range(len(items))` | `for j in range(len(data))` | dynamic bound, could scale badly |
| Plain variable | `for j in items` | BenchForge cannot prove independence |
| Function call | `for x in ast.walk(tree)` | BenchForge cannot bound the size at analysis time |

Known limitation:

- some safe loops can still be flagged because BenchForge does not have full runtime type information
- this is a tradeoff in favor of surfacing possible risks instead of pretending certainty

---

## 6. User Configuration

You can override scoring parameters and scope per project with `.benchforge.toml` in the project root:

```toml
[scope]
include = ["src/**"]
exclude = ["src/legacy/**", "tests/**"]

[scoring.weights]
performance     = 0.40   # must sum to 1.0 with the others
maintainability = 0.35
memory          = 0.25

[scoring.penalties]
nested_loop     = 10.0
long_function   = 4.0
unused_import   = 1.0
high_complexity = 8.0
duplicate_code  = 3.0

[scoring.thresholds]
cc_excellent    = 2.0    # avg complexity -> score 100
cc_poor         = 20.0   # avg complexity -> score 0
mi_excellent    = 90.0
mi_poor         = 20.0
runtime_fast_ms = 10.0
runtime_slow_ms = 1000.0
memory_small_mb = 5.0
memory_large_mb = 200.0
```

Why configuration exists:

- different project types have different structural patterns
- a CLI tool, a data pipeline, and a framework should not always be scored with the exact same assumptions
- BenchForge aims to be transparent and tunable, not rigid for its own sake

Validation rules:

- `performance + maintainability + memory` must equal `1.0`
- all penalties must be `>= 0`
- `cc_excellent < cc_poor`
- `mi_poor < mi_excellent`
- `runtime_fast_ms < runtime_slow_ms`
- `memory_small_mb < memory_large_mb`
- `scope.include` and `scope.exclude` patterns must be non-empty strings

If the file is absent or a key is missing, BenchForge uses built-in defaults.

---

## 7. Limitations and How to Read the Score

Static analysis is useful because it is fast, deterministic, and safe. But it has limits.

### What static analysis can miss

Static analysis does not execute the code, so it cannot directly see:

- how the code behaves with real production data
- load-related slowdowns that only appear at runtime
- logic bugs and incorrect behavior
- memory spikes caused by specific runtime inputs
- project-specific intent that is obvious to humans but not to a parser

### Why false positives happen

BenchForge works from source code structure, not full runtime knowledge.

That means it sometimes has to be conservative. For example:

- a nested loop may be harmless in context, but still worth a look
- a long function may be appropriate for a CLI handler
- duplicate code may be intentional in a boundary layer

### Why the score is still useful

Even though the score is imperfect, it is still useful because it helps you:

- find hotspots faster
- compare one version against another
- catch regressions early
- start review in the most suspicious places

Best practice:

- use the score as a guide
- read the issue list
- profile when performance really matters
- tune the config when your project shape makes the defaults noisy

---

## 8. Design Principles Behind the Score

BenchForge scoring follows a few project-level principles:

- **Deterministic**: same input, same result
- **Transparent**: weights, penalties, thresholds, and caps are inspectable
- **Relevant by default**: production code signal matters more than test noise
- **Non-punitive**: caps stop one issue type from dominating everything
- **Layered**: static analysis provides a baseline, benchmark data improves realism
- **AI-safe**: AI can explain the score, but it cannot alter the score

For the broader philosophy, see [`design_rulebook.md`](design_rulebook.md).
For the beginner-oriented overview, see [`../README.md`](../README.md).
For future direction, see [`roadmap.md`](roadmap.md).
