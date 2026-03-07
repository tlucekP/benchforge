"""Benchmark engine — measures runtime and memory of Python callables.

SECURITY BOUNDARY: This module executes user-provided callables.
It must NEVER be called automatically during static analysis.
Only invoke explicitly via the `benchforge benchmark` CLI command.

The caller is responsible for importing and passing safe, known functions.
"""

from __future__ import annotations

import cProfile
import io
import pstats
import timeit
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class FunctionBenchmark:
    """Benchmark result for a single callable."""

    name: str
    mean_runtime_ms: float      # mean execution time in milliseconds
    min_runtime_ms: float
    max_runtime_ms: float
    peak_memory_mb: float       # peak memory usage in megabytes (0.0 if unavailable)
    profile_summary: str        # top N lines from cProfile output
    runs: int
    error: str | None = None    # set if benchmarking failed


@dataclass
class BenchmarkResult:
    """Aggregated benchmark results for a set of functions."""

    functions: list[FunctionBenchmark] = field(default_factory=list)
    total_functions_benchmarked: int = 0
    errors: list[str] = field(default_factory=list)


def _run_timeit(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    runs: int,
) -> tuple[float, float, float]:
    """Run timeit and return (mean_ms, min_ms, max_ms)."""
    timer = timeit.Timer(lambda: func(*args, **kwargs))
    # Warm-up run to avoid JIT/import skew
    try:
        timer.timeit(number=1)
    except Exception:
        pass

    times_sec = timer.repeat(repeat=runs, number=1)
    times_ms = [t * 1000 for t in times_sec]
    mean_ms = round(sum(times_ms) / len(times_ms), 4)
    min_ms = round(min(times_ms), 4)
    max_ms = round(max(times_ms), 4)
    return mean_ms, min_ms, max_ms


def _run_cprofile(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    top_n: int = 10,
) -> str:
    """Run cProfile and return a compact text summary of the top N calls."""
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        func(*args, **kwargs)
    finally:
        profiler.disable()

    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats("cumulative")
    stats.print_stats(top_n)
    return stream.getvalue()


def _measure_memory(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> float:
    """Measure peak memory usage in MB. Returns 0.0 if memory_profiler is unavailable."""
    try:
        from memory_profiler import memory_usage  # type: ignore[import]

        mem: list[float] = memory_usage(
            (func, args, kwargs),
            interval=0.01,
            timeout=30,
            retval=False,
        )
        if mem:
            return round(max(mem) - min(mem), 4)
        return 0.0
    except ImportError:
        return 0.0
    except Exception:
        return 0.0


def benchmark_function(
    func: Callable[..., Any],
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
    runs: int = 5,
    measure_memory: bool = True,
) -> FunctionBenchmark:
    """Benchmark a single callable.

    Args:
        func: The callable to benchmark.
        args: Positional arguments to pass to the callable.
        kwargs: Keyword arguments to pass to the callable.
        runs: Number of timed repetitions for timeit.
        measure_memory: Whether to measure peak memory delta.

    Returns:
        FunctionBenchmark with timing and memory metrics.
    """
    if kwargs is None:
        kwargs = {}

    name = getattr(func, "__qualname__", getattr(func, "__name__", repr(func)))

    try:
        mean_ms, min_ms, max_ms = _run_timeit(func, args, kwargs, runs)
    except Exception as exc:
        return FunctionBenchmark(
            name=name,
            mean_runtime_ms=0.0,
            min_runtime_ms=0.0,
            max_runtime_ms=0.0,
            peak_memory_mb=0.0,
            profile_summary="",
            runs=runs,
            error=f"timeit failed: {exc}",
        )

    try:
        profile_summary = _run_cprofile(func, args, kwargs)
    except Exception:
        profile_summary = "(profiling unavailable)"

    peak_memory_mb = _measure_memory(func, args, kwargs) if measure_memory else 0.0

    return FunctionBenchmark(
        name=name,
        mean_runtime_ms=mean_ms,
        min_runtime_ms=min_ms,
        max_runtime_ms=max_ms,
        peak_memory_mb=peak_memory_mb,
        profile_summary=profile_summary,
        runs=runs,
    )


def benchmark_callables(
    callables: list[tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]]],
    runs: int = 5,
    measure_memory: bool = True,
) -> BenchmarkResult:
    """Benchmark a list of callables.

    Args:
        callables: List of (func, args, kwargs) tuples.
        runs: Timeit repetitions per function.
        measure_memory: Whether to profile memory.

    Returns:
        BenchmarkResult with per-function metrics.
    """
    result = BenchmarkResult()

    for func, args, kwargs in callables:
        fb = benchmark_function(func, args, kwargs, runs=runs, measure_memory=measure_memory)
        result.functions.append(fb)
        if fb.error:
            result.errors.append(f"{fb.name}: {fb.error}")

    result.total_functions_benchmarked = len(result.functions)
    return result


def benchmark_file(path: Path, runs: int = 5) -> BenchmarkResult:
    """Discover and benchmark top-level functions in a Python file.

    SECURITY NOTE: This imports and executes code from the given file.
    Only call with trusted, known files.

    Args:
        path: Path to a Python source file.
        runs: Timeit repetitions per function.

    Returns:
        BenchmarkResult, possibly with errors for non-importable files.
    """
    import importlib.util
    import inspect

    result = BenchmarkResult()

    if not path.exists() or not path.is_file():
        result.errors.append(f"File not found: {path}")
        return result

    if path.suffix.lower() != ".py":
        result.errors.append(f"Not a Python file: {path}")
        return result

    try:
        spec = importlib.util.spec_from_file_location("_benchforge_target", path)
        if spec is None or spec.loader is None:
            result.errors.append(f"Cannot load module spec for: {path}")
            return result

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except Exception as exc:
        result.errors.append(f"Import error for {path.name}: {exc}")
        return result

    callables: list[tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]]] = []
    for name, obj in inspect.getmembers(module, inspect.isfunction):
        # Only benchmark functions defined in this module (not imported ones)
        if getattr(obj, "__module__", None) == "_benchforge_target":
            try:
                sig = inspect.signature(obj)
                # Only benchmark zero-argument functions automatically
                params = [
                    p for p in sig.parameters.values()
                    if p.default is inspect.Parameter.empty
                ]
                if not params:
                    callables.append((obj, (), {}))
            except (ValueError, TypeError):
                continue

    if not callables:
        result.errors.append(
            f"No zero-argument functions found in {path.name} — "
            "provide explicit callables via benchmark_callables()."
        )
        return result

    for func, args, kwargs in callables:
        fb = benchmark_function(func, args, kwargs, runs=runs, measure_memory=True)
        result.functions.append(fb)
        if fb.error:
            result.errors.append(f"{fb.name}: {fb.error}")

    result.total_functions_benchmarked = len(result.functions)
    return result
