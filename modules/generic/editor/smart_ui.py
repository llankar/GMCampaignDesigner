from __future__ import annotations

import customtkinter as ctk

from modules.generic.editor.styles import (
    EDITOR_PALETTE,
    option_menu_style,
    primary_button_style,
    toolbar_entry_style,
)


DEFAULT_FIELD_PRIORITY = ("Name", "Portrait", "Image", "Audio")


def prioritize_fields(fields: list[dict], priority: tuple[str, ...] = DEFAULT_FIELD_PRIORITY) -> list[dict]:
    """Return fields ordered by a small priority list while staying generic."""
    by_name = {str(field.get("name", "")): field for field in fields if isinstance(field, dict)}
    ordered: list[dict] = []
    seen: set[str] = set()

    for field_name in priority:
        field = by_name.get(field_name)
        if field is not None:
            ordered.append(field)
            seen.add(field_name)

    for field in fields:
        name = str(field.get("name", ""))
        if name in seen:
            continue
        ordered.append(field)

    return ordered


class SmartEditorToolbar(ctk.CTkFrame):
    """Top toolbar with quick-jump, filtering and dirty-state feedback."""

    def __init__(self, master, *, on_filter_change, on_jump_to_field):
        super().__init__(
            master,
            fg_color=EDITOR_PALETTE["surface_alt"],
            border_width=1,
            border_color=EDITOR_PALETTE["border"],
            corner_radius=12,
        )
        self._on_filter_change = on_filter_change
        self._on_jump_to_field = on_jump_to_field
        self._field_names: list[str] = []

        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self,
            text="Find field",
            text_color=EDITOR_PALETTE["muted_text"],
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, padx=(14, 8), pady=10)

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._handle_search)
        self.search_entry = ctk.CTkEntry(
            self,
            textvariable=self.search_var,
            placeholder_text="Type to filter fields…",
            **toolbar_entry_style(),
        )
        self.search_entry.grid(row=0, column=1, sticky="ew", pady=10)

        self.jump_menu = ctk.CTkOptionMenu(
            self,
            values=["Jump to…"],
            command=self._handle_jump,
            **option_menu_style(),
        )
        self.jump_menu.grid(row=0, column=2, padx=10, pady=10)

        self.info_label = ctk.CTkLabel(
            self,
            text="0/0 fields",
            text_color=EDITOR_PALETTE["muted_text"],
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.info_label.grid(row=0, column=3, padx=(0, 10), pady=10)

        self.dirty_label = ctk.CTkLabel(
            self,
            text="Saved",
            text_color=EDITOR_PALETTE["success"],
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.dirty_label.grid(row=0, column=4, padx=(0, 14), pady=10)

    def set_fields(self, field_names: list[str]):
        self._field_names = field_names
        values = ["Jump to…", *field_names] if field_names else ["Jump to…"]
        self.jump_menu.configure(values=values)
        self.jump_menu.set("Jump to…")
        self.update_visible_count(len(field_names), len(field_names))

    def update_visible_count(self, visible: int, total: int):
        self.info_label.configure(text=f"{visible}/{total} fields")

    def set_dirty(self, dirty: bool):
        if dirty:
            self.dirty_label.configure(text="Unsaved changes", text_color=EDITOR_PALETTE["warning"])
        else:
            self.dirty_label.configure(text="Saved", text_color=EDITOR_PALETTE["success"])

    def _handle_search(self, *_):
        self._on_filter_change(self.search_var.get())

    def _handle_jump(self, value: str):
        if value and value != "Jump to…":
            self._on_jump_to_field(value)
