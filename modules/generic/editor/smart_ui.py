from __future__ import annotations

import customtkinter as ctk


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
        super().__init__(master)
        self._on_filter_change = on_filter_change
        self._on_jump_to_field = on_jump_to_field
        self._field_names: list[str] = []

        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Find field").grid(row=0, column=0, padx=(8, 6), pady=8)

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._handle_search)
        self.search_entry = ctk.CTkEntry(
            self,
            textvariable=self.search_var,
            placeholder_text="Type to filter fields…",
        )
        self.search_entry.grid(row=0, column=1, sticky="ew", pady=8)

        self.jump_menu = ctk.CTkOptionMenu(self, values=["Jump to…"], command=self._handle_jump)
        self.jump_menu.grid(row=0, column=2, padx=8, pady=8)

        self.info_label = ctk.CTkLabel(self, text="0/0 fields")
        self.info_label.grid(row=0, column=3, padx=(0, 8), pady=8)

        self.dirty_label = ctk.CTkLabel(self, text="Saved", text_color="#8ddf8d")
        self.dirty_label.grid(row=0, column=4, padx=(0, 8), pady=8)

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
            self.dirty_label.configure(text="Unsaved changes", text_color="#f2bd4a")
        else:
            self.dirty_label.configure(text="Saved", text_color="#8ddf8d")

    def _handle_search(self, *_):
        self._on_filter_change(self.search_var.get())

    def _handle_jump(self, value: str):
        if value and value != "Jump to…":
            self._on_jump_to_field(value)
