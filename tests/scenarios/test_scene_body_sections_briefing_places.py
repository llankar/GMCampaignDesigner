"""Tests ensuring place avatars are attached for scene briefing data."""

from __future__ import annotations

from types import SimpleNamespace

from modules.scenarios.widgets import scene_body_sections as subject


class _DummyWidget:
    """Tiny stand-in for CTk widgets."""

    def __init__(self, *_, **__):
        self._children = []
        self.config = {}

    def pack(self, *_, **__):
        return None

    def grid(self, *_, **__):
        return None

    def grid_columnconfigure(self, *_, **__):
        return None

    def pack_forget(self, *_, **__):
        return None

    def bind(self, *_, **__):
        return None

    def configure(self, **kwargs):
        self.config.update(kwargs)

    def winfo_width(self):
        return 500

    def winfo_children(self):
        return list(self._children)

    def destroy(self):
        return None


class _DummyBoolVar:
    """Simple bool var for toggles in tests."""

    def __init__(self, master=None, value=False):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _patch_minimal_ctk(monkeypatch):
    dummy_ctk = SimpleNamespace(
        CTkFrame=_DummyWidget,
        CTkLabel=_DummyWidget,
        CTkButton=_DummyWidget,
        CTkFont=lambda *a, **k: None,
        BooleanVar=_DummyBoolVar,
    )
    monkeypatch.setattr(subject, "ctk", dummy_ctk)


def test_create_description_block_attaches_place_avatars_for_briefing(monkeypatch):
    """Scene briefing data should call attach avatars for Places in description block."""
    _patch_minimal_ctk(monkeypatch)

    monkeypatch.setattr(
        subject,
        "parse_scene_sections_with_structured_fallback",
        lambda *_a, **_k: {
            "has_sections": True,
            "intro_text": "Intro",
            "sections": [{"key": "clues/hooks", "title": "Clues", "items": ["clue"]}],
        },
    )

    calls = []

    def _fake_attach(group, rows, _gm_view_ref):
        calls.append((group, rows))
        return rows

    monkeypatch.setattr(subject, "attach_entity_avatars", _fake_attach)

    captured_brief = {}

    def _fake_briefing_layout(_parent, **kwargs):
        captured_brief.update(kwargs)
        return _DummyWidget()

    monkeypatch.setattr(subject, "create_scene_briefing_layout", _fake_briefing_layout)

    subject._create_description_block(
        _DummyWidget(),
        "Body",
        scene_dict={"SceneLocations": ["Dock 9"], "SceneNPCs": ["Ilya"]},
        npc_names=["Nina"],
        place_names=["Old Quarter"],
        gm_view_ref=object(),
    )

    called_groups = [group for group, _rows in calls]
    assert "NPCs" in called_groups
    assert "Places" in called_groups

    assert captured_brief["place_names"] == [
        {"name": "Old Quarter", "line": "Old Quarter", "avatar": None},
        {"name": "Dock 9", "line": "Dock 9", "avatar": None},
    ]
