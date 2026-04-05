"""Reusable result card widget for image browsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import customtkinter as ctk


@dataclass(slots=True)
class ImageResult:
    """Simple data object representing one image library item."""

    path: str
    name: str
    modified_ts: float = 0.0
    subtitle: str = ""
    source_folder_name: str = ""


class ImageResultCard(ctk.CTkFrame):
    """Visual card that supports both list and grid layouts."""

    def __init__(
        self,
        parent,
        *,
        item: ImageResult,
        image: ctk.CTkImage,
        display_mode: str,
        on_open: Callable[[ImageResult], None],
        on_view: Callable[[ImageResult], None],
        on_context_menu: Callable[[ImageResult, int, int], None],
    ) -> None:
        super().__init__(parent, corner_radius=8)
        self.item = item
        self._on_open = on_open
        self._on_view = on_view
        self._on_context_menu = on_context_menu

        self.grid_columnconfigure(1, weight=1)

        if display_mode == "List":
            self._build_list_layout(image)
        else:
            self._build_grid_layout(image)

    def _build_list_layout(self, image: ctk.CTkImage) -> None:
        """Build row-oriented layout."""
        thumb = ctk.CTkLabel(self, text="", image=image)
        thumb.grid(row=0, column=0, padx=(8, 12), pady=8, sticky="w")

        title = ctk.CTkLabel(self, text=self.item.name, anchor="w")
        title.grid(row=0, column=1, padx=(0, 8), pady=(8, 2), sticky="ew")

        subtitle_text = self.item.subtitle or self.item.path
        subtitle = ctk.CTkLabel(self, text=subtitle_text, anchor="w", justify="left", wraplength=700)
        subtitle.grid(row=1, column=1, padx=(0, 8), pady=(0, 8), sticky="ew")

        open_button = ctk.CTkButton(self, text="Open", width=72, command=self._open)
        open_button.grid(row=0, column=2, rowspan=2, padx=(8, 10), pady=8, sticky="e")

        self._bind_interactions(thumb, title, subtitle)

    def _build_grid_layout(self, image: ctk.CTkImage) -> None:
        """Build card-style layout."""
        thumb = ctk.CTkLabel(self, text="", image=image)
        thumb.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="n")

        title = ctk.CTkLabel(self, text=self.item.name, justify="center", wraplength=180)
        title.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="ew")

        self._bind_interactions(thumb, title, self)

    def _bind_interactions(self, *widgets) -> None:
        """Wire all interaction shortcuts consistently."""
        for widget in widgets:
            widget.bind("<Double-Button-1>", lambda _event: self._open())
            widget.bind("<Button-3>", self._open_context)

    def _open(self) -> None:
        self._on_open(self.item)

    def _open_context(self, event) -> None:
        self._on_context_menu(self.item, event.x_root, event.y_root)

    def trigger_view(self) -> None:
        """Open full preview dialog action."""
        self._on_view(self.item)
