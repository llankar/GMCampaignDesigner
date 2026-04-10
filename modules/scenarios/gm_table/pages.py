"""GM Table page wrappers."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from modules.image_assets import ImageAssetsService
from modules.ui.image_library.browser_panel import ImageBrowserPanel
from modules.ui.image_library.result_card import ImageResult
from modules.ui.image_library.toolbar import ToolbarState


class GMTableHostedPage(ctk.CTkFrame):
    """Wrap an existing widget or controller in a GM Table page shell."""

    def __init__(
        self,
        master,
        *,
        builder: Callable[[ctk.CTkFrame], object],
        state_getter: Callable[[object], dict] | None = None,
        close_callback: Callable[[object], None] | None = None,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._payload = builder(self)
        self._state_getter = state_getter
        self._close_callback = close_callback

    def get_state(self) -> dict:
        """Return any serializable page state."""
        if self._state_getter is None:
            return {}
        try:
            state = self._state_getter(self._payload) or {}
        except Exception:
            state = {}
        return state if isinstance(state, dict) else {}

    def close(self) -> None:
        """Dispose the underlying payload if needed."""
        if self._close_callback is None:
            return
        try:
            self._close_callback(self._payload)
        except Exception:
            pass


class GMTableNotePage(ctk.CTkFrame):
    """Simple fast note page for the GM table."""

    def __init__(self, master, *, initial_text: str = "") -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text="Scratchpad",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.textbox = ctk.CTkTextbox(self, wrap="word")
        self.textbox.grid(row=1, column=0, sticky="nsew")
        if initial_text:
            self.textbox.insert("1.0", initial_text)

    def get_state(self) -> dict:
        """Return the note contents."""
        return {"text": self.textbox.get("1.0", "end-1c")}


class GMTableImageLibraryPage(ctk.CTkFrame):
    """Embedded shared image library browser."""

    def __init__(self, master, *, initial_state: dict | None = None) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._service = ImageAssetsService()
        self._folder_choices: list[str] = []
        state = dict(initial_state or {})
        self._panel = ImageBrowserPanel(
            self,
            records=[],
            toolbar_state=ToolbarState(
                query=str(state.get("query") or ""),
                folder_name=str(state.get("folder_name") or ""),
                mode=str(state.get("mode") or "Browse"),
                size_label=str(state.get("size_label") or "Medium"),
                sort_label=str(state.get("sort_label") or "Newest"),
            ),
            on_toolbar_state_changed=self._on_toolbar_state_changed,
        )
        self._panel.grid(row=0, column=0, sticky="nsew")
        self._load_records()

    def _load_records(self) -> None:
        """Fetch and map image records for the browser."""
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
        """Refresh content on browser filter changes."""
        self._load_records()

    def get_state(self) -> dict:
        """Persist the latest toolbar state."""
        state = self._panel.toolbar.state
        return {
            "query": state.query,
            "folder_name": state.folder_name,
            "mode": state.mode,
            "size_label": state.size_label,
            "sort_label": state.sort_label,
        }
