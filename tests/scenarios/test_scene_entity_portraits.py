"""Tests for scene body entity portraits."""

from __future__ import annotations

from modules.scenarios.widgets.scene_body import entity_portraits as subject


class _FakeWrapper:
    def __init__(self, items):
        self._items = items

    def load_items(self):
        return self._items


class _FakeGMView:
    def __init__(self, wrappers):
        self.wrappers = wrappers


class _FakeCTkImage:
    def __init__(self, light_image=None, dark_image=None, size=None):
        self.light_image = light_image
        self.dark_image = dark_image
        self.size = size


class _FakeImageObj:
    def __init__(self):
        self.width = 64
        self.height = 64

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def convert(self, _mode):
        return self

    def thumbnail(self, size, _resample):
        self.width, self.height = size

    def copy(self):
        return self


def test_attach_entity_avatars_adds_avatar_from_portrait_field(tmp_path, monkeypatch):
    portrait_path = tmp_path / "npc_portrait.png"
    portrait_path.write_bytes(b"not-an-image")

    monkeypatch.setattr(subject.ctk, "CTkImage", _FakeCTkImage)
    monkeypatch.setattr(subject.ConfigHelper, "get_campaign_dir", staticmethod(lambda: str(tmp_path)))
    monkeypatch.setattr(subject.Image, "open", lambda _path: _FakeImageObj())

    gm_view = _FakeGMView(
        wrappers={
            "NPCs": _FakeWrapper(
                [
                    {"Name": "Avery", "Portrait": str(portrait_path)},
                ]
            )
        }
    )

    entities = [{"name": "Avery", "role": "Guide"}]
    prepared = subject.attach_entity_avatars("NPCs", entities, gm_view)

    assert prepared[0]["avatar"] is not None
    assert prepared[0]["avatar"].size == (24, 24)


def test_attach_entity_avatars_uses_cache_for_same_entity(tmp_path, monkeypatch):
    portrait_path = tmp_path / "villain_portrait.png"
    portrait_path.write_bytes(b"not-an-image")

    monkeypatch.setattr(subject.ctk, "CTkImage", _FakeCTkImage)
    monkeypatch.setattr(subject.ConfigHelper, "get_campaign_dir", staticmethod(lambda: str(tmp_path)))

    open_calls = {"count": 0}

    def _fake_open(_path):
        open_calls["count"] += 1
        return _FakeImageObj()

    monkeypatch.setattr(subject.Image, "open", _fake_open)

    gm_view = _FakeGMView(
        wrappers={
            "Villains": _FakeWrapper(
                [
                    {"Name": "Mordrek", "Portrait": str(portrait_path)},
                ]
            )
        }
    )

    entities = [{"name": "Mordrek"}]
    first = subject.attach_entity_avatars("Villains", entities, gm_view)
    second = subject.attach_entity_avatars("Villains", entities, gm_view)

    assert first[0]["avatar"] is second[0]["avatar"]
    assert open_calls["count"] == 1
