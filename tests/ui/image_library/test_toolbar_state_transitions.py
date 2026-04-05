"""Regression tests for image library toolbar state transitions."""

from __future__ import annotations

from modules.ui.image_library.toolbar import ImageLibraryToolbar


def test_toolbar_updates_size_and_mode_state() -> None:
    """Changing size/mode selectors should emit coherent toolbar state."""
    seen = []

    toolbar = ImageLibraryToolbar(parent=None, on_change=lambda state: seen.append(state))

    toolbar.size_var.set("Large")
    toolbar.mode_var.set("List")
    toolbar._emit_change(immediate=True)

    assert toolbar.state.size_preset == "Large"
    assert toolbar.state.display_mode == "List"
    assert seen[-1].size_preset == "Large"
    assert seen[-1].display_mode == "List"
