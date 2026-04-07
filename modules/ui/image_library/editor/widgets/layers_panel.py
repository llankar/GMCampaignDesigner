"""Layers panel widget for image editor."""

from __future__ import annotations

from collections.abc import Callable
import tkinter as tk

import customtkinter as ctk

from modules.ui.image_library.editor.core.document import ImageDocument


class LayersPanel(ctk.CTkFrame):
    """Simple layers panel with add/delete/reorder/visibility controls."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        on_changed: Callable[[], None],
        on_add: Callable[[], bool] | None = None,
        on_delete: Callable[[], bool] | None = None,
        on_move: Callable[[int], bool] | None = None,
        on_toggle_visibility: Callable[[], bool] | None = None,
    ) -> None:
        super().__init__(master)
        self._document: ImageDocument | None = None
        self._on_changed = on_changed
        self._on_add = on_add
        self._on_delete = on_delete
        self._on_move = on_move
        self._on_toggle_visibility = on_toggle_visibility

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Layers", anchor="w").grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))

        self._listbox = tk.Listbox(self, height=8, exportselection=False)
        self._listbox.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        self._listbox.bind("<<ListboxSelect>>", self._on_select, add="+")

        buttons = ctk.CTkFrame(self)
        buttons.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 8))

        ctk.CTkButton(buttons, text="+", width=34, command=self._add).grid(row=0, column=0, padx=3, pady=3)
        ctk.CTkButton(buttons, text="-", width=34, command=self._delete).grid(row=0, column=1, padx=3, pady=3)
        ctk.CTkButton(buttons, text="↑", width=34, command=lambda: self._move(1)).grid(row=0, column=2, padx=3, pady=3)
        ctk.CTkButton(buttons, text="↓", width=34, command=lambda: self._move(-1)).grid(row=0, column=3, padx=3, pady=3)
        ctk.CTkButton(buttons, text="👁", width=40, command=self._toggle_visibility).grid(row=0, column=4, padx=3, pady=3)

    def bind_document(self, document: ImageDocument) -> None:
        self._document = document
        self.refresh()

    def refresh(self) -> None:
        self._listbox.delete(0, tk.END)
        if self._document is None:
            return

        for display_index, layer_index in enumerate(range(len(self._document.layers) - 1, -1, -1)):
            layer = self._document.layers[layer_index]
            eye = "👁" if layer.visible else "🚫"
            active = "●" if layer_index == self._document.active_layer_index else "○"
            self._listbox.insert(tk.END, f"{active} {eye} {layer.name}")

        if self._document.layers:
            self.sync_active_layer(self._document.active_layer_index)

    def sync_active_layer(self, index: int) -> None:
        if self._document is None or not self._document.layers:
            return
        bounded_index = max(0, min(int(index), len(self._document.layers) - 1))
        display_index = len(self._document.layers) - 1 - bounded_index
        self._listbox.selection_clear(0, tk.END)
        self._listbox.selection_set(display_index)
        self._listbox.activate(display_index)

    def _emit_changed(self) -> None:
        self.refresh()
        self._on_changed()

    def _add(self) -> None:
        if self._document is None:
            return
        if self._on_add is not None:
            if self._on_add():
                self._emit_changed()
            return
        self._document.add_layer()
        self._emit_changed()

    def _delete(self) -> None:
        if self._document is None:
            return
        if self._on_delete is not None:
            if self._on_delete():
                self._emit_changed()
            return
        self._document.delete_active_layer()
        self._emit_changed()

    def _move(self, direction: int) -> None:
        if self._document is None:
            return
        if self._on_move is not None:
            if self._on_move(direction):
                self._emit_changed()
            return
        if self._document.move_active_layer(direction):
            self._emit_changed()

    def _toggle_visibility(self) -> None:
        if self._document is None:
            return
        if self._on_toggle_visibility is not None:
            if self._on_toggle_visibility():
                self._emit_changed()
            return
        if self._document.toggle_layer_visibility(self._document.active_layer_index):
            self._emit_changed()

    def _on_select(self, _event: tk.Event) -> None:
        if self._document is None:
            return
        selection = self._listbox.curselection()
        if not selection:
            return
        display_index = int(selection[0])
        layer_index = len(self._document.layers) - 1 - display_index
        if self._document.set_active_layer(layer_index):
            self._emit_changed()
