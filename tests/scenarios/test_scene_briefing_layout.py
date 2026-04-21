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



def test_create_scene_briefing_layout_passes_place_dict_rows_with_avatar(monkeypatch):
    """Place dict rows should keep avatar payload in the Places column call path."""
    captured = []

    class _DummyFrame:
        def __init__(self, *_, **__):
            pass

        def pack(self, *_, **__):
            return None

    monkeypatch.setattr(subject.ctk, "CTkFrame", _DummyFrame)
    monkeypatch.setattr(subject, "_add_vertical_separator", lambda *_, **__: None)

    def _capture_column(_parent, *, title, lines, **kwargs):
        captured.append((title, lines, kwargs))

    monkeypatch.setattr(subject, "_create_column", _capture_column)

    avatar = object()
    place_rows = [{"line": "Clocktower", "avatar": avatar}]
    subject.create_scene_briefing_layout(
        _DummyFrame(),
        npc_names=["Nina"],
        place_names=place_rows,
        clue_lines=[],
        event_lines=[],
        palette={
            "surface_card": "#111",
            "muted_border": "#222",
            "muted_text": "#aaa",
            "text": "#fff",
            "accent": "#0bf",
        },
    )

    places_column = next(item for item in captured if item[0] == "Places")
    assert places_column[1] == place_rows



def test_create_scene_briefing_layout_keeps_plain_string_places_backward_compatible(monkeypatch):
    """Plain string place names should still flow to the Places column."""
    captured = []

    class _DummyFrame:
        def __init__(self, *_, **__):
            pass

        def pack(self, *_, **__):
            return None

    monkeypatch.setattr(subject.ctk, "CTkFrame", _DummyFrame)
    monkeypatch.setattr(subject, "_add_vertical_separator", lambda *_, **__: None)
    monkeypatch.setattr(
        subject,
        "_create_column",
        lambda _parent, *, title, lines, **kwargs: captured.append((title, lines)),
    )

    place_names = ["Harbor", "Undercity"]
    subject.create_scene_briefing_layout(
        _DummyFrame(),
        npc_names=[],
        place_names=place_names,
        clue_lines=[],
        event_lines=[],
        palette={
            "surface_card": "#111",
            "muted_border": "#222",
            "muted_text": "#aaa",
            "text": "#fff",
            "accent": "#0bf",
        },
    )

    assert next(lines for title, lines in captured if title == "Places") == place_names
