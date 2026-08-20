from __future__ import annotations

from pathlib import Path

from modules.generic.editor.window_components.asset_path_and_preview import (
    GenericEditorWindowAssetPathAndPreview,
)
from modules.generic.editor.window_components.portrait_and_image_workflows import (
    GenericEditorWindowPortraitAndImageWorkflows,
)
from modules.helpers.portrait_helper import parse_portrait_value, serialize_portrait_value


class _LabelStub:
    def __init__(self) -> None:
        self.calls = []

    def configure(self, **kwargs):
        self.calls.append(kwargs)


class _EditorHarness(
    GenericEditorWindowAssetPathAndPreview,
    GenericEditorWindowPortraitAndImageWorkflows,
):
    def __init__(self) -> None:
        self.item = {"Name": "Tester"}
        self.field_widgets = {}
        self.image_label = _LabelStub()
        self.image_image = None
        self.portrait_paths: list[str] = []
        self.added_portraits: list[str] = []

    def _add_portrait_path(self, path: str, *, make_primary: bool = False):
        if make_primary:
            self.portrait_paths.insert(0, path)
        else:
            self.portrait_paths.append(path)
        self.added_portraits.append(path)
        self.field_widgets["Portrait"] = serialize_portrait_value(self.portrait_paths)


def test_select_image_persists_campaign_relative_path(monkeypatch, tmp_path: Path):
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
        "modules.generic.editor.window_components.asset_path_and_preview.filedialog.askopenfilename",
        lambda **_: str(source),
    )
    monkeypatch.setattr(
        editor,
        "copy_and_resize_image",
        lambda _src: str(campaign_dir / "assets" / "images" / "map_images" / "copied.png"),
    )

    editor.select_image()

    assert editor.field_widgets["Image"] == "assets/images/map_images/copied.png"


def test_select_portrait_missing_source_shows_error(monkeypatch, tmp_path: Path):
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    missing = tmp_path / "library" / "missing.png"

    editor = _EditorHarness()
    seen_errors: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "modules.generic.editor.window_components.asset_path_and_preview.ConfigHelper.get_campaign_dir",
        lambda: str(campaign_dir),
    )
    monkeypatch.setattr(
        "modules.generic.editor.window_components.portrait_and_image_workflows.filedialog.askopenfilenames",
        lambda **_: [str(missing)],
    )
    monkeypatch.setattr(
        "modules.generic.editor.window_components.asset_path_and_preview.messagebox.showerror",
        lambda title, message: seen_errors.append((title, message)),
    )

    def _unexpected_copy(_src):
        raise AssertionError("copy_and_resize_portrait should not be called for missing source")

    monkeypatch.setattr(editor, "copy_and_resize_portrait", _unexpected_copy)

    editor.select_portrait()

    assert seen_errors
    assert "introuvable" in seen_errors[0][0].lower()
    assert "Portrait" not in editor.field_widgets


def test_select_portrait_accepts_video_and_preserves_existing_multiple_values(monkeypatch, tmp_path: Path):
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    video = tmp_path / "library" / "intro.WEBM"
    video.parent.mkdir()
    video.write_bytes(b"video")
    editor = _EditorHarness()
    editor.portrait_paths = ["assets/portraits/first.png", "assets/portraits/second.jpg"]
    dialog_options = {}

    monkeypatch.setattr(
        "modules.generic.editor.window_components.asset_path_and_preview.ConfigHelper.get_campaign_dir",
        lambda: str(campaign_dir),
    )

    def choose(**kwargs):
        dialog_options.update(kwargs)
        return [str(video)]

    monkeypatch.setattr(
        "modules.generic.editor.window_components.portrait_and_image_workflows.filedialog.askopenfilenames",
        choose,
    )
    monkeypatch.setattr(
        editor,
        "copy_and_resize_portrait",
        lambda _src: "assets/portraits/intro.webm",
    )

    editor.select_portrait()

    assert "*.webm" in dialog_options["filetypes"][0][1]
    assert parse_portrait_value(editor.field_widgets["Portrait"]) == [
        "assets/portraits/first.png",
        "assets/portraits/second.jpg",
        "assets/portraits/intro.webm",
    ]
