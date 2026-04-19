"""Tests for the cinematic image reveal viewer."""

from __future__ import annotations

from pathlib import Path

from modules.ui import image_viewer


class _FakeWindow:
    def __init__(self) -> None:
        self.attribute_calls = []
        self.after_calls = []
        self.bindings = {}
        self.configure_calls = []
        self.destroy_calls = 0
        self.geometry_value = None
        self.overrideredirect_value = None
        self.protocol_calls = []
        self.title_value = None
        self.updated = False
        self.lifted = False
        self.focused = False

    def attributes(self, *args):
        self.attribute_calls.append(args)

    def after(self, delay_ms, callback):
        self.after_calls.append((delay_ms, callback))

    def bind(self, sequence, callback) -> None:
        self.bindings[sequence] = callback

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(kwargs)

    def destroy(self) -> None:
        self.destroy_calls += 1

    def focus_force(self) -> None:
        self.focused = True

    def geometry(self, value: str) -> None:
        self.geometry_value = value

    def lift(self) -> None:
        self.lifted = True

    def overrideredirect(self, value: bool) -> None:
        self.overrideredirect_value = value

    def protocol(self, name: str, callback) -> None:
        self.protocol_calls.append((name, callback))

    def title(self, value: str) -> None:
        self.title_value = value

    def update_idletasks(self) -> None:
        self.updated = True

    def winfo_exists(self) -> int:
        return 0 if self.destroy_calls else 1


class _FakeImage:
    def __init__(self, size=(800, 600)) -> None:
        self.size = size
        self.resize_calls = []

    def resize(self, size, resample):
        self.resize_calls.append((size, resample))
        return _FakeImage(size=size)


class _FakeOpenedImage:
    def __init__(self, image: _FakeImage) -> None:
        self.image = image
        self.closed = False
        self.copy_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.closed = True

    def copy(self):
        self.copy_calls += 1
        return self.image


class _FakeWidget:
    created = []

    def __init__(self, master=None, **kwargs) -> None:
        self.master = master
        self.kwargs = kwargs
        self.children = []
        self.configure_calls = []
        self.pack_calls = []
        self.place_calls = []
        self.place_configure_calls = []
        self.place_forget_calls = 0
        if master is not None and hasattr(master, "children"):
            master.children.append(self)
        self.__class__.created.append(self)

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(kwargs)

    def place(self, **kwargs) -> None:
        self.place_calls.append(kwargs)

    def place_configure(self, **kwargs) -> None:
        self.place_configure_calls.append(kwargs)

    def place_forget(self) -> None:
        self.place_forget_calls += 1

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(kwargs)
        self.kwargs.update(kwargs)


class _FakeFrame(_FakeWidget):
    created = []


class _FakeLabel(_FakeWidget):
    created = []


class _FakeContent:
    def __init__(self, *, width: int = 1280) -> None:
        self._reveal_stage = _FakeWidget()
        self._reveal_image_label = _FakeWidget()
        self._reveal_curtain_overlays = None
        self.width = width

    def winfo_width(self) -> int:
        return self.width

    def winfo_reqwidth(self) -> int:
        return self.width


def _run_after_callbacks(window: _FakeWindow) -> None:
    index = 0
    while index < len(window.after_calls):
        _delay, callback = window.after_calls[index]
        index += 1
        callback()


def test_show_portrait_existing_file_prefers_second_monitor_and_starts_fade(monkeypatch) -> None:
    image_path = str(Path("viewer-assets") / "handout.png")
    window = _FakeWindow()
    fake_image = _FakeImage()
    opened_image = _FakeOpenedImage(fake_image)
    content_calls = []
    overlay_calls = []

    monkeypatch.setattr(image_viewer.ConfigHelper, "get_campaign_dir", lambda: "campaign")
    monkeypatch.setattr(image_viewer, "resolve_portrait_path", lambda path, campaign_dir: image_path)
    monkeypatch.setattr(image_viewer.os.path, "exists", lambda candidate: candidate == image_path)
    monkeypatch.setattr(image_viewer.Image, "open", lambda path: opened_image)
    monkeypatch.setattr(image_viewer.ImageTk, "PhotoImage", lambda image: ("photo", image.size))
    monkeypatch.setattr(image_viewer.ctk, "CTkToplevel", lambda: window)
    monkeypatch.setattr(
        image_viewer,
        "_get_monitors",
        lambda: [(0, 0, 1920, 1080), (1920, 0, 2560, 1440)],
    )
    monkeypatch.setattr(
        image_viewer,
        "_configure_single_monitor_overlay",
        lambda win, monitors: overlay_calls.append((win, monitors)),
    )
    monkeypatch.setattr(
        image_viewer,
        "_build_reveal_content",
        lambda win, photo, *, title=None, subtitle=None: content_calls.append((win, photo, title, subtitle)),
    )

    result = image_viewer.show_portrait("ignored.png", title="Kara Voss", subtitle="NPC")

    assert result is window
    assert window.title_value == "Kara Voss"
    assert window.geometry_value == "2560x1440+1920+0"
    assert window.overrideredirect_value is True
    assert window.updated is True
    assert window.lifted is True
    assert window.focused is True
    assert {"<Button-1>", "<Escape>", "<Return>", "<space>"} == set(window.bindings)
    assert [name for name, _callback in window.protocol_calls] == ["WM_DELETE_WINDOW"]
    assert ("-alpha", 0.0) in window.attribute_calls
    assert window.after_calls
    assert content_calls == [(window, ("photo", (800, 600)), "Kara Voss", "NPC")]
    assert overlay_calls == [(window, [(0, 0, 1920, 1080), (1920, 0, 2560, 1440)])]
    assert opened_image.copy_calls == 1
    assert opened_image.closed is True


