from __future__ import annotations

from pathlib import Path

from modules.generic.editor.window_components.asset_path_and_preview import (
    GenericEditorWindowAssetPathAndPreview,
)
from modules.generic.editor.window_components.portrait_and_image_workflows import (
    GenericEditorWindowPortraitAndImageWorkflows,
)
from modules.ui.image_library.result_card import ImageResult


class _LabelStub:
    def configure(self, **_kwargs):
        return None


class _EditorHarness(
    GenericEditorWindowAssetPathAndPreview,
    GenericEditorWindowPortraitAndImageWorkflows,
):
    def __init__(self) -> None:
        self.item = {"Name": "NPC"}
        self.field_widgets = {}
        self.image_label = _LabelStub()
        self.image_image = None
        self.portrait_paths: list[str] = []
        self.captured_portrait_paths: list[str] = []

    def _add_portrait_path(self, path: str, *, make_primary: bool = False):
        if make_primary:
            self.portrait_paths.insert(0, path)
        else:
            self.portrait_paths.append(path)
        self.captured_portrait_paths.append(path)
        self.field_widgets["Portrait"] = path


def test_attach_portrait_from_library_stores_campaign_relative_path(monkeypatch, tmp_path: Path):
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    source = tmp_path / "library" / "portrait.png"
    source.parent.mkdir()
    source.write_bytes(b"x")

    editor = _EditorHarness()

    monkeypatch.setattr(
        "modules.generic.editor.window_components.asset_path_and_preview.ConfigHelper.get_campaign_dir",
        lambda: str(campaign_dir),
    )
    monkeypatch.setattr(
        editor,
        "copy_and_resize_portrait",
        lambda _src: str(campaign_dir / "assets" / "portraits" / "npc_portrait.png"),
    )

    editor.attach_portrait_from_library(ImageResult(path=str(source), name="portrait"))

    assert editor.captured_portrait_paths == ["assets/portraits/npc_portrait.png"]
    assert editor.field_widgets["Portrait"] == "assets/portraits/npc_portrait.png"


def test_attach_image_from_library_stores_campaign_relative_path(monkeypatch, tmp_path: Path):
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    source = tmp_path / "library" / "map.png"
    source.parent.mkdir()
    source.write_bytes(b"x")

    editor = _EditorHarness()

    monkeypatch.setattr(
        "modules.generic.editor.window_components.asset_path_and_preview.ConfigHelper.get_campaign_dir",
        lambda: str(campaign_dir),
    )
    monkeypatch.setattr(
        editor,
        "copy_and_resize_image",
        lambda _src: str(campaign_dir / "assets" / "images" / "map_images" / "battlemap.png"),
    )

    editor.attach_image_from_library(ImageResult(path=str(source), name="map"))

    assert editor.field_widgets["Image"] == "assets/images/map_images/battlemap.png"
