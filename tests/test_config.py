"""Tests for benchforge.core.config — .benchforge.toml loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from benchforge.core.config import (
    BenchForgeConfig,
    ScoringWeights,
    ScoringPenalties,
    ScoringThresholds,
    load_config,
    CONFIG_FILENAME,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_toml(directory: Path, content: str) -> Path:
    cfg = directory / CONFIG_FILENAME
    cfg.write_text(content, encoding="utf-8")
    return cfg


# ---------------------------------------------------------------------------
# Default config (no file)
# ---------------------------------------------------------------------------

class TestDefaultConfig:
    def test_load_config_no_file_returns_defaults(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path)
        assert isinstance(cfg, BenchForgeConfig)

    def test_default_weights_sum_to_one(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path)
        total = cfg.weights.performance + cfg.weights.maintainability + cfg.weights.memory
        assert abs(total - 1.0) < 1e-6

    def test_default_config_path_is_none(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path)
        assert cfg.config_path is None

    def test_default_weights_values(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path)
        assert cfg.weights.performance == pytest.approx(0.35)
        assert cfg.weights.maintainability == pytest.approx(0.40)
        assert cfg.weights.memory == pytest.approx(0.25)

    def test_default_penalties_values(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path)
        assert cfg.penalties.nested_loop == pytest.approx(8.0)
        assert cfg.penalties.long_function == pytest.approx(5.0)

    def test_default_thresholds_values(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path)
        assert cfg.thresholds.cc_excellent == pytest.approx(3.0)
        assert cfg.thresholds.runtime_fast_ms == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# Loading from file
# ---------------------------------------------------------------------------

class TestLoadFromFile:
    def test_config_path_set_when_file_exists(self, tmp_path: Path) -> None:
        _write_toml(tmp_path, "[scoring.weights]\nperformance = 0.35\nmaintainability = 0.40\nmemory = 0.25\n")
        cfg = load_config(tmp_path)
        assert cfg.config_path is not None
        assert cfg.config_path.name == CONFIG_FILENAME

    def test_custom_weights_loaded(self, tmp_path: Path) -> None:
        _write_toml(tmp_path, "[scoring.weights]\nperformance = 0.50\nmaintainability = 0.30\nmemory = 0.20\n")
        cfg = load_config(tmp_path)
        assert cfg.weights.performance == pytest.approx(0.50)
        assert cfg.weights.maintainability == pytest.approx(0.30)
        assert cfg.weights.memory == pytest.approx(0.20)

    def test_custom_penalties_loaded(self, tmp_path: Path) -> None:
        _write_toml(tmp_path, "[scoring.penalties]\nnested_loop = 12.0\nlong_function = 3.0\n")
        cfg = load_config(tmp_path)
        assert cfg.penalties.nested_loop == pytest.approx(12.0)
        assert cfg.penalties.long_function == pytest.approx(3.0)
        # Unspecified keys fall back to defaults
        assert cfg.penalties.unused_import == pytest.approx(2.0)

    def test_custom_thresholds_loaded(self, tmp_path: Path) -> None:
        _write_toml(tmp_path, "[scoring.thresholds]\ncc_excellent = 2.0\ncc_poor = 20.0\n")
        cfg = load_config(tmp_path)
        assert cfg.thresholds.cc_excellent == pytest.approx(2.0)
        assert cfg.thresholds.cc_poor == pytest.approx(20.0)

    def test_partial_section_uses_defaults_for_rest(self, tmp_path: Path) -> None:
        _write_toml(tmp_path, "[scoring.weights]\nperformance = 0.35\nmaintainability = 0.40\nmemory = 0.25\n")
        cfg = load_config(tmp_path)
        # Thresholds not specified — must still be defaults
        assert cfg.thresholds.runtime_fast_ms == pytest.approx(10.0)

    def test_empty_file_returns_defaults(self, tmp_path: Path) -> None:
        _write_toml(tmp_path, "")
        cfg = load_config(tmp_path)
        assert cfg.weights.performance == pytest.approx(0.35)


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

class TestValidation:
    def test_weights_not_summing_to_one_raises(self, tmp_path: Path) -> None:
        _write_toml(tmp_path, "[scoring.weights]\nperformance = 0.50\nmaintainability = 0.50\nmemory = 0.50\n")
        with pytest.raises(ValueError, match="sum to 1.0"):
            load_config(tmp_path)

    def test_weight_out_of_range_raises(self, tmp_path: Path) -> None:
        _write_toml(tmp_path, "[scoring.weights]\nperformance = -0.1\nmaintainability = 0.60\nmemory = 0.50\n")
        with pytest.raises(ValueError):
            load_config(tmp_path)

    def test_negative_penalty_raises(self, tmp_path: Path) -> None:
        _write_toml(tmp_path, "[scoring.penalties]\nnested_loop = -5.0\n")
        with pytest.raises(ValueError, match=">="):
            load_config(tmp_path)

    def test_cc_excellent_gte_cc_poor_raises(self, tmp_path: Path) -> None:
        _write_toml(tmp_path, "[scoring.thresholds]\ncc_excellent = 20.0\ncc_poor = 5.0\n")
        with pytest.raises(ValueError, match="cc_excellent"):
            load_config(tmp_path)

    def test_runtime_fast_gte_slow_raises(self, tmp_path: Path) -> None:
        _write_toml(tmp_path, "[scoring.thresholds]\nruntime_fast_ms = 1000.0\nruntime_slow_ms = 10.0\n")
        with pytest.raises(ValueError, match="runtime_fast_ms"):
            load_config(tmp_path)


# ---------------------------------------------------------------------------
# ScoringWeights standalone validation
# ---------------------------------------------------------------------------

class TestScoringWeightsValidation:
    def test_valid_weights_do_not_raise(self) -> None:
        w = ScoringWeights(performance=0.4, maintainability=0.4, memory=0.2)
        w.validate()  # must not raise

    def test_invalid_sum_raises(self) -> None:
        w = ScoringWeights(performance=0.5, maintainability=0.5, memory=0.5)
        with pytest.raises(ValueError):
            w.validate()