def test_show_portrait_existing_file_uses_primary_monitor_when_it_is_the_only_option(monkeypatch) -> None:
    image_path = str(Path("viewer-assets") / "single-monitor.png")
    window = _FakeWindow()
    opened_image = _FakeOpenedImage(_FakeImage())

    monkeypatch.setattr(image_viewer.ConfigHelper, "get_campaign_dir", lambda: "campaign")
    monkeypatch.setattr(image_viewer, "resolve_portrait_path", lambda path, campaign_dir: image_path)
    monkeypatch.setattr(image_viewer.os.path, "exists", lambda candidate: candidate == image_path)
    monkeypatch.setattr(image_viewer.Image, "open", lambda path: opened_image)
    monkeypatch.setattr(image_viewer.ImageTk, "PhotoImage", lambda image: object())
    monkeypatch.setattr(image_viewer.ctk, "CTkToplevel", lambda: window)
    monkeypatch.setattr(image_viewer, "_get_monitors", lambda: [(10, 20, 1600, 900)])
    monkeypatch.setattr(image_viewer, "_build_reveal_content", lambda *args, **kwargs: None)

    image_viewer.show_portrait("ignored.png", title="Map")

    assert window.geometry_value == "1600x900+10+20"


def test_show_portrait_forwards_selected_animation_to_scheduler(monkeypatch) -> None:
    image_path = str(Path("viewer-assets") / "dramatic.png")
    window = _FakeWindow()
    scheduled = []
    opened_image = _FakeOpenedImage(_FakeImage())

    monkeypatch.setattr(image_viewer.ConfigHelper, "get_campaign_dir", lambda: "campaign")
    monkeypatch.setattr(image_viewer, "resolve_portrait_path", lambda path, campaign_dir: image_path)
    monkeypatch.setattr(image_viewer.os.path, "exists", lambda candidate: candidate == image_path)
    monkeypatch.setattr(image_viewer.Image, "open", lambda path: opened_image)
    monkeypatch.setattr(image_viewer.ImageTk, "PhotoImage", lambda image: object())
    monkeypatch.setattr(image_viewer.ctk, "CTkToplevel", lambda: window)
    monkeypatch.setattr(image_viewer, "_get_monitors", lambda: [(0, 0, 1600, 900)])
    monkeypatch.setattr(image_viewer, "_build_reveal_content", lambda *args, **kwargs: "content")
    monkeypatch.setattr(
        image_viewer,
        "_schedule_reveal_animation",
        lambda win, content, *, animation=None, image=None: scheduled.append((win, content, animation, image.size)),
    )

    image_viewer.show_portrait("ignored.png", title="Handout", animation="zoom in")

    assert scheduled == [(window, "content", "zoom", (800, 600))]


def test_show_portrait_shows_error_without_opening_window_for_invalid_path(monkeypatch) -> None:
    missing_path = str(Path("viewer-assets") / "missing.png")
    errors = []
    created = []

    monkeypatch.setattr(image_viewer.ConfigHelper, "get_campaign_dir", lambda: "campaign")
    monkeypatch.setattr(image_viewer, "resolve_portrait_path", lambda path, campaign_dir: missing_path)
    monkeypatch.setattr(image_viewer.os.path, "exists", lambda candidate: False)
    monkeypatch.setattr(image_viewer.messagebox, "showerror", lambda title, body: errors.append((title, body)))
    monkeypatch.setattr(
        image_viewer.ctk,
        "CTkToplevel",
        lambda: created.append("window") or _FakeWindow(),
    )

    result = image_viewer.show_portrait("ignored.png")

    assert result is None
    assert created == []
    assert errors == [("Error", "No valid portrait available.")]


