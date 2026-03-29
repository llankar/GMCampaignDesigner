from modules.ui.windows.ai_run_window.formatters import format_ai_response_for_humans


def test_format_ai_response_for_humans_pretty_prints_full_json() -> None:
    raw = '{"status":"ok","items":[1,2]}'

    formatted = format_ai_response_for_humans(raw)

    assert '"status": "ok"' in formatted
    assert '"items": [' in formatted


def test_format_ai_response_for_humans_pretty_prints_fenced_json_block() -> None:
    raw = "Result:\n```json\n{\"name\":\"Nova\"}\n```\nDone."

    formatted = format_ai_response_for_humans(raw)

    assert "Result:" in formatted
    assert '"name": "Nova"' in formatted
    assert "Done." in formatted


def test_format_ai_response_for_humans_preserves_plain_text() -> None:
    raw = "No JSON here"

    formatted = format_ai_response_for_humans(raw)

    assert formatted == raw
