"""Top-level dialog shell that hosts the reusable image browser panel."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

import customtkinter as ctk

from modules.image_assets import ImageAssetsService
from modules.ui.image_library.browser_panel import ImageBrowserPanel
from modules.ui.image_library.result_card import ImageResult
from modules.ui.image_library.toolbar import ToolbarState


class ImageLibraryBrowserDialog(ctk.CTkToplevel):
    """Open shared image browser with optional query and attach callback."""

    def __init__(
        self,
        master: tk.Misc | None = None,
        *,
        service: ImageAssetsService | None = None,
        search_query: str = "",
        on_attach_to_entity: Callable[[ImageResult], None] | None = None,
    ) -> None:
        super().__init__(master)
        self.title("Image Library")
        self.geometry("1240x820")
        self.minsize(960, 680)
        self.transient(master)

        self._service = service or ImageAssetsService()
        self._search_query = str(search_query or "").strip()
        self._on_attach_to_entity = on_attach_to_entity
        self._folder_choices: list[str] = []

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._panel = ImageBrowserPanel(
            self,
            records=[],
            toolbar_state=ToolbarState(query=self._search_query),
            on_attach_to_entity=self._on_attach_to_entity,
            on_toolbar_state_changed=self._on_toolbar_state_changed,
        )
        self._panel.grid(row=0, column=0, sticky="nsew")

        self._load_records()

        self.bind("<Escape>", lambda _event: self.destroy())
        self.lift()
        self.focus_force()

    def _load_records(self) -> None:
        """Fetch records and map them to panel data model."""
        toolbar_state = self._panel.toolbar.state
        selected_folder = (toolbar_state.folder_name or "").strip()
        filters = {"source_folder_names": [selected_folder]} if selected_folder and selected_folder != "All" else None
        rows, _total = self._service.search_images(
            query=toolbar_state.query,
            filters=filters,
            limit=5000,
            offset=0,
            sort="updated_desc",
        )
        self._folder_choices = sorted(
            {
                str(row.source_folder_name).strip()
                for row in rows
                if str(row.source_folder_name).strip()
            },
            key=str.lower,
        )
        self._panel.toolbar.set_folder_choices(self._folder_choices)
        results = [
            ImageResult(
                path=row.path,
                name=row.name,
                modified_ts=0.0,
                subtitle=row.relative_path or row.source_root,
                source_folder_name=row.source_folder_name,
            )
            for row in rows
        ]
        self._panel.set_records(results)

    def _on_toolbar_state_changed(self, _state: ToolbarState) -> None:
        """Re-query backend when toolbar state changes."""
        self._load_records()
