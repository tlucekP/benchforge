"""Tests for benchforge.ai.interpreter.

Strategy: test without real API calls.
  - Test _is_available() logic
  - Test _build_prompt() output structure
  - Test _parse_response() parsing
  - Test interpret() returns None when key not set
  - Test interpret() handles API errors gracefully
  - Test AIInsight dataclass structure
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from benchforge.ai.interpreter import (
    AIInsight,
    _build_prompt,
    _is_available,
    _parse_response,
    interpret,
    MISTRAL_MODEL,
)
from benchforge.core.analyzer import analyze_project
from benchforge.core.scanner import scan_project
from benchforge.core.scoring import compute_score
from benchforge.report.html_report import build_report_data


def _make_report_data(project_path: Path):
    scan = scan_project(project_path)
    analysis = analyze_project(scan)
    score = compute_score(analysis)
    scan_summary = {
        "file_count": scan.file_count,
        "primary_language": scan.primary_language,
        "total_size_kb": scan.total_size_kb,
        "modules": scan.modules,
        "languages": scan.languages,
    }
    return build_report_data(
        project_path=project_path,
        scan_summary=scan_summary,
        analysis=analysis,
        score=score,
    )


class TestIsAvailable:
    def test_returns_false_without_key(self, monkeypatch) -> None:
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        assert _is_available() is False

    def test_returns_false_with_empty_key(self, monkeypatch) -> None:
        monkeypatch.setenv("MISTRAL_API_KEY", "")
        assert _is_available() is False

    def test_returns_false_with_whitespace_key(self, monkeypatch) -> None:
        monkeypatch.setenv("MISTRAL_API_KEY", "   ")
        assert _is_available() is False

    def test_returns_true_with_key(self, monkeypatch) -> None:
        monkeypatch.setenv("MISTRAL_API_KEY", "test-key-123")
        assert _is_available() is True


class TestBuildPrompt:
    def test_returns_string(self, single_file_project: Path) -> None:
        data = _make_report_data(single_file_project)
        prompt = _build_prompt(data)
        assert isinstance(prompt, str)

    def test_contains_scores(self, single_file_project: Path) -> None:
        data = _make_report_data(single_file_project)
        prompt = _build_prompt(data)
        assert "Performance" in prompt
        assert "Maintainability" in prompt

    def test_contains_file_count(self, single_file_project: Path) -> None:
        data = _make_report_data(single_file_project)
        prompt = _build_prompt(data)
        assert str(data.scan_summary["file_count"]) in prompt

    def test_no_raw_source_code(self, fixtures_dir: Path) -> None:
        """Prompt must not contain raw source file content."""
        data = _make_report_data(fixtures_dir)
        prompt = _build_prompt(data)
        # The prompt should NOT contain Python syntax from the fixture files
        assert "def find_duplicates" not in prompt
        assert "import os" not in prompt

    def test_caps_issues_in_prompt(self, fixtures_dir: Path) -> None:
        """Prompt should cap number of issues to avoid token overflow."""
        data = _make_report_data(fixtures_dir)
        prompt = _build_prompt(data)
        assert isinstance(prompt, str)
        assert len(prompt) < 5000  # reasonable upper bound


class TestParseResponse:
    def test_parses_well_formed_response(self) -> None:
        text = (
            "SUMMARY: The code has some issues.\n"
            "INSIGHTS:\n"
            "nested_loop: Use a dict lookup instead.\n"
            "long_function: Split into smaller functions.\n"
            "TOP SUGGESTION: Refactor the nested loop first.\n"
        )
        summary, insights, top = _parse_response(text)
        assert "issues" in summary
        assert len(insights) == 2
        assert "nested_loop" in insights[0]
        assert "Refactor" in top

    def test_handles_empty_response(self) -> None:
        summary, insights, top = _parse_response("")
        assert isinstance(summary, str)
        assert isinstance(insights, list)
        assert isinstance(top, str)

    def test_handles_malformed_response(self) -> None:
        """Parser must not raise on unexpected format."""
        summary, insights, top = _parse_response("This is just plain text with no structure.")
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_insights_are_list(self) -> None:
        text = "SUMMARY: ok\nINSIGHTS:\nfoo: bar\nTOP SUGGESTION: do something"
        _, insights, _ = _parse_response(text)
        assert isinstance(insights, list)


mistralai = pytest.importorskip("mistralai", reason="mistralai not installed (optional dependency)")


class TestInterpret:
    def test_returns_none_without_api_key(
        self, monkeypatch, single_file_project: Path
    ) -> None:
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        data = _make_report_data(single_file_project)
        result = interpret(data)
        assert result is None

    def test_returns_ai_insight_on_success(
        self, monkeypatch, single_file_project: Path
    ) -> None:
        monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")

        mock_response_text = (
            "SUMMARY: The project looks well structured.\n"
            "INSIGHTS:\n"
            "nested_loop: Replace with dict.\n"
            "TOP SUGGESTION: Fix the nested loop.\n"
        )

        mock_choice = MagicMock()
        mock_choice.message.content = mock_response_text
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.complete.return_value = mock_response

        with patch("mistralai.Mistral", return_value=mock_client):
            data = _make_report_data(single_file_project)
            result = interpret(data)

        assert result is not None
        assert isinstance(result, AIInsight)
        assert result.available is True
        assert result.model == MISTRAL_MODEL

    def test_returns_insight_with_error_on_api_failure(
        self, monkeypatch, single_file_project: Path
    ) -> None:
        monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")

        mock_client = MagicMock()
        mock_client.chat.complete.side_effect = ConnectionError("timeout")

        with patch("mistralai.Mistral", return_value=mock_client):
            data = _make_report_data(single_file_project)
            result = interpret(data)

        assert result is not None
        assert result.available is False
        assert "ConnectionError" in result.summary

    def test_insight_structure(
        self, monkeypatch, single_file_project: Path
    ) -> None:
        monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")

        mock_choice = MagicMock()
        mock_choice.message.content = (
            "SUMMARY: Good code.\nINSIGHTS:\nfoo: bar\nTOP SUGGESTION: Do foo.\n"
        )
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.complete.return_value = mock_response

        with patch("mistralai.Mistral", return_value=mock_client):
            data = _make_report_data(single_file_project)
            result = interpret(data)

        assert result is not None
        assert isinstance(result.summary, str)
        assert isinstance(result.issue_insights, list)
        assert isinstance(result.top_suggestion, str)
        assert isinstance(result.model, str)
        assert isinstance(result.available, bool)
