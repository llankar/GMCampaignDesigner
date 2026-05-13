"""Shared object shelf panel builder."""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Iterable

import customtkinter as ctk

from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.logging_helper import log_warning
from modules.helpers.template_loader import load_template
from modules.objects.object_constants import OBJECT_CATEGORY_ALLOWED
from modules.objects.object_shelf_canvas_view import ObjectShelfView


class ObjectShelfPanel(ctk.CTkFrame):
    """Lightweight host exposing the list-view API expected by ObjectShelfView."""

    def __init__(
        self,
        master,
        *,
        open_entity_callback: Callable[..., object] | None = None,
    ) -> None:
        """Create a standalone object shelf backed by the objects model."""
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.open_entity_callback = open_entity_callback
        self.model_wrapper = GenericModelWrapper("objects")
        self.template = load_template("objects")
        self.items: list[dict] = []
        self.filtered_items: list[dict] = []
        self.selected_iids: set[str] = set()
        self.search_var = tk.StringVar(master=self)

        self.shelf_view = ObjectShelfView(self, OBJECT_CATEGORY_ALLOWED)
        self.shelf_view.frame.grid(row=0, column=0, sticky="nsew")
        self.refresh_items()

    def refresh_items(self) -> None:
        """Reload objects from storage and refresh the shelf rows."""
        try:
            self.items = list(self.model_wrapper.load_items())
        except Exception as exc:
            log_warning(
                f"Unable to load object shelf items: {exc}",
                func_name="ObjectShelfPanel.refresh_items",
            )
            self.items = []
        self.filter_items(self.search_var.get())

    def filter_items(self, query: str | None = None) -> None:
        """Filter the shelf by a simple full-record text search."""
        text = (query or "").strip()
        try:
            self.search_var.set(text)
        except Exception:
            pass

        normalized = text.casefold()
        if normalized:
            self.filtered_items = [
                item for item in self.items if self._item_matches_query(item, normalized)
            ]
        else:
            self.filtered_items = list(self.items)

        self.shelf_view.populate()
        self.shelf_view.refresh_selection()

    def open_item(self, item: dict) -> object | None:
        """Open an object through the optional host callback."""
        if not callable(self.open_entity_callback):
            return None
        name = item.get("Name") or item.get("Title")
        return self.open_entity_callback("Objects", name)

    def open_selected_item(self, item: dict) -> object | None:
        """Compatibility alias for shelf/item-opening callbacks."""
        return self.open_item(item)

    @classmethod
    def _item_matches_query(cls, item: dict, normalized_query: str) -> bool:
        """Return whether any primitive value in an item matches the query."""
        return any(
            normalized_query in str(value).casefold()
            for value in cls._iter_search_values(item.values())
        )

    @classmethod
    def _iter_search_values(cls, values: Iterable[object]) -> Iterable[object]:
        """Yield nested values from dictionaries/lists for broad shelf searching."""
        for value in values:
            if isinstance(value, dict):
                yield from cls._iter_search_values(value.values())
            elif isinstance(value, (list, tuple, set)):
                yield from cls._iter_search_values(value)
            elif value is not None:
                yield value


def create_object_shelf_panel(master, open_entity_callback=None) -> ObjectShelfPanel:
    """Create a standalone object shelf panel for GM Table and GM Screen hosts."""
    return ObjectShelfPanel(master, open_entity_callback=open_entity_callback)
