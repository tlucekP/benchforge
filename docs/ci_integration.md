# BenchForge CI Integration

BenchForge includes a built-in quality gate, `benchforge ci`, for CI/CD pipelines.
The command exits with code **1** when the BenchForge score falls below a configured threshold, which causes most CI systems to fail the build automatically.

Use this when you want a simple answer to: "Did this branch stay above our agreed minimum score?"

---

## Quick Start

```bash
# Pass if score >= 60 (default threshold)
benchforge ci .

# Custom threshold
benchforge ci . --min-score 75

# Machine-readable JSON output
benchforge ci . --min-score 70 --format json
```

Exit codes:

| Code | Meaning |
|---|---|
| `0` | Score >= threshold, quality gate passed |
| `1` | Score < threshold, quality gate failed |

---

## Beginner Guidance

A good way to start:

- begin with a **lower threshold** such as 50 or 60
- fix the noisiest issues first
- raise the threshold gradually as the codebase improves

BenchForge should help teams add a useful guardrail without turning CI into a wall of red failures on day one.

For the scoring methodology behind that threshold, see [`scoring.md`](scoring.md).

---

## Configuring the Threshold

### Via CLI flag

```bash
benchforge ci . --min-score 80
```

### Via `.benchforge.toml`

```toml
[ci]
min_score = 70
```

The CLI flag `--min-score` always takes precedence over the config file.

---

## GitHub Actions

### Minimal workflow

```yaml
name: BenchForge Quality Gate

on: [push, pull_request]

jobs:
  quality-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install BenchForge
        run: pip install benchforge

      - name: Run quality gate
        run: benchforge ci . --min-score 70
```

### With JSON output and annotations

```yaml
      - name: Run quality gate (JSON)
        id: benchforge
        run: |
          benchforge ci . --min-score 70 --format json | tee benchforge_result.json
          echo "score=$(jq '.actual_score' benchforge_result.json)" >> $GITHUB_OUTPUT
          echo "passed=$(jq '.passed' benchforge_result.json)" >> $GITHUB_OUTPUT

      - name: Upload BenchForge result
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: benchforge-result
          path: benchforge_result.json

      - name: Fail if quality gate did not pass
        if: steps.benchforge.outputs.passed == 'false'
        run: exit 1
```

### PR comment with score (optional)

```yaml
      - name: Comment score on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const result = JSON.parse(fs.readFileSync('benchforge_result.json'));
            const icon = result.passed ? 'PASS' : 'FAIL';
            const body = `${icon} BenchForge Score: ${result.actual_score}/100 (threshold: ${result.min_score})`;
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body
            });
```

---

## GitLab CI

```yaml
benchforge:
  stage: test
  image: python:3.12
  script:
    - pip install benchforge
    - benchforge ci . --min-score 70 --format json | tee benchforge_result.json
  artifacts:
    paths:
      - benchforge_result.json
    when: always
```

---

## JSON Output Reference

`benchforge ci . --format json` produces:

```json
{
  "passed": true,
  "actual_score": 78,
  "min_score": 70,
  "score_gap": -8,
  "path": "/path/to/project",
  "score": {
    "performance": 80,
    "maintainability": 76,
    "memory": 75,
    "benchforge_score": 78,
    "has_benchmark_data": false,
    "score_notes": []
  },
  "scan": {
    "root": "/path/to/project",
    "file_count": 12,
    "primary_language": "Python",
    "total_size_kb": 48,
    "modules": [],
    "languages": {"Python": 12}
  },
  "analysis": {
    "total_issues": 3,
    "issue_breakdown": {"complexity": 2, "long_function": 1},
    "avg_complexity": 4.2,
    "avg_maintainability": 76.1,
    "issues": []
  }
}
```

`score_gap` is `min_score - actual_score`:

- negative or zero means passing
- positive means how many points are still needed

---

## Tips

- Store the threshold in `.benchforge.toml` so every developer uses the same gate locally.
- Run `benchforge analyze .` locally before pushing to see the full issue breakdown.
- If you need regression protection against drops, pair `benchforge ci` with `benchforge pr-guard`.
