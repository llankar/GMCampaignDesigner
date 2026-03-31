"""Regression tests for AI prompt text formatter."""

from modules.ui.windows.ai_run_window.formatters import format_ai_prompt_for_humans


def test_format_ai_prompt_for_humans_formats_roles_and_headers() -> None:
    """Verify that format AI prompt for humans formats roles and headers."""
    raw = "[1:system]\nYou are helpful\n\n[2:user]\nTell me a story"

    formatted = format_ai_prompt_for_humans(raw)

    assert "Message 1 — SYSTEM" in formatted
    assert "Message 2 — USER" in formatted
    assert "You are helpful" in formatted
    assert "Tell me a story" in formatted


def test_format_ai_prompt_for_humans_pretty_prints_json_message_content() -> None:
    """Verify that format AI prompt for humans pretty prints JSON message content."""
    raw = '[1:user]\n{"name":"Nova","traits":["brave","curious"]}'

    formatted = format_ai_prompt_for_humans(raw)

    assert '"name": "Nova"' in formatted
    assert '"traits": [' in formatted
    assert '"brave"' in formatted


def test_format_ai_prompt_for_humans_returns_raw_when_not_serialized() -> None:
    """Verify that format AI prompt for humans returns raw when not serialized."""
    raw = "Just plain text"

    formatted = format_ai_prompt_for_humans(raw)

    assert formatted == raw
