"""BenchForge user configuration loader.

Reads an optional `.benchforge.toml` file from the project root.
All settings are optional — missing keys fall back to built-in defaults.

Example .benchforge.toml:
    [scoring.weights]
    performance     = 0.40
    maintainability = 0.35
    memory          = 0.25

    [scoring.penalties]
    nested_loop     = 10.0
    long_function   = 5.0
    unused_import   = 2.0
    high_complexity = 6.0
    duplicate_code  = 4.0

    [scoring.thresholds]
    cc_excellent    = 3.0
    cc_poor         = 15.0
    mi_excellent    = 90.0
    mi_poor         = 20.0
    runtime_fast_ms = 10.0
    runtime_slow_ms = 1000.0
    memory_small_mb = 5.0
    memory_large_mb = 200.0

    [ci]
    min_score = 60
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

CONFIG_FILENAME = ".benchforge.toml"

# ---------------------------------------------------------------------------
# TOML parser — stdlib (3.11+) with fallback to tomli
# ---------------------------------------------------------------------------

def _load_toml(path: Path) -> dict:
    """Parse a TOML file. Returns empty dict if TOML support is unavailable."""
    try:
        import tomllib  # Python 3.11+
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except ImportError:
        pass
    try:
        import tomli  # pip install tomli
        with open(path, "rb") as fh:
            return tomli.load(fh)
    except ImportError:
        return {}


# ---------------------------------------------------------------------------
# Config dataclass
# ---------------------------------------------------------------------------

@dataclass
class ScoringWeights:
    performance: float = 0.35
    maintainability: float = 0.40
    memory: float = 0.25

    def validate(self) -> None:
        total = self.performance + self.maintainability + self.memory
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"[scoring.weights] must sum to 1.0, got {total:.6f}. "
                f"Check your .benchforge.toml."
            )
        for name, val in [
            ("performance", self.performance),
            ("maintainability", self.maintainability),
            ("memory", self.memory),
        ]:
            if not (0.0 <= val <= 1.0):
                raise ValueError(
                    f"[scoring.weights.{name}] must be between 0.0 and 1.0, got {val}."
                )


@dataclass
class ScoringPenalties:
    nested_loop: float = 8.0
    long_function: float = 5.0
    unused_import: float = 2.0
    high_complexity: float = 6.0
    duplicate_code: float = 4.0

    def validate(self) -> None:
        for name, val in self.__dict__.items():
            if val < 0:
                raise ValueError(
                    f"[scoring.penalties.{name}] must be >= 0, got {val}."
                )


@dataclass
class ScoringThresholds:
    cc_excellent: float = 3.0
    cc_poor: float = 15.0
    mi_excellent: float = 90.0
    mi_poor: float = 20.0
    runtime_fast_ms: float = 10.0
    runtime_slow_ms: float = 1000.0
    memory_small_mb: float = 5.0
    memory_large_mb: float = 200.0

    def validate(self) -> None:
        if self.cc_excellent >= self.cc_poor:
            raise ValueError(
                f"[scoring.thresholds] cc_excellent ({self.cc_excellent}) "
                f"must be < cc_poor ({self.cc_poor})."
            )
        if self.mi_poor >= self.mi_excellent:
            raise ValueError(
                f"[scoring.thresholds] mi_poor ({self.mi_poor}) "
                f"must be < mi_excellent ({self.mi_excellent})."
            )
        if self.runtime_fast_ms >= self.runtime_slow_ms:
            raise ValueError(
                f"[scoring.thresholds] runtime_fast_ms ({self.runtime_fast_ms}) "
                f"must be < runtime_slow_ms ({self.runtime_slow_ms})."
            )
        if self.memory_small_mb >= self.memory_large_mb:
            raise ValueError(
                f"[scoring.thresholds] memory_small_mb ({self.memory_small_mb}) "
                f"must be < memory_large_mb ({self.memory_large_mb})."
            )


@dataclass
class CiConfig:
    min_score: int = 60

    def validate(self) -> None:
        if not (0 <= self.min_score <= 100):
            raise ValueError(
                f"[ci.min_score] must be between 0 and 100, got {self.min_score}."
            )


@dataclass
class BenchForgeConfig:
    weights: ScoringWeights = field(default_factory=ScoringWeights)
    penalties: ScoringPenalties = field(default_factory=ScoringPenalties)
    thresholds: ScoringThresholds = field(default_factory=ScoringThresholds)
    ci: CiConfig = field(default_factory=CiConfig)
    config_path: Path | None = None  # None = using built-in defaults

    def validate(self) -> None:
        self.weights.validate()
        self.penalties.validate()
        self.thresholds.validate()
        self.ci.validate()


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(project_root: Path) -> BenchForgeConfig:
    """Load .benchforge.toml from project_root if it exists.

    Returns BenchForgeConfig with built-in defaults if the file is absent
    or TOML support is unavailable. Raises ValueError on invalid values.

    Args:
        project_root: Directory to search for .benchforge.toml.

    Returns:
        BenchForgeConfig instance (validated).
    """
    config_file = project_root / CONFIG_FILENAME

    if not config_file.exists():
        return BenchForgeConfig()

    raw = _load_toml(config_file)
    if not raw:
        # File exists but TOML not parseable (no tomllib/tomli) — use defaults
        return BenchForgeConfig()

    scoring_raw = raw.get("scoring", {})
    weights_raw = scoring_raw.get("weights", {})
    penalties_raw = scoring_raw.get("penalties", {})
    thresholds_raw = scoring_raw.get("thresholds", {})
    ci_raw = raw.get("ci", {})

    weights = ScoringWeights(
        performance=float(weights_raw.get("performance", ScoringWeights.performance)),
        maintainability=float(weights_raw.get("maintainability", ScoringWeights.maintainability)),
        memory=float(weights_raw.get("memory", ScoringWeights.memory)),
    )
    penalties = ScoringPenalties(
        nested_loop=float(penalties_raw.get("nested_loop", ScoringPenalties.nested_loop)),
        long_function=float(penalties_raw.get("long_function", ScoringPenalties.long_function)),
        unused_import=float(penalties_raw.get("unused_import", ScoringPenalties.unused_import)),
        high_complexity=float(penalties_raw.get("high_complexity", ScoringPenalties.high_complexity)),
        duplicate_code=float(penalties_raw.get("duplicate_code", ScoringPenalties.duplicate_code)),
    )
    thresholds = ScoringThresholds(
        cc_excellent=float(thresholds_raw.get("cc_excellent", ScoringThresholds.cc_excellent)),
        cc_poor=float(thresholds_raw.get("cc_poor", ScoringThresholds.cc_poor)),
        mi_excellent=float(thresholds_raw.get("mi_excellent", ScoringThresholds.mi_excellent)),
        mi_poor=float(thresholds_raw.get("mi_poor", ScoringThresholds.mi_poor)),
        runtime_fast_ms=float(thresholds_raw.get("runtime_fast_ms", ScoringThresholds.runtime_fast_ms)),
        runtime_slow_ms=float(thresholds_raw.get("runtime_slow_ms", ScoringThresholds.runtime_slow_ms)),
        memory_small_mb=float(thresholds_raw.get("memory_small_mb", ScoringThresholds.memory_small_mb)),
        memory_large_mb=float(thresholds_raw.get("memory_large_mb", ScoringThresholds.memory_large_mb)),
    )

    ci = CiConfig(
        min_score=int(ci_raw.get("min_score", CiConfig.min_score)),
    )

    cfg = BenchForgeConfig(
        weights=weights,
        penalties=penalties,
        thresholds=thresholds,
        ci=ci,
        config_path=config_file,
    )
    cfg.validate()
    return cfg
