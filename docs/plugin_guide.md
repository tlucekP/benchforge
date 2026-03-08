# BenchForge Plugin Guide

Version: 1.0
Status: Reference
Audience: Contributors who want to add language support

---

## Start Here

BenchForge currently analyzes **Python** projects.

The plugin architecture is already in place. Adding support for another language means implementing one class that satisfies the `AnalyzerPlugin` protocol, plus updating one routing function in the core.

This guide walks through both steps honestly — including the part that is not wired up yet.

If you want the product philosophy first, see [`design_rulebook.md`](design_rulebook.md).
If you want the project direction, see [`roadmap.md`](roadmap.md).

---

## How the Plugin System Works

BenchForge has a plugin registry in `benchforge/plugins/base.py`.

Any class that satisfies the `AnalyzerPlugin` protocol can be registered and will be recognized by the system. The protocol requires three things:

```python
from pathlib import Path
from benchforge.core.analyzer import Issue

class MyLanguagePlugin:

    @property
    def name(self) -> str:
        return "My Language Analyzer"

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".mylang"})

    def analyze(self, path: Path) -> list[Issue]:
        # analyze the file, return issues
        ...
```

That is the full contract. No base class to inherit. No framework to import beyond `Issue` and the registration helper.

---

## The Reference Implementation

The built-in Python plugin lives at `benchforge/plugins/python/plugin.py`.

It is the reference implementation. It delegates to `analyze_file()` in the core analyzer, validates itself against the protocol at import time, and registers itself.

Read it before writing a new plugin — it shows the full pattern in about 50 lines.

---

## Step-by-Step: Adding a New Language

### 1. Create the plugin directory

```
benchforge/plugins/<language>/
    __init__.py
    plugin.py
```

### 2. Implement the protocol

In `plugin.py`, implement the three required members:

- `name` — human-readable string, e.g. `"JavaScript Analyzer"`
- `supported_extensions` — file extensions this plugin handles, e.g. `frozenset({".js", ".mjs"})`
- `analyze(path)` — reads the file, returns a list of `Issue` objects

The `Issue` dataclass is language-agnostic:

```python
from benchforge.core.analyzer import Issue

Issue(
    category="high_complexity",    # string key used in scoring
    description="...",             # shown to the user
    file="src/app.js",             # relative path
    line=42,                       # optional
    severity="warning",            # "warning" or "info"
)
```

Issue categories that the scoring engine already handles:

| Category | Score effect |
|---|---|
| `nested_loop` | lowers Performance |
| `high_complexity` | lowers Performance |
| `long_function` | lowers Maintainability |
| `unused_import` | lowers Maintainability |
| `duplicate_code` | lowers Maintainability |

You can introduce new category names. They will appear in the issue breakdown but will not affect the score unless the scoring engine is updated to handle them.

### 3. Choose your analysis tooling

Python analysis uses `ast` (built-in) and `radon` (cyclomatic complexity, maintainability index).

For other languages you will need a different approach. Some options:

| Language | Tooling options |
|---|---|
| JavaScript / TypeScript | `tree-sitter`, `escomplex`, subprocess to `eslint --json` |
| Java | `tree-sitter-java`, subprocess to `checkstyle` |
| Go | subprocess to `go vet`, `staticcheck` |
| Rust | subprocess to `clippy --message-format json` |

Subprocess-based approaches work fine. Capture structured output (JSON preferred), map findings to `Issue` objects.

### 4. Register the plugin

At the bottom of your `plugin.py`:

```python
from benchforge.plugins.base import register_plugin

_plugin = MyLanguagePlugin()
assert isinstance(_plugin, AnalyzerPlugin), "Protocol not satisfied"
register_plugin(_plugin)
```

Import your plugin's module somewhere that runs at startup — the cleanest place is `benchforge/plugins/__init__.py`.

### 5. Update `analyze_project()` — the required core change

This is the one place where the current code is not yet wired for multi-language use.

`benchforge/core/analyzer.py`, function `analyze_project()` (line 388), currently does this:

```python
py_files = [f for f in scan_result.files if f.suffix.lower() == ".py"]
```

It hardcodes `.py` and calls `analyze_file()` directly, bypassing the plugin registry.

To support your language, this function needs to route by extension:

```python
from benchforge.plugins.base import get_plugins_for_extension

for file in scan_result.files:
    plugins = get_plugins_for_extension(file.suffix.lower())
    for plugin in plugins:
        issues = plugin.analyze(file)
        ...
```

The `get_plugins_for_extension()` helper already exists in `benchforge/plugins/base.py`. The routing logic just needs to be applied in `analyze_project()`.

This is tracked on the roadmap as the next infrastructure step before the first non-Python language ships.

---

## What Works Right Now vs. What Needs the Routing Fix

| Capability | Status |
|---|---|
| Plugin protocol (`AnalyzerPlugin`) | Ready |
| Plugin registry (`register_plugin`, `get_plugins`) | Ready |
| Extension routing helper (`get_plugins_for_extension`) | Ready |
| `Issue` dataclass (language-agnostic) | Ready |
| Scanner language detection (14 languages recognized) | Ready |
| `analyze_project()` routing to plugins | Not yet wired — requires the change above |
| Scoring for non-Python issue categories | Partial — existing categories work, new ones need scoring updates |

---

## Honest Constraints

**Static analysis tooling varies per language.**
Python gets `ast` and `radon` for free. Other languages may require external tools (tree-sitter, linters, compilers). Make sure any subprocess dependency is documented in `docs/DEV_SETUP.md` and listed in `requirements.txt` or a language-specific extras group.

**Complexity and maintainability metrics differ per language.**
The scoring engine expects `avg_complexity` and `avg_maintainability` values in the 0–100 range. If your language's tooling produces different scales, normalize them before returning. The scoring engine does not know what tool produced the number.

**Benchmark engine is Python-only.**
`benchforge benchmark .` uses `timeit` and `memory_profiler` to call Python functions directly. Benchmarking non-Python code is a separate problem and is out of scope for the plugin system at this stage.

---

## Questions

If you are building a plugin and have questions, open an issue on GitHub. The plugin contract is stable and the routing fix is the main infrastructure item on the near-term roadmap.
