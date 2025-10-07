"""Virtualized object catalog views used by the application."""

from __future__ import annotations

import os
from collections.abc import Iterable as IterableABC
from functools import lru_cache
from typing import Callable, Iterable, Optional

import customtkinter as ctk
from tkinter import ttk
from PIL import Image

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_module_import


OBJECT_VIEW_SECTION = "ObjectCatalogView"
OBJECT_VIEW_KEY = "mode"
OBJECT_VIEW_CLASSIC = "classic"
OBJECT_VIEW_EXPLORER = "explorer"
_OBJECT_VIEW_LEGACY_MAP = {"accordion": OBJECT_VIEW_EXPLORER}


def _normalize_mode(raw: str) -> str:
    normalized = (raw or "").strip().lower()
    if normalized in (OBJECT_VIEW_CLASSIC, OBJECT_VIEW_EXPLORER):
        return normalized
    return _OBJECT_VIEW_LEGACY_MAP.get(normalized, OBJECT_VIEW_CLASSIC)


def load_object_catalog_mode() -> str:
    """Return the persisted object catalog display mode."""

    cfg = ConfigHelper.load_campaign_config()
    if cfg.has_section(OBJECT_VIEW_SECTION):
        raw = cfg.get(OBJECT_VIEW_SECTION, OBJECT_VIEW_KEY, fallback="")
        mode = _normalize_mode(raw)
        if mode in (OBJECT_VIEW_CLASSIC, OBJECT_VIEW_EXPLORER):
            return mode
    return OBJECT_VIEW_CLASSIC


def save_object_catalog_mode(mode: str) -> None:
    """Persist the object catalog display mode to the campaign settings."""

    normalized = _normalize_mode(mode)
    cfg = ConfigHelper.load_campaign_config()
    if not cfg.has_section(OBJECT_VIEW_SECTION):
        cfg.add_section(OBJECT_VIEW_SECTION)
    cfg.set(OBJECT_VIEW_SECTION, OBJECT_VIEW_KEY, normalized)
    settings_path = ConfigHelper.get_campaign_settings_path()
    with open(settings_path, "w", encoding="utf-8") as f:
        cfg.write(f)
    try:
        ConfigHelper._campaign_mtime = os.path.getmtime(settings_path)
    except OSError:
        pass


