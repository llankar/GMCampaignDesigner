from __future__ import annotations

from modules.generic.editor.window_components.portrait_and_image_workflows import (
    GenericEditorWindowPortraitAndImageWorkflows,
)


class _DestroyEvent:
    def __init__(self, widget):
        self.widget = widget


class _DialogStub:
    def __init__(self, editor):
        self.editor = editor
        self.transient_parent = None
        self.lift_called = False
        self.focus_called = False
        self.grab_called = False
        self._destroy_callbacks = []

    def transient(self, parent):
        self.transient_parent = parent

    def lift(self):
        self.lift_called = True

    def focus_force(self):
        self.focus_called = True

    def grab_set(self):
        self.grab_called = True
        self.editor._current_grab = self

    def bind(self, event_name, callback, add=None):
        if event_name == "<Destroy>":
            self._destroy_callbacks.append(callback)

    def destroy(self):
        if self.editor._current_grab is self:
            self.editor._current_grab = None
        for callback in list(self._destroy_callbacks):
            callback(_DestroyEvent(self))


class _EditorHarness(GenericEditorWindowPortraitAndImageWorkflows):
    def __init__(self):
        self._current_grab = None
        self.lift_called = False
        self.focus_called = False

    def _resolve_portrait_search_query(self):
        return "goblin"

    def _attach_portrait_from_image_library(self, *_args, **_kwargs):
        return None

    def _attach_image_from_image_library(self, *_args, **_kwargs):
        return None

    def grab_current(self):
        return self._current_grab

    def grab_release(self):
        if self._current_grab is self:
            self._current_grab = None

    def grab_set(self):
        self._current_grab = self

    def winfo_exists(self):
        return True

    def lift(self):
        self.lift_called = True

    def focus_force(self):
        self.focus_called = True


def test_opening_image_library_hands_grab_to_dialog_when_editor_is_modal(monkeypatch):
    editor = _EditorHarness()
    editor._current_grab = editor
    dialog = _DialogStub(editor)

    monkeypatch.setattr(editor, "_resolve_image_library_opener", lambda: (lambda **_kwargs: dialog))

    editor.open_portrait_image_library()

    assert dialog.transient_parent is editor
    assert dialog.lift_called is True
    assert dialog.focus_called is True
    assert dialog.grab_called is True
    assert editor.grab_current() is dialog


def test_closing_image_library_restores_editor_grab(monkeypatch):
    editor = _EditorHarness()
    editor._current_grab = editor
    dialog = _DialogStub(editor)

    monkeypatch.setattr(editor, "_resolve_image_library_opener", lambda: (lambda **_kwargs: dialog))

    editor.open_image_image_library()
    dialog.destroy()

    assert editor.grab_current() is editor
    assert editor.lift_called is True
    assert editor.focus_called is True


def test_modal_state_is_restored_if_opener_returns_no_dialog(monkeypatch):
    editor = _EditorHarness()
    editor._current_grab = editor

    monkeypatch.setattr(editor, "_resolve_image_library_opener", lambda: (lambda **_kwargs: None))

    editor.open_portrait_image_library()

    assert editor.grab_current() is editor


def test_closing_dialog_does_not_force_editor_modal_when_it_was_not_modal(monkeypatch):
    editor = _EditorHarness()
    dialog = _DialogStub(editor)

    monkeypatch.setattr(editor, "_resolve_image_library_opener", lambda: (lambda **_kwargs: dialog))

    editor.open_image_image_library()
    dialog.destroy()

    assert editor.grab_current() is None
