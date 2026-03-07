"""Tests for benchforge.core.badge and the `benchforge badge` CLI command."""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from click.testing import CliRunner

from benchforge.cli.main import cli
from benchforge.core.badge import BadgeResult, generate_badge
from benchforge.core.scanner import scan_project
from benchforge.core.analyzer import analyze_project
from benchforge.core.scoring import compute_score


CLEAN_CODE = """\
def add(a: int, b: int) -> int:
    return a + b

def greet(name: str) -> str:
    return f"Hello, {name}!"
"""


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def clean_project(tmp_path: Path) -> Path:
    project = tmp_path / "clean"
    project.mkdir()
    (project / "main.py").write_text(CLEAN_CODE, encoding="utf-8")
    return project


class TestBadgeColors:
    @pytest.mark.parametrize(
        ("score", "color"),
        [
            (100, "brightgreen"),
            (80, "brightgreen"),
            (79, "yellow"),
            (60, "yellow"),
            (59, "orange"),
            (40, "orange"),
            (39, "red"),
            (0, "red"),
        ],
    )
    def test_color_thresholds(self, score: int, color: str) -> None:
        badge = generate_badge(score)
        assert badge.color == color


class TestGenerateBadge:
    def test_returns_badge_result(self) -> None:
        badge = generate_badge(78)
        assert isinstance(badge, BadgeResult)

    def test_svg_is_string(self) -> None:
        badge = generate_badge(78)
        assert isinstance(badge.svg, str)

    def test_svg_contains_svg_tag(self) -> None:
        badge = generate_badge(78)
        assert badge.svg.startswith("<svg")

    def test_svg_contains_score_text(self) -> None:
        badge = generate_badge(78)
        assert "78/100" in badge.svg

    def test_svg_contains_label(self) -> None:
        badge = generate_badge(78, label="code quality")
        assert "code quality" in badge.svg

    def test_default_label_is_benchforge(self) -> None:
        badge = generate_badge(78)
        assert badge.label == "BenchForge"

    def test_blank_label_falls_back_to_default(self) -> None:
        badge = generate_badge(78, label="   ")
        assert badge.label == "BenchForge"

    def test_score_is_clamped_high(self) -> None:
        badge = generate_badge(150)
        assert badge.score == 100

    def test_score_is_clamped_low(self) -> None:
        badge = generate_badge(-5)
        assert badge.score == 0

    def test_svg_is_valid_xml(self) -> None:
        badge = generate_badge(78)
        root = ET.fromstring(badge.svg)
        assert root.tag.endswith("svg")

    def test_label_is_escaped(self) -> None:
        badge = generate_badge(78, label='x < y & "z"')
        assert "x &lt; y &amp; &quot;z&quot;" in badge.svg

    def test_invalid_style_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported badge style"):
            generate_badge(78, style="unknown")


class TestBadgeStyles:
    def test_flat_style_selected(self) -> None:
        badge = generate_badge(78, style="flat")
        assert badge.style == "flat"

    def test_flat_square_style_selected(self) -> None:
        badge = generate_badge(78, style="flat-square")
        assert badge.style == "flat-square"

    def test_plastic_style_selected(self) -> None:
        badge = generate_badge(78, style="plastic")
        assert badge.style == "plastic"

    def test_each_style_returns_different_svg(self) -> None:
        flat = generate_badge(78, style="flat").svg
        square = generate_badge(78, style="flat-square").svg
        plastic = generate_badge(78, style="plastic").svg
        assert len({flat, square, plastic}) == 3

    def test_plastic_contains_gradient(self) -> None:
        badge = generate_badge(78, style="plastic")
        assert "linearGradient" in badge.svg

    def test_flat_square_differs_from_flat_geometry(self) -> None:
        flat = generate_badge(78, style="flat").svg
        square = generate_badge(78, style="flat-square").svg
        assert 'fill="#555"' in flat
        assert 'fill="#444"' in square


class TestCliBadge:
    def test_stdout_outputs_svg(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["badge", str(clean_project)])
        assert result.exit_code == 0
        assert "<svg" in result.output

    def test_stdout_contains_score(self, runner: CliRunner, clean_project: Path) -> None:
        scan = scan_project(clean_project)
        analysis = analyze_project(scan)
        score = compute_score(analysis)
        result = runner.invoke(cli, ["badge", str(clean_project)])
        assert result.exit_code == 0
        assert f"{score.benchforge_score}/100" in result.output

    def test_output_writes_file(self, runner: CliRunner, clean_project: Path, tmp_path: Path) -> None:
        output = tmp_path / "badge.svg"
        result = runner.invoke(cli, ["badge", str(clean_project), "--output", str(output)])
        assert result.exit_code == 0
        assert output.exists()

    def test_output_file_contains_svg(self, runner: CliRunner, clean_project: Path, tmp_path: Path) -> None:
        output = tmp_path / "badge.svg"
        runner.invoke(cli, ["badge", str(clean_project), "--output", str(output)])
        assert output.read_text(encoding="utf-8").startswith("<svg")

    def test_custom_label_propagates(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["badge", str(clean_project), "--label", "code quality"])
        assert result.exit_code == 0
        assert "code quality" in result.output

    def test_custom_style_propagates(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["badge", str(clean_project), "--style", "plastic"])
        assert result.exit_code == 0
        assert "linearGradient" in result.output

    def test_json_output_is_valid(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["badge", str(clean_project), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "svg" in data

    def test_json_contains_expected_fields(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["badge", str(clean_project), "--format", "json"])
        data = json.loads(result.output)
        for key in ("score", "label", "style", "color", "svg"):
            assert key in data

    def test_json_svg_contains_svg_tag(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(cli, ["badge", str(clean_project), "--format", "json"])
        data = json.loads(result.output)
        assert data["svg"].startswith("<svg")

    def test_json_honors_label_and_style(self, runner: CliRunner, clean_project: Path) -> None:
        result = runner.invoke(
            cli,
            ["badge", str(clean_project), "--format", "json", "--label", "code quality", "--style", "flat-square"],
        )
        data = json.loads(result.output)
        assert data["label"] == "code quality"
        assert data["style"] == "flat-square"

    def test_invalid_path_exit_nonzero(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(cli, ["badge", str(tmp_path / "missing")])
        assert result.exit_code != 0
