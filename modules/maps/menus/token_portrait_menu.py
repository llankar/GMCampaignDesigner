"""Build the portrait-selection portion of a token context menu."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Iterable

from modules.helpers.portrait_helper import portrait_menu_label, resolve_portrait_candidate


def add_token_portrait_menu(
    parent_menu,
    portrait_paths: Iterable[str],
    *,
    campaign_dir: str,
    load_image: Callable[[str], object | None],
    on_select: Callable[[str], None],
    menu_factory: Callable[..., object] = tk.Menu,
) -> bool:
    """Add a change-image submenu when multiple valid portraits are available.

    Candidate paths are captured in each command's default argument to avoid
    late-binding bugs.  The controller callback remains responsible for
    resolving and applying the selected portrait.
    """
    candidates = [
        path
        for path in portrait_paths
        if resolve_portrait_candidate(path, campaign_dir)
    ]
    if len(candidates) <= 1:
        return False

    portrait_menu = menu_factory(parent_menu, tearoff=0)
    for index, path in enumerate(candidates, start=1):
        options = {
            "label": portrait_menu_label(path, index),
            "command": lambda selected=path: on_select(selected),
        }
        image = load_image(path)
        if image is not None:
            options.update(image=image, compound="left")
        portrait_menu.add_command(**options)

    parent_menu.add_cascade(label="Change Token Image", menu=portrait_menu)
    return True
