from __future__ import annotations

import pytest

from modules.generic.editor.window_components.portrait_and_image_workflows import (
    GenericEditorWindowPortraitAndImageWorkflows,
)


class _Host:
    def __init__(self, *, opener=None, master=None, parent=None):
        if opener is not None:
            self.open_image_library_browser = opener
        self.master = master
        self.parent = parent


class _EditorHarness(GenericEditorWindowPortraitAndImageWorkflows):
    def __init__(self, toplevel, *, main_window=None, app=None):
        self._toplevel = toplevel
        self.main_window = main_window
        self.app = app

    def winfo_toplevel(self):
        return self._toplevel


@pytest.mark.parametrize(
    "method_name, expected_callback_name",
    [
        ("open_portrait_image_library", "_attach_portrait_from_image_library"),
        ("open_image_image_library", "_attach_image_from_image_library"),
    ],
)
def test_image_library_resolution_falls_back_to_main_window(
    monkeypatch,
    method_name: str,
    expected_callback_name: str,
):
    opener_calls: list[dict] = []

    def _opener(**kwargs):
        opener_calls.append(kwargs)

    main_window = _Host(opener=_opener)
    toplevel = _Host(master=main_window)
    editor = _EditorHarness(toplevel=toplevel, main_window=main_window)

    monkeypatch.setattr(editor, "_resolve_portrait_search_query", lambda: "npc portrait")

    getattr(editor, method_name)()

    assert len(opener_calls) == 1
    assert opener_calls[0]["search_query"] == "npc portrait"
    assert opener_calls[0]["on_attach_to_entity"] == getattr(editor, expected_callback_name)


def test_image_library_resolution_missing_host_shows_existing_error(monkeypatch):
    toplevel = _Host()
    editor = _EditorHarness(toplevel=toplevel)
    seen_errors: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "modules.generic.editor.window_components.portrait_and_image_workflows.messagebox.showerror",
        lambda title, message: seen_errors.append((title, message)),
    )

    editor.open_portrait_image_library()

    assert seen_errors == [
        ("Image Library", "Image library is unavailable from this window."),
    ]
