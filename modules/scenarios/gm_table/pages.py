"""GM Table page wrappers."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import customtkinter as ctk
from PIL import Image

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.portrait_helper import resolve_portrait_candidate
from modules.image_assets import ImageAssetsService
from modules.scenarios.gm_table.attachments import EntityAttachment
from modules.ui.image_library.browser_panel import ImageBrowserPanel
from modules.ui.image_library.result_card import ImageResult
from modules.ui.image_library.toolbar import ToolbarState

IMAGE_PANEL_SIZE = (520, 390)


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
        self._grid_payload_if_needed()
        self._state_getter = state_getter
        self._close_callback = close_callback

    def _grid_payload_if_needed(self) -> None:
        """Mount returned widget payloads that were not laid out by their builder."""
        payload = self._payload
        if not hasattr(payload, "grid") or not hasattr(payload, "winfo_manager"):
            return
        try:
            if payload.winfo_manager():
                return
            payload.grid(row=0, column=0, sticky="nsew")
        except Exception:
            pass

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


class GMTableImagePage(ctk.CTkFrame):
    """Display one image as a resizable GM Table window."""

    def __init__(self, master, *, image_path: str, title: str = "Image") -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._image_path = str(image_path or "").strip()
        self._title = str(title or Path(self._image_path).name or "Image")
        self._ctk_image: ctk.CTkImage | None = None
        self._source_image: Image.Image | None = None

        ctk.CTkLabel(
            self,
            text=self._title,
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.image_label = ctk.CTkLabel(self, text="Loading image…", anchor="center")
        self.image_label.grid(row=1, column=0, sticky="nsew")
        self.bind("<Configure>", self._refresh_image, add="+")
        self._load_image()

    def _resolve_image_path(self) -> str | None:
        return resolve_portrait_candidate(
            self._image_path, ConfigHelper.get_campaign_dir()
        )

    def _load_image(self) -> None:
        resolved = self._resolve_image_path()
        if not resolved:
            self.image_label.configure(
                text=f"Image not found:\n{self._image_path}", image=None
            )
            return
        try:
            self._source_image = Image.open(resolved).convert("RGBA")
        except Exception as exc:
            self.image_label.configure(text=f"Unable to load image:\n{exc}", image=None)
            return
        self._refresh_image()

    def _refresh_image(self, _event=None) -> None:
        if self._source_image is None:
            return
        width = max(160, int(self.winfo_width() or IMAGE_PANEL_SIZE[0]) - 24)
        height = max(120, int(self.winfo_height() or IMAGE_PANEL_SIZE[1]) - 58)
        render = self._source_image.copy()
        render.thumbnail((width, height), Image.Resampling.LANCZOS)
        if render.width <= 0 or render.height <= 0:
            return
        self._ctk_image = ctk.CTkImage(
            light_image=render, dark_image=render, size=render.size
        )
        self.image_label.configure(text="", image=self._ctk_image)

    def get_state(self) -> dict:
        return {"image_path": self._image_path, "image_title": self._title}


class GMTableAttachmentGallery(ctk.CTkFrame):
    """Compact gallery for entity attachments on the GM Table."""

    def __init__(self, master, *, attachments: list[EntityAttachment]) -> None:
        super().__init__(master, fg_color="transparent")
        self._images: list[ctk.CTkImage] = []
        self.grid_columnconfigure(0, weight=1)
        title = f"Attachments ({len(attachments)})"
        ctk.CTkLabel(
            self, text=title, font=ctk.CTkFont(size=15, weight="bold"), anchor="w"
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="ew")
        for index, attachment in enumerate(attachments):
            card = ctk.CTkFrame(body, corner_radius=12)
            card.grid(row=index // 2, column=index % 2, sticky="ew", padx=6, pady=6)
            card.grid_columnconfigure(0, weight=1)
            if attachment.is_image and attachment.resolved_path:
                self._add_image_preview(card, attachment)
            else:
                ctk.CTkLabel(card, text="📎", font=ctk.CTkFont(size=28)).grid(
                    row=0, column=0, pady=(10, 2)
                )
            ctk.CTkLabel(
                card, text=attachment.label, wraplength=220, justify="center"
            ).grid(row=1, column=0, padx=10, pady=(2, 10), sticky="ew")

    def _add_image_preview(self, parent, attachment: EntityAttachment) -> None:
        try:
            image = Image.open(attachment.resolved_path).convert("RGBA")
            image.thumbnail((220, 150), Image.Resampling.LANCZOS)
            ctk_image = ctk.CTkImage(
                light_image=image, dark_image=image, size=image.size
            )
            self._images.append(ctk_image)
            ctk.CTkLabel(parent, text="", image=ctk_image).grid(
                row=0, column=0, padx=10, pady=(10, 2)
            )
        except Exception:
            ctk.CTkLabel(parent, text="🖼", font=ctk.CTkFont(size=28)).grid(
                row=0, column=0, pady=(10, 2)
            )


class GMTableImageLibraryPage(ctk.CTkFrame):
    """Embedded shared image library browser."""

    def __init__(
        self,
        master,
        *,
        initial_state: dict | None = None,
        on_attach_to_table: Callable[[ImageResult], None] | None = None,
    ) -> None:
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
            on_attach_to_entity=on_attach_to_table,
            on_toolbar_state_changed=self._on_toolbar_state_changed,
        )
        self._panel.grid(row=0, column=0, sticky="nsew")
        self._load_records()

    def _load_records(self) -> None:
        """Fetch and map image records for the browser."""
        toolbar_state = self._panel.toolbar.state
        selected_folder = (toolbar_state.folder_name or "").strip()
        filters = (
            {"source_folder_names": [selected_folder]}
            if selected_folder and selected_folder != "All"
            else None
        )
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
