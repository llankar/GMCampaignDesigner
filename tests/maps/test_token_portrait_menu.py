"""Coverage for token portrait selection context menus."""

from types import SimpleNamespace

import pytest

from modules.maps.controllers import display_map_controller
from modules.maps.controllers.display_map_controller import DisplayMapController
from modules.maps.menus.token_portrait_menu import add_token_portrait_menu


class FakeMenu:
    def __init__(self, parent=None, **options):
        self.parent = parent
        self.options = options
        self.commands = []
        self.cascades = []

    def add_command(self, **options):
        self.commands.append(options)

    def add_cascade(self, **options):
        self.cascades.append(options)


@pytest.mark.parametrize("candidate_count", [0, 1])
def test_no_change_image_menu_with_fewer_than_two_portraits(tmp_path, candidate_count):
    paths = []
    if candidate_count:
        portrait = tmp_path / "only.png"
        portrait.write_bytes(b"portrait")
        paths.append(str(portrait))
    parent = FakeMenu()

    added = add_token_portrait_menu(
        parent,
        paths,
        campaign_dir=str(tmp_path),
        load_image=lambda _path: None,
        on_select=lambda _path: None,
        menu_factory=FakeMenu,
    )

    assert not added
    assert parent.cascades == []


def test_change_image_submenu_contains_all_valid_candidates(tmp_path):
    first = tmp_path / "hero.png"
    second = tmp_path / "hero-alt.png"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    thumbnails = {str(first): object(), str(second): object()}
    parent = FakeMenu()

    assert add_token_portrait_menu(
        parent,
        [str(first), str(tmp_path / "missing.png"), str(second)],
        campaign_dir=str(tmp_path),
        load_image=thumbnails.get,
        on_select=lambda _path: None,
        menu_factory=FakeMenu,
    )

    assert [item["label"] for item in parent.cascades] == ["Change Token Image"]
    commands = parent.cascades[0]["menu"].commands
    assert [item["label"] for item in commands] == ["1. hero.png", "2. hero-alt.png"]
    assert [item["image"] for item in commands] == [thumbnails[str(first)], thumbnails[str(second)]]


def test_submenu_commands_replace_with_their_resolved_portrait(tmp_path, monkeypatch):
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    for name in ("first.png", "second.png"):
        (campaign / name).write_bytes(name.encode())
    monkeypatch.setattr(display_map_controller.ConfigHelper, "get_campaign_dir", lambda: str(campaign))
    replacements = []
    monkeypatch.setattr(
        display_map_controller,
        "replace_token_media",
        lambda controller, token, path: replacements.append((controller, token, path))
        or SimpleNamespace(success=True, error=""),
    )
    controller = DisplayMapController.__new__(DisplayMapController)
    controller.canvas = None
    token = {"type": "token", "image_path": "original.png"}
    parent = FakeMenu()
    add_token_portrait_menu(
        parent,
        ["first.png", "second.png"],
        campaign_dir=str(campaign),
        load_image=lambda _path: None,
        on_select=lambda selected: controller._replace_token_portrait(token, selected),
        menu_factory=FakeMenu,
    )

    commands = parent.cascades[0]["menu"].commands
    commands[0]["command"]()
    commands[1]["command"]()

    assert [call[2] for call in replacements] == [
        str(campaign / "first.png"),
        str(campaign / "second.png"),
    ]


def test_failed_portrait_replacement_preserves_media_and_reports_error(tmp_path, monkeypatch):
    portrait = tmp_path / "portrait.png"
    portrait.write_bytes(b"portrait")
    monkeypatch.setattr(display_map_controller.ConfigHelper, "get_campaign_dir", lambda: str(tmp_path))
    errors = []
    monkeypatch.setattr(
        display_map_controller,
        "replace_token_media",
        lambda *_args: SimpleNamespace(success=False, error="decode failed"),
    )
    monkeypatch.setattr(
        display_map_controller.messagebox,
        "showerror",
        lambda *args, **kwargs: errors.append((args, kwargs)),
    )
    controller = DisplayMapController.__new__(DisplayMapController)
    controller.canvas = None
    token = {"type": "token", "image_path": "original.png", "media_type": "image"}
    original = token.copy()

    controller._replace_token_portrait(token, str(portrait))

    assert token == original
    assert errors[0][0] == (
        "Change Token Image",
        "Unable to replace the token media.\n\ndecode failed",
    )
