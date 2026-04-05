"""Toolbar controls for the image library browser panel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import customtkinter as ctk


SIZE_PRESETS = ("Small", "Medium", "Large", "Very Large")
DISPLAY_MODES = ("Grid", "List")
SORT_OPTIONS = (
    "Name (A-Z)",
    "Name (Z-A)",
    "Newest First",
    "Oldest First",
    "Path (A-Z)",
)


@dataclass(slots=True)
class ToolbarState:
    """Current state for toolbar controls."""

    query: str = ""
    size_preset: str = "Medium"
    display_mode: str = "Grid"
    sort_by: str = "Name (A-Z)"
    folder_name: str = "All"


class ImageLibraryToolbar(ctk.CTkFrame):
    """Composite toolbar with debounced search and selectors."""

    def __init__(
        self,
        parent,
        *,
        on_change: Callable[[ToolbarState], None],
        debounce_ms: int = 250,
        initial_state: ToolbarState | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_change = on_change
        self._debounce_ms = max(50, int(debounce_ms))
        self._pending_search_job: str | None = None
        self._state = initial_state or ToolbarState()

        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Search").grid(row=0, column=0, padx=(8, 6), pady=8, sticky="w")
        self.search_var = ctk.StringVar(value=self._state.query)
        self.search_entry = ctk.CTkEntry(self, textvariable=self.search_var, placeholder_text="Search images...")
        self.search_entry.grid(row=0, column=1, padx=(0, 10), pady=8, sticky="ew")
        self.search_entry.bind("<KeyRelease>", self._on_search_key_release)

        self.size_var = ctk.StringVar(value=self._state.size_preset)
        self.size_selector = ctk.CTkOptionMenu(
            self,
            values=list(SIZE_PRESETS),
            variable=self.size_var,
            command=lambda _value: self._emit_change(immediate=True),
        )
        self.size_selector.grid(row=0, column=2, padx=6, pady=8, sticky="ew")

        self.mode_var = ctk.StringVar(value=self._state.display_mode)
        self.mode_selector = ctk.CTkOptionMenu(
            self,
            values=list(DISPLAY_MODES),
            variable=self.mode_var,
            command=lambda _value: self._emit_change(immediate=True),
        )
        self.mode_selector.grid(row=0, column=3, padx=6, pady=8, sticky="ew")

        self.sort_var = ctk.StringVar(value=self._state.sort_by)
        self.sort_selector = ctk.CTkOptionMenu(
            self,
            values=list(SORT_OPTIONS),
            variable=self.sort_var,
            command=lambda _value: self._emit_change(immediate=True),
        )
        self.sort_selector.grid(row=0, column=4, padx=(6, 8), pady=8, sticky="ew")

        ctk.CTkLabel(self, text="Folder").grid(row=0, column=5, padx=(8, 6), pady=8, sticky="w")
        self.folder_var = ctk.StringVar(value=self._state.folder_name or "All")
        self.folder_selector = ctk.CTkOptionMenu(
            self,
            values=["All"],
            variable=self.folder_var,
            command=lambda _value: self._emit_change(immediate=True),
        )
        self.folder_selector.grid(row=0, column=6, padx=(0, 8), pady=8, sticky="ew")

    def _on_search_key_release(self, _event=None) -> None:
        """Debounce user typing and emit a single consolidated change."""
        if self._pending_search_job:
            self.after_cancel(self._pending_search_job)
        self._pending_search_job = self.after(self._debounce_ms, self._emit_change)

    def _emit_change(self, immediate: bool = False) -> None:
        """Push toolbar state to callback."""
        if self._pending_search_job and immediate:
            self.after_cancel(self._pending_search_job)
            self._pending_search_job = None

        self._state = ToolbarState(
            query=self.search_var.get().strip(),
            size_preset=self.size_var.get(),
            display_mode=self.mode_var.get(),
            sort_by=self.sort_var.get(),
            folder_name=self.folder_var.get().strip() or "All",
        )
        self._on_change(self._state)

    def set_folder_choices(self, folder_names: list[str]) -> None:
        """Refresh available source-folder options while preserving selection when possible."""
        distinct = sorted({str(name).strip() for name in folder_names if str(name).strip()}, key=str.lower)
        values = ["All", *distinct]
        self.folder_selector.configure(values=values)

        selected = self.folder_var.get().strip() or "All"
        self.folder_var.set(selected if selected in values else "All")

    @property
    def state(self) -> ToolbarState:
        """Expose latest toolbar state."""
        return self._state
