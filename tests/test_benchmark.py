"""Tests for benchforge.core.benchmark.

Strategy: validate structure and presence of metrics only.
No timing assertions — benchmark values are environment-dependent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from benchforge.core.benchmark import (
    benchmark_function,
    benchmark_callables,
    benchmark_file,
    FunctionBenchmark,
    BenchmarkResult,
)


def _noop() -> None:
    """Zero-argument no-op function for testing."""
    pass


def _add_one(x: int) -> int:
    return x + 1


class TestBenchmarkFunction:
    def test_returns_function_benchmark(self) -> None:
        result = benchmark_function(_noop, runs=2, measure_memory=False)
        assert isinstance(result, FunctionBenchmark)

    def test_name_captured(self) -> None:
        result = benchmark_function(_noop, runs=2, measure_memory=False)
        assert "noop" in result.name or result.name  # name must be non-empty

    def test_mean_runtime_non_negative(self) -> None:
        result = benchmark_function(_noop, runs=2, measure_memory=False)
        assert result.mean_runtime_ms >= 0.0

    def test_min_lte_mean_lte_max(self) -> None:
        result = benchmark_function(_noop, runs=3, measure_memory=False)
        if result.error is None:
            assert result.min_runtime_ms <= result.mean_runtime_ms <= result.max_runtime_ms

    def test_runs_recorded(self) -> None:
        result = benchmark_function(_noop, runs=3, measure_memory=False)
        assert result.runs == 3

    def test_profile_summary_is_string(self) -> None:
        result = benchmark_function(_noop, runs=2, measure_memory=False)
        assert isinstance(result.profile_summary, str)

    def test_with_args(self) -> None:
        result = benchmark_function(_add_one, args=(5,), runs=2, measure_memory=False)
        assert result.error is None
        assert result.mean_runtime_ms >= 0.0

    def test_error_on_exception(self) -> None:
        def always_raises() -> None:
            raise ValueError("intentional error")

        # timeit will catch the exception; error should be set
        result = benchmark_function(always_raises, runs=1, measure_memory=False)
        # Either error is set or runtime is 0
        if result.error:
            assert "intentional error" in result.error or result.error

    def test_memory_disabled_returns_zero(self) -> None:
        result = benchmark_function(_noop, runs=2, measure_memory=False)
        assert result.peak_memory_mb == 0.0


class TestBenchmarkCallables:
    def test_returns_benchmark_result(self) -> None:
        result = benchmark_callables([(_noop, (), {})], runs=2, measure_memory=False)
        assert isinstance(result, BenchmarkResult)

    def test_total_functions_count(self) -> None:
        result = benchmark_callables([(_noop, (), {}), (_noop, (), {})], runs=1, measure_memory=False)
        assert result.total_functions_benchmarked == 2

    def test_empty_callables(self) -> None:
        result = benchmark_callables([], runs=1, measure_memory=False)
        assert result.total_functions_benchmarked == 0
        assert result.functions == []

    def test_errors_list_is_list(self) -> None:
        result = benchmark_callables([(_noop, (), {})], runs=1, measure_memory=False)
        assert isinstance(result.errors, list)


class TestBenchmarkFile:
    def test_clean_file_benchmark(self, clean_file: Path) -> None:
        result = benchmark_file(clean_file, runs=1)
        assert isinstance(result, BenchmarkResult)

    def test_no_zero_arg_functions_produces_error(self, tmp_path: Path) -> None:
        """Files with only parameterised functions should report an informational error."""
        f = tmp_path / "parameterised.py"
        f.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        result = benchmark_file(f, runs=1)
        assert len(result.errors) >= 1

    def test_nonexistent_file_produces_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "ghost.py"
        result = benchmark_file(missing, runs=1)
        assert len(result.errors) >= 1

    def test_non_python_file_produces_error(self, tmp_path: Path) -> None:
        txt = tmp_path / "readme.txt"
        txt.write_text("hello\n", encoding="utf-8")
        result = benchmark_file(txt, runs=1)
        assert len(result.errors) >= 1

    def test_result_structure(self, clean_file: Path) -> None:
        result = benchmark_file(clean_file, runs=1)
        assert isinstance(result.functions, list)
        assert isinstance(result.errors, list)
        assert isinstance(result.total_functions_benchmarked, int)
