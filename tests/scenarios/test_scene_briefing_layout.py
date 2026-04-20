"""Tests for scene briefing layout row normalization."""

from modules.scenarios.widgets import scene_briefing_layout as subject


def test_normalize_rows_accepts_dict_payload_with_avatar():
    """Verify that normalize rows preserves avatar payload for dict items."""
    avatar = object()
    rows = subject._normalize_rows([
        {"line": "  Aleksander   Lesnik  ", "avatar": avatar},
        "",
    ])

    assert rows == [{"line": "Aleksander Lesnik", "avatar": avatar}]


def test_normalize_rows_accepts_plain_strings_without_avatar():
    """Verify that normalize rows keeps plain string entries."""
    rows = subject._normalize_rows(["  Capitaine du navire "])

    assert rows == [{"line": "Capitaine du navire", "avatar": None}]