class ObjectExplorerCatalog(ctk.CTkFrame):
    """High-performance object catalog using a ttk Treeview with lazy loading."""

    def __init__(
        self,
        master,
        *,
        resolve_media_path: Optional[Callable[[str], Optional[str]]] = None,
        on_edit_item: Optional[Callable[[dict], None]] = None,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._resolve_media_path = resolve_media_path
        self._on_edit_item = on_edit_item

        self._items: list[dict] = []
        self._item_lookup: dict[str, dict] = {}
        self._loaded_count = 0
        self._page_size = 80
        self._load_job: Optional[str] = None
        self._stats_field = "Stats"
        self._description_field = "Description"
        self._secrets_field = "Secrets"
        self._category_field = "Category"
        self._portrait_field: Optional[str] = None
        self._unique_field = "Name"
        self._current_portrait: Optional[ctk.CTkImage] = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=3)

        self._list_container = ctk.CTkFrame(self, fg_color="transparent")
        self._list_container.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=4)
        self._list_container.grid_rowconfigure(0, weight=1)
        self._list_container.grid_columnconfigure(0, weight=1)

        self._style = ttk.Style(self)
        try:
            self._style.theme_use("clam")
        except Exception:
            pass
        self._style.configure(
            "ObjectCatalog.Treeview",
            background="#1B1B1B",
            foreground="#F0F0F0",
            fieldbackground="#1B1B1B",
            bordercolor="#3C3C3C",
            rowheight=32,
            font=("Segoe UI", 12),
        )
        self._style.configure(
            "ObjectCatalog.Treeview.Heading",
            background="#2B2B2B",
            foreground="#F0F0F0",
            font=("Segoe UI", 12, "bold"),
        )
        self._style.map(
            "ObjectCatalog.Treeview",
            background=[("selected", "#385070")],
            foreground=[("selected", "#FFFFFF")],
        )

        self._tree = ttk.Treeview(
            self._list_container,
            columns=("name", "category", "preview"),
            show="headings",
            style="ObjectCatalog.Treeview",
            selectmode="browse",
        )
        self._tree.heading("name", text="Name")
        self._tree.heading("category", text="Category")
        self._tree.heading("preview", text="Stats Preview")
        self._tree.column("name", width=240, minwidth=200, anchor="w")
        self._tree.column("category", width=160, minwidth=120, anchor="w")
        self._tree.column("preview", width=360, minwidth=240, anchor="w")
        self._tree.grid(row=0, column=0, sticky="nsew")

        self._tree_scrollbar = ttk.Scrollbar(
            self._list_container, orient="vertical", command=self._tree.yview
        )
        self._tree_scrollbar.grid(row=0, column=1, sticky="ns")
        self._tree.configure(yscrollcommand=self._on_tree_scroll)

        self._tree.bind("<<TreeviewSelect>>", self._handle_selection)
        self._tree.bind("<Double-1>", self._on_tree_double_click)
        self._tree.bind("<Return>", lambda _e: self._open_selected())
        self._tree.bind("<KeyRelease-Up>", self._handle_keyboard_navigation)
        self._tree.bind("<KeyRelease-Down>", self._handle_keyboard_navigation)

        self._detail_frame = ctk.CTkFrame(self, corner_radius=12, fg_color="#1E1E1E")
        self._detail_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=4)
        self._detail_frame.grid_columnconfigure(0, weight=1)
        self._detail_frame.grid_columnconfigure(1, weight=0)
        self._detail_frame.grid_rowconfigure(5, weight=1)
        self._detail_frame.grid_rowconfigure(7, weight=1)
        self._detail_frame.grid_rowconfigure(9, weight=1)

        self._empty_message = ctk.CTkLabel(
            self._detail_frame,
            text="Select an object to view its details.",
            font=("Segoe UI", 14, "italic"),
            text_color="#B4B4B4",
        )
        self._empty_message.grid(row=0, column=0, columnspan=2, padx=16, pady=16, sticky="nsew")

        self._title_label = ctk.CTkLabel(
            self._detail_frame,
            text="",
            font=("Segoe UI", 20, "bold"),
            anchor="w",
        )
        self._title_label.grid(row=0, column=0, sticky="w", padx=16, pady=(18, 4))
        self._title_label.grid_remove()

        self._category_label = ctk.CTkLabel(
            self._detail_frame,
            text="",
            font=("Segoe UI", 14),
            text_color="#B4B4B4",
            anchor="w",
        )
        self._category_label.grid(row=1, column=0, sticky="w", padx=16)
        self._category_label.grid_remove()

        self._portrait_label = ctk.CTkLabel(self._detail_frame, text="")
        self._portrait_label.grid(row=0, column=1, rowspan=6, sticky="ne", padx=16, pady=16)
        self._portrait_label.grid_remove()

        self._stats_heading = ctk.CTkLabel(
            self._detail_frame,
            text="Stats",
            font=("Segoe UI", 13, "bold"),
            anchor="w",
        )
        self._stats_heading.grid(row=2, column=0, sticky="w", padx=16, pady=(8, 4))
        self._stats_heading.grid_remove()

        self._stats_box = ctk.CTkTextbox(
            self._detail_frame,
            wrap="word",
            height=120,
            fg_color="#242424",
        )
        self._stats_box.grid(row=3, column=0, sticky="nsew", padx=16)
        self._stats_box.configure(state="disabled")
        self._stats_box.grid_remove()

        self._description_heading = ctk.CTkLabel(
            self._detail_frame,
            text="Description",
            font=("Segoe UI", 13, "bold"),
            anchor="w",
        )
        self._description_heading.grid(row=4, column=0, sticky="w", padx=16, pady=(12, 4))
        self._description_heading.grid_remove()

        self._description_box = ctk.CTkTextbox(
            self._detail_frame,
            wrap="word",
            height=140,
            fg_color="#242424",
        )
        self._description_box.grid(row=5, column=0, sticky="nsew", padx=16)
        self._description_box.configure(state="disabled")
        self._description_box.grid_remove()

        self._secrets_heading = ctk.CTkLabel(
            self._detail_frame,
            text="Secrets",
            font=("Segoe UI", 13, "bold"),
            anchor="w",
        )
        self._secrets_heading.grid(row=6, column=0, sticky="w", padx=16, pady=(12, 4))
        self._secrets_heading.grid_remove()

        self._secrets_box = ctk.CTkTextbox(
            self._detail_frame,
            wrap="word",
            height=120,
            fg_color="#242424",
        )
        self._secrets_box.grid(row=7, column=0, sticky="nsew", padx=16)
        self._secrets_box.configure(state="disabled")
        self._secrets_box.grid_remove()

        self._edit_button = ctk.CTkButton(
            self._detail_frame,
            text="Open in Editor",
            command=self._open_selected,
            state="disabled",
        )
        self._edit_button.grid(row=8, column=0, sticky="e", padx=16, pady=(16, 16))
        self._edit_button.grid_remove()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_text(value: Optional[object]) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            parts = []
            for key, sub_value in value.items():
                key_text = str(key).strip()
                sub_text = ObjectExplorerCatalog._normalize_text(sub_value)
                if sub_text:
                    parts.append(f"{key_text}: {sub_text}")
                else:
                    parts.append(key_text)
            return "\n".join(part for part in parts if part)
        if isinstance(value, IterableABC) and not isinstance(value, (bytes, bytearray, str)):
            items = [ObjectExplorerCatalog._normalize_text(v) for v in value]
            items = [item for item in items if item]
            return "\n".join(
                f"• {item}" if not item.startswith("• ") else item for item in items
            )
        return str(value).strip()

    @staticmethod
    def _inline_text(value: Optional[object]) -> str:
        text = ObjectExplorerCatalog._normalize_text(value)
        return ", ".join(part for part in (segment.strip() for segment in text.splitlines()) if part)

    @staticmethod
    def _stats_preview(stats: str, limit: int = 180) -> str:
        if not stats:
            return "No stats available"
        collapsed = " ".join(stats.split())
        if len(collapsed) > limit:
            return collapsed[:limit].rstrip() + "..."
        return collapsed

    def _set_textbox(self, widget: ctk.CTkTextbox, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        if text:
            widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _clear_details(self, message: str = "Select an object to view its details.") -> None:
        self._empty_message.configure(text=message)
        self._empty_message.grid()
        for widget in (
            self._title_label,
            self._category_label,
            self._portrait_label,
            self._stats_heading,
            self._stats_box,
            self._description_heading,
            self._description_box,
            self._secrets_heading,
            self._secrets_box,
            self._edit_button,
        ):
            widget.grid_remove()
        self._title_label.configure(text="")
        self._category_label.configure(text="")
        self._portrait_label.configure(image=None)
        self._current_portrait = None
        self._set_textbox(self._stats_box, "")
        self._set_textbox(self._description_box, "")
        self._set_textbox(self._secrets_box, "")
        self._edit_button.configure(state="disabled")

    # ------------------------------------------------------------------
    # Tree management
    # ------------------------------------------------------------------
    def _clear_tree(self) -> None:
        if self._load_job:
            try:
                self.after_cancel(self._load_job)
            except Exception:
                pass
            self._load_job = None
        for iid in self._tree.get_children():
            self._tree.delete(iid)
        self._item_lookup.clear()
        self._items = []
        self._loaded_count = 0

    def _on_tree_scroll(self, first: str, last: str) -> None:
        self._tree_scrollbar.set(first, last)
        try:
            last_float = float(last)
        except (TypeError, ValueError):
            last_float = 0.0
        if self._loaded_count < len(self._items) and last_float > 0.98:
            if not self._load_job:
                self._load_job = self.after(20, self._load_next_batch)

    def _load_next_batch(self, reset_selection: bool = False) -> None:
        self._load_job = None
        total = len(self._items)
        if self._loaded_count >= total:
            return
        batch_size = self._page_size
        start = self._loaded_count
        end = min(start + batch_size, total)
        for index in range(start, end):
            item = self._items[index]
            name = self._inline_text(item.get(self._unique_field) or item.get("Name"))
            if not name:
                name = "Unnamed Object"
            category = self._inline_text(item.get(self._category_field))

            @lru_cache(maxsize=1)
            def stats_value(_item=item):
                return self._normalize_text(_item.get(self._stats_field))

            preview = self._stats_preview(stats_value())
            iid = f"item-{index}"
            self._tree.insert("", "end", iid=iid, values=(name, category, preview))
            self._item_lookup[iid] = {
                "item": item,
                "stats_provider": stats_value,
            }
        self._loaded_count = end

        if reset_selection and self._items:
            first = self._tree.get_children()
            if first:
                self._tree.selection_set(first[0])
                self._tree.focus(first[0])
                self._show_details(first[0])

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _handle_selection(self, _event=None) -> None:
        selection = self._tree.selection()
        if not selection:
            self._clear_details()
            return
        iid = selection[0]
        self._show_details(iid)

    def _handle_keyboard_navigation(self, _event=None) -> None:
        self.after_idle(self._handle_selection)

    def _on_tree_double_click(self, event) -> None:
        row = self._tree.identify_row(event.y)
        if not row:
            return
        self._tree.selection_set(row)
        self._tree.focus(row)
        self._show_details(row)
        self._open_selected()

    # ------------------------------------------------------------------
    # Detail panel population
    # ------------------------------------------------------------------
    def _show_details(self, iid: str) -> None:
        payload = self._item_lookup.get(iid)
        if not payload:
            self._clear_details()
            return
        item = payload["item"]
        stats_provider = payload["stats_provider"]

        self._empty_message.grid_remove()
        self._title_label.grid()
        self._category_label.grid()
        self._edit_button.grid()

        name = self._inline_text(item.get(self._unique_field) or item.get("Name"))
        if not name:
            name = "Unnamed Object"
        category = self._inline_text(item.get(self._category_field))

        self._title_label.configure(text=name)
        self._category_label.configure(text=category or "")
        self._edit_button.configure(state="normal")

        stats_text = stats_provider()
        if stats_text:
            self._stats_heading.grid()
            self._stats_box.grid()
            self._set_textbox(self._stats_box, stats_text)
        else:
            self._stats_heading.grid_remove()
            self._stats_box.grid_remove()
            self._set_textbox(self._stats_box, "")

        if self._description_field:
            description = self._normalize_text(item.get(self._description_field))
        else:
            description = ""
        if description:
            self._description_heading.grid()
            self._description_box.grid()
            self._set_textbox(self._description_box, description)
        else:
            self._description_heading.grid_remove()
            self._description_box.grid_remove()
            self._set_textbox(self._description_box, "")

        if self._secrets_field:
            secrets = self._normalize_text(item.get(self._secrets_field))
        else:
            secrets = ""
        if secrets:
            self._secrets_heading.grid()
            self._secrets_box.grid()
            self._set_textbox(self._secrets_box, secrets)
        else:
            self._secrets_heading.grid_remove()
            self._secrets_box.grid_remove()
            self._set_textbox(self._secrets_box, "")

        portrait_path = None
        if self._portrait_field:
            value = item.get(self._portrait_field)
            if isinstance(value, str):
                portrait_path = value.strip() or None
            elif value is not None:
                portrait_path = str(value).strip() or None

        if portrait_path and self._resolve_media_path:
            resolved = self._resolve_media_path(portrait_path)
        else:
            resolved = None

        if resolved:
            try:
                with Image.open(resolved) as img:
                    preview = img.copy()
                if hasattr(Image, "Resampling"):
                    preview.thumbnail((220, 220), Image.Resampling.LANCZOS)
                else:
                    preview.thumbnail((220, 220), Image.LANCZOS)
                self._current_portrait = ctk.CTkImage(
                    light_image=preview, dark_image=preview, size=preview.size
                )
                self._portrait_label.configure(image=self._current_portrait, text="")
                self._portrait_label.grid()
            except Exception:
                self._portrait_label.grid_remove()
                self._portrait_label.configure(image=None, text="")
                self._current_portrait = None
        else:
            self._portrait_label.grid_remove()
            self._portrait_label.configure(image=None, text="")
            self._current_portrait = None

        self._detail_frame.update_idletasks()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def populate(
        self,
        items: Iterable[dict],
        *,
        unique_field: str = "Name",
        stats_field: str = "Stats",
        description_field: str = "Description",
        secrets_field: str = "Secrets",
        category_field: str = "Category",
        portrait_field: Optional[str] = None,
    ) -> None:
        """Populate the catalog with the provided object entries."""

        self._clear_tree()
        item_list = list(items or [])
        message = (
            "Select an object to view its details." if item_list else "No objects to display"
        )
        self._clear_details(message)

        self._items = item_list
        self._unique_field = unique_field or "Name"
        self._stats_field = stats_field or "Stats"
        self._description_field = description_field or ""
        self._secrets_field = secrets_field or ""
        self._category_field = category_field or "Category"
        self._portrait_field = portrait_field
        self._page_size = 120 if len(item_list) > 600 else 80

        if not item_list:
            return

        self._load_next_batch(reset_selection=True)

    def _open_selected(self) -> None:
        if not callable(self._on_edit_item):
            return
        selection = self._tree.selection()
        if not selection:
            return
        payload = self._item_lookup.get(selection[0])
        if not payload:
            return
        item = payload.get("item")
        if not isinstance(item, dict):
            return
        try:
            self._on_edit_item(item)
        except Exception:
            pass


log_module_import(__name__)
