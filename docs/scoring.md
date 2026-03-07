# BenchForge Scoring Methodology

Version: 1.0\
Status: Reference\
Source of truth: `benchforge/core/scoring.py`, `benchforge/core/config.py`

---

## Overview

BenchForge produces a single composite **BenchForge Score** (0–100) from three
sub-scores, each measuring a different quality dimension:

| Sub-score | Default weight | Source |
|---|---|---|
| Performance | 35 % | static analysis or benchmark runtime |
| Maintainability | 40 % | radon MI + issue penalties |
| Memory | 25 % | benchmark delta or static proxy |

All scoring is **deterministic and reproducible** — the same codebase always
produces the same score. AI interpretation (if enabled) never modifies scores.

---

## 1. Performance Score (0–100)

### Without benchmark data (default)

Derived from static analysis in two steps:

**Step 1 — Issue penalties** (start from 100):

| Issue | Penalty per occurrence | Cap |
|---|---|---|
| `nested_loop` | 8 pts | 40 pts total |
| `high_complexity` | 6 pts | 30 pts total |

**Step 2 — Complexity blend:**

If average cyclomatic complexity is available, the score is blended:

```
final = issue_score × 0.60 + complexity_score × 0.40
```

Complexity score is a linear interpolation between:

| Avg complexity | Complexity score |
|---|---|
| ≤ 3.0 (excellent) | 100 |
| ≥ 15.0 (poor) | 0 |

### With benchmark data (`benchforge benchmark .`)

Average mean runtime across all successfully benchmarked zero-argument
functions, mapped linearly:

| Runtime | Score |
|---|---|
| ≤ 10 ms | 100 |
| ≥ 1000 ms | 0 |

---

## 2. Maintainability Score (0–100)

**Base score** from radon Maintainability Index (MI, 0–100):

| MI value | Score |
|---|---|
| ≥ 90 (excellent) | 100 |
| ≤ 20 (poor) | 0 |

**Issue penalties** (applied after MI base, each capped at 25 pts):

| Issue | Penalty per occurrence | Cap |
|---|---|---|
| `long_function` | 5 pts | 25 pts |
| `unused_import` | 2 pts | 25 pts |
| `duplicate_code` | 4 pts | 25 pts |

Example: 10 long functions → 10 × 5 = 50 pts, capped to 25 pts deducted.

---

## 3. Memory Score (0–100)

### With benchmark data

Average peak memory delta across successful benchmarks, mapped linearly:

| Memory delta | Score |
|---|---|
| ≤ 5 MB | 100 |
| ≥ 200 MB | 0 |

### Without benchmark data (static proxy)

Conservative default of **80**, reduced by nested loop risk:

| Nested loops | Penalty | Cap |
|---|---|---|
| n | n × 5 pts | 20 pts |

---

## 4. Combined BenchForge Score

```
BenchForge Score = Performance × 0.35
                 + Maintainability × 0.40
                 + Memory × 0.25
```

Result is rounded to the nearest integer.

### Interpretation guide

| Score | Grade | Meaning |
|---|---|---|
| 80–100 | ✓ Good | Production-ready quality |
| 55–79 | ~ OK | Acceptable, targeted improvements recommended |
| 0–54 | ✗ Poor | Significant quality issues detected |

---

## 5. Issue Detection

Issues are detected by static AST analysis — no code is executed.

| Issue category | Detector | Severity |
|---|---|---|
| `nested_loop` | AST loop depth visitor | warning |
| `long_function` | AST line count (threshold: 50 lines) | warning |
| `unused_import` | AST import/name visitor | warning |
| `high_complexity` | radon cyclomatic complexity (threshold: > 10) | warning |
| `duplicate_code` | SHA-256 hash of normalized function bodies | info |

---

## 6. User Configuration

Scoring parameters can be overridden per-project via `.benchforge.toml`
placed in the project root:

```toml
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
cc_excellent    = 2.0    # avg complexity → score 100
cc_poor         = 20.0   # avg complexity → score 0
mi_excellent    = 90.0
mi_poor         = 20.0
runtime_fast_ms = 10.0
runtime_slow_ms = 1000.0
memory_small_mb = 5.0
memory_large_mb = 200.0
```

Validation rules:
- `performance + maintainability + memory` must equal `1.0`
- All penalties must be `≥ 0`
- `cc_excellent < cc_poor`, `mi_poor < mi_excellent`
- `runtime_fast_ms < runtime_slow_ms`, `memory_small_mb < memory_large_mb`

If the file is absent or a key is missing, built-in defaults are used.

---

## 7. Design Principles

- **Deterministic**: same input → same output, always
- **Transparent**: every penalty and weight is documented and auditable
- **Non-punitive caps**: no single issue type can erase the entire score
- **Layered**: static analysis provides a baseline; benchmark data refines it
- **AI-safe**: AI interpretation layer reads scores but never modifies them