def test_build_reveal_content_renders_uppercase_subtitle_title_and_image(monkeypatch) -> None:
    _FakeFrame.created = []
    _FakeLabel.created = []
    root = _FakeFrame()

    monkeypatch.setattr(image_viewer.tk, "Frame", _FakeFrame)
    monkeypatch.setattr(image_viewer.tk, "Label", _FakeLabel)

    content = image_viewer._build_reveal_content(root, "photo", title="Kara Voss", subtitle="npc")

    text_labels = [widget.kwargs["text"] for widget in _FakeLabel.created if "text" in widget.kwargs]
    image_labels = [widget.kwargs["image"] for widget in _FakeLabel.created if "image" in widget.kwargs]

    assert content is _FakeFrame.created[1]
    assert text_labels == ["NPC", "Kara Voss"]
    assert image_labels == ["photo"]


def test_schedule_reveal_animation_updates_zoom_frames(monkeypatch) -> None:
    window = _FakeWindow()
    content = _FakeContent()
    image = _FakeImage(size=(800, 600))

    monkeypatch.setattr(image_viewer, "_build_zoom_frames", lambda _image, _steps: ["frame-0", "frame-1", "frame-2"])

    image_viewer._schedule_reveal_animation(
        window,
        content,
        animation="zoom",
        image=image,
        alpha_steps=(0.0, 0.5, 1.0),
        delay_ms=10,
    )
    _run_after_callbacks(window)

    assert content._reveal_image_label.configure_calls == [
        {"image": "frame-0"},
        {"image": "frame-1"},
        {"image": "frame-2"},
    ]
    assert content._reveal_image_label.image == "frame-2"
    assert window.attribute_calls == [("-alpha", 0.0), ("-alpha", 0.5), ("-alpha", 1.0)]


def test_schedule_reveal_animation_offsets_stage_for_drift_mode() -> None:
    window = _FakeWindow()
    content = _FakeContent()

    image_viewer._schedule_reveal_animation(
        window,
        content,
        animation="drift up",
        alpha_steps=(0.0, 0.5, 1.0),
        delay_ms=10,
    )
    _run_after_callbacks(window)

    assert content._reveal_stage.place_configure_calls == [
        {"y": image_viewer._DRIFT_START_OFFSET},
        {"y": 21},
        {"y": 0},
    ]


def test_schedule_reveal_animation_updates_curtain_progress(monkeypatch) -> None:
    window = _FakeWindow()
    content = _FakeContent(width=1440)
    progress_calls = []

    monkeypatch.setattr(
        image_viewer,
        "_set_curtain_position",
        lambda target, progress: progress_calls.append((target, progress)),
    )
    image_viewer._schedule_reveal_animation(
        window,
        content,
        animation="curtain",
        alpha_steps=(0.0, 0.5, 1.0),
        delay_ms=10,
    )
    _run_after_callbacks(window)

    assert progress_calls == [
        (content, 0.0),
        (content, 0.5),
        (content, 1.0),
    ]


def test_schedule_reveal_animation_keeps_non_fade_motion_when_alpha_is_unsupported(monkeypatch) -> None:
    window = _FakeWindow()
    content = _FakeContent(width=1440)
    progress_calls = []

    def _unsupported_alpha(*_args):
        raise RuntimeError("alpha unsupported")

    monkeypatch.setattr(window, "attributes", _unsupported_alpha)
    monkeypatch.setattr(
        image_viewer,
        "_set_curtain_position",
        lambda target, progress: progress_calls.append((target, progress)),
    )

    image_viewer._schedule_reveal_animation(
        window,
        content,
        animation="curtain",
        alpha_steps=(0.0, 0.5, 1.0),
        delay_ms=10,
    )
    _run_after_callbacks(window)

    assert progress_calls == [
        (content, 0.0),
        (content, 0.5),
        (content, 1.0),
    ]


def test_bind_close_controls_binds_minimal_shortcuts_and_closes_window() -> None:
    window = _FakeWindow()

    image_viewer._bind_close_controls(window)

    assert {"<Button-1>", "<Escape>", "<Return>", "<space>"} == set(window.bindings)
    assert [name for name, _callback in window.protocol_calls] == ["WM_DELETE_WINDOW"]
    assert window.bindings["<Escape>"](None) == "break"
    assert window.destroy_calls == 1


def test_resize_for_reveal_never_requests_zero_sized_dimensions() -> None:
    image = _FakeImage(size=(1, 5000))

    resized = image_viewer._resize_for_reveal(image, 100, 100)

    assert resized.size == (1, 28)
    assert image.resize_calls == [((1, 28), image_viewer.Image.Resampling.LANCZOS)]


def test_normalize_reveal_animation_falls_back_to_default() -> None:
    assert image_viewer.normalize_reveal_animation("unknown") == image_viewer.DEFAULT_REVEAL_ANIMATION
