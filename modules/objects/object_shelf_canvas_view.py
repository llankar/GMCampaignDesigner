"""Canvas‑based shelf view for object entities.

This implementation focuses on fast drawing with a background image and
category shelves that span the full width. It exposes the same minimal
public API the app expects from the previous view:

- is_available() -> bool
- is_visible() -> bool
- show(before_widget)
- hide()
- populate()
- refresh_selection()
- update_summary()
- start_visibility_monitor()/stop_visibility_monitor()

It draws only category shelves (not individual items) for performance and
clarity; counts are shown per category. The background image is scaled to
the canvas and shelves are drawn as semi‑transparent rounded panels so the
background remains visible behind them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk
from modules.helpers.text_helpers import rtf_to_html, format_multiline_text
try:
    from tkhtmlview import HTMLLabel  # type: ignore
except Exception:
    HTMLLabel = None  # fallback to plain textbox


@dataclass
class _ShelfRow:
    category_key: str
    display: str
    count: int
    items: List[dict]
    expanded: bool = False
    y1: int = 0
    y2: int = 0
    content_y1: int = 0
    content_y2: int = 0


class ObjectShelfView:
    """Canvas‑based shelves with background image."""

    def __init__(self, host, allowed_categories: Sequence[str]):
        self.host = host
        self.allowed_categories = list(allowed_categories)

        self.frame = ctk.CTkFrame(host, fg_color="transparent")

        # Search bar (uses host.search_var if present)
        self.search_frame: Optional[ctk.CTkFrame] = None
        self.search_entry: Optional[ctk.CTkEntry] = None
        self.search_button: Optional[ctk.CTkButton] = None
        self._build_search_bar()

        # Summary bar (text updated by update_summary())
        self.summary_bar = ctk.CTkFrame(
            self.frame,
            fg_color="#242424",
            corner_radius=12,
            border_width=1,
            border_color="#404040",
        )
        self.summary_bar.pack(fill="x", padx=10, pady=((6, 0) if self.search_frame else (10, 0)))
        self.summary_label = ctk.CTkLabel(
            self.summary_bar, text="", font=("Segoe UI", 12, "bold"), anchor="w"
        )
        self.summary_label.pack(fill="x", padx=12, pady=6)

        # Scrollable canvas
        self.canvas_holder = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.canvas_holder.pack(fill="both", expand=True, padx=10, pady=10)
        self.canvas = tk.Canvas(
            self.canvas_holder,
            highlightthickness=0,
            bd=0,
            bg="#0e0e0e",
        )
        self.vscroll = tk.Scrollbar(
            self.canvas_holder, orient="vertical", command=self.canvas.yview
        )
        self.canvas.configure(yscrollcommand=self.vscroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vscroll.pack(side="right", fill="y")

        # Background image handling
        self._bg_source: Optional[Image.Image] = None
        self._bg_photo: Optional[ImageTk.PhotoImage] = None
        self._bg_item: Optional[int] = None
        self._load_background()

        # Shelf rows and drawing cache
        self._rows: List[_ShelfRow] = []
        self._panel_cache: Dict[Tuple[int, int], ImageTk.PhotoImage] = {}
        self._item_by_tag: Dict[str, dict] = {}
        self._detail_panel: Optional[ctk.CTkFrame] = None
        self._detail_body: Optional[ctk.CTkScrollableFrame] = None
        self._detail_title: Optional[ctk.CTkLabel] = None
        self._detail_meta: Optional[ctk.CTkLabel] = None
        self._detail_desc: Optional[ctk.CTkTextbox] = None
        self._detail_html_label = None

        # Bindings
        self.canvas.bind("<Configure>", self._on_canvas_configure, add=True)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel, add=True)
        self.canvas.bind("<Button-1>", self._on_click, add=True)

        # Simple throttling for redraw
        self._pending_redraw: Optional[str] = None

    # ----- Public API ----------------------------------------------------
    def is_available(self) -> bool:
        return getattr(self.host.model_wrapper, "entity_type", None) == "objects"

    def is_visible(self) -> bool:
        return bool(self.frame.winfo_manager())

    def show(self, before_widget):
        self.frame.pack(fill="both", expand=True, padx=5, pady=5, before=before_widget)

    def hide(self):
        self.frame.pack_forget()
        self.stop_visibility_monitor()

    def populate(self):
        if not self.is_available():
            return
        self._rows = self._build_rows()
        self._expand_rows_for_search()
        self._request_redraw()
        self.update_summary()

    def refresh_selection(self):
        # No per‑item selection in this canvas view; no‑op for compatibility
        return

    def update_summary(self):
        total = len(getattr(self.host, "filtered_items", []) or [])
        filters = []
        query = self._current_search_query()
        if query:
            filters.append(f'Search: "{query}"')
        if getattr(self.host, "filtered_items", None) is not getattr(self.host, "items", None) and not query:
            filters.append("Additional filters active")
        filter_text = " | ".join(filters) if filters else "No active filters"
        self.summary_label.configure(
            text=f"Visible items: {total}  |  {filter_text}"
        )

    def _build_search_bar(self):
        var = getattr(self.host, "search_var", None)
        if var is None:
            return
        self.search_frame = ctk.CTkFrame(
            self.frame,
            fg_color="#242424",
            corner_radius=12,
            border_width=1,
            border_color="#404040",
        )
        self.search_frame.pack(fill="x", padx=10, pady=(10, 0))
        self.search_entry = ctk.CTkEntry(
            self.search_frame,
            textvariable=var,
            placeholder_text="Search objects...",
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(12, 6), pady=6)
        self.search_entry.bind("<Return>", self._trigger_search)
        self.search_button = ctk.CTkButton(
            self.search_frame,
            text="Search",
            command=self._trigger_search,
            corner_radius=18,
            width=90,
        )
        self.search_button.pack(side="left", padx=(0, 12), pady=6)

    def _trigger_search(self, event=None):
        var = getattr(self.host, "search_var", None)
        if var is None or not hasattr(self.host, "filter_items"):
            return "break" if event is not None else None
        self.host.filter_items(var.get())
        return "break" if event is not None else None

    def _current_search_query(self) -> str:
        var = getattr(self.host, "search_var", None)
        if var is None:
            return ""
        try:
            return (var.get() or "").strip()
        except Exception:
            return ""

    def _expand_rows_for_search(self):
        q = self._current_search_query()
        if not q:
            return
        for row in self._rows:
            if row.count > 0:
                row.expanded = True

    def start_visibility_monitor(self):
        # Keep background and panels sized properly during idle
        self.stop_visibility_monitor()
        self._visibility_job = self.host.after(250, self._on_visibility_tick)

    def stop_visibility_monitor(self):
        job = getattr(self, "_visibility_job", None)
        if job is not None:
            try:
                self.host.after_cancel(job)
            except Exception:
                pass
        self._visibility_job = None

    # ----- Internals -----------------------------------------------------
    def _load_background(self):
        image_path = Path(__file__).resolve().parents[2] / "assets" / "objects_shelves_background.jpg"
        if image_path.exists():
            try:
                with Image.open(image_path) as img:
                    self._bg_source = img.convert("RGBA")
            except Exception:
                self._bg_source = None

    def _on_visibility_tick(self):
        # Redraw if needed and keep monitoring while visible
        if self.is_visible():
            self._request_redraw()
            self._visibility_job = self.host.after(500, self._on_visibility_tick)

    def _on_mousewheel(self, event):
        if getattr(self.host, "view_mode", "") != "shelf":
            return
        delta = -1 * (event.delta if event.delta else 0)
        self.canvas.yview_scroll(int(delta / 120), "units")

    def _on_detail_mousewheel(self, event):
        # Scroll only the detail body's own scrollable area and stop propagation
        body = getattr(self, "_detail_body", None)
        if body is None or not body.winfo_exists():
            return
        inner_canvas = getattr(body, "_parent_canvas", None)
        if inner_canvas is None:
            return "break"
        delta = -1 * (event.delta if event.delta else 0)
        inner_canvas.yview_scroll(int(delta / 120), "units")
        return "break"

    def _on_canvas_configure(self, _event):
        self._request_redraw()

    def _request_redraw(self):
        if self._pending_redraw is not None:
            return
        try:
            self._pending_redraw = self.host.after_idle(self._redraw)
        except Exception:
            self._redraw()

    def _redraw(self):
        self._pending_redraw = None
        w = max(self.canvas.winfo_width(), 1)
        h = max(self.canvas.winfo_height(), 1)
        self._ensure_background(w, h)
        self.canvas.delete("shelf")
        self._item_by_tag.clear()

        # Layout parameters
        margin_x = 16
        margin_y = 12
        shelf_h = 64
        spacing = 14
        y = margin_y

        # Determine visible vertical span for cheap virtualization of expanded items
        view_top = self.canvas.canvasy(0)
        view_bottom = view_top + h

        # Draw rows
        for row in self._rows:
            row.y1 = y
            row.y2 = y + shelf_h
            self._draw_shelf_row(0, row.y1, w, row.y2, row)
            y = row.y2 + spacing
            # Expanded content
            self.canvas.delete(f"items:{row.category_key}")
            if row.expanded:
                content_h = self._measure_items_height(w - 2 * margin_x, row)
                row.content_y1 = y
                row.content_y2 = y + content_h
                # Draw container panel
                panel = self._get_panel_image(w - 2 * margin_x, content_h, radius=12)
                self.canvas.create_image(
                    margin_x, y, image=panel, anchor="nw", tags=("shelf", f"items:{row.category_key}")
                )
                self.canvas.image = getattr(self.canvas, "image", [])
                self.canvas.image.append(panel)
                # Draw items only if within viewport (with small buffer)
                buffer_px = 200
                if row.content_y2 >= view_top - buffer_px and row.content_y1 <= view_bottom + buffer_px:
                    self._draw_row_items(margin_x, y, w - margin_x, row)
                y = row.content_y2 + spacing

        # Scroll region
        total_h = max(h, y + margin_y)
        self.canvas.configure(scrollregion=(0, 0, w, total_h))

    def _ensure_background(self, w: int, h: int):
        # Scale/crop background to fill the canvas
        if not self._bg_source:
            # fallback to a solid rect so drawing order stays stable
            if self._bg_item is None:
                self._bg_item = self.canvas.create_rectangle(
                    0, 0, w, h, fill="#101010", width=0, tags=("bg",)
                )
            self.canvas.coords(self._bg_item, 0, 0, w, h)
            return

        src_w, src_h = self._bg_source.size
        scale = max(w / src_w, h / src_h)
        new_w, new_h = int(src_w * scale), int(src_h * scale)
        img = self._bg_source.resize((new_w, new_h), Image.LANCZOS)
        # center crop
        left = max(0, (new_w - w) // 2)
        top = max(0, (new_h - h) // 2)
        img = img.crop((left, top, left + w, top + h))
        self._bg_photo = ImageTk.PhotoImage(img)
        if self._bg_item is None:
            self._bg_item = self.canvas.create_image(0, 0, image=self._bg_photo, anchor="nw", tags=("bg",))
        else:
            self.canvas.itemconfigure(self._bg_item, image=self._bg_photo)
        self.canvas.tag_lower("bg")

    def _draw_shelf_row(self, x1: int, y1: int, x2: int, y2: int, row: _ShelfRow):
        width = max(1, x2 - x1)
        height = max(1, y2 - y1)
        # Guard against very small widths during early geometry phases
        panel_w = max(1, width - 32)
        panel_h = max(1, height)
        panel = self._get_panel_image(panel_w, panel_h, radius=16)
        img_item = self.canvas.create_image(
            x1 + 16, y1, image=panel, anchor="nw", tags=("shelf", f"row:{row.category_key}")
        )
        # Keep a reference via canvas tag binding
        self.canvas.image = getattr(self.canvas, "image", [])
        self.canvas.image.append(panel)

        # Centered text: "CATEGORY • 77 items"
        label = f"{row.display.upper()} • {row.count} items"
        self.canvas.create_text(
            (x1 + x2) // 2,
            y1 + height // 2,
            text=label,
            fill="#e9e9e9",
            font=("Segoe UI", 14, "bold"),
            anchor="center",
            tags=("shelf", f"row:{row.category_key}"),
        )

    def _get_panel_image(self, width: int, height: int, radius: int = 12) -> ImageTk.PhotoImage:
        key = (width, height)
        cached = self._panel_cache.get(key)
        if cached is not None:
            return cached
        # Semi‑transparent dark panel with subtle border and inner highlights
        width = max(1, int(width))
        height = max(1, int(height))
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        r = radius
        # Background panel with alpha to see background through
        fill = (20, 20, 20, 185)
        border = (0, 0, 0, 180)
        self._rounded_rect(draw, (0, 0, width, height), r, fill=fill, outline=border, width=2)
        # Top highlight (skip if too small)
        if width >= 4 and height >= 4 and r >= 2:
            x2 = max(2, width - 2)
            y2 = max(2, height // 2)
            self._rounded_rect(draw, (1, 1, x2, y2), max(0, r - 2), fill=(255, 255, 255, 18))
        photo = ImageTk.PhotoImage(img)
        self._panel_cache[key] = photo
        return photo

    @staticmethod
    def _rounded_rect(draw: ImageDraw.ImageDraw, box, radius, fill=None, outline=None, width: int = 1):
        x1, y1, x2, y2 = box
        if radius <= 0:
            draw.rectangle(box, fill=fill, outline=outline, width=width)
            return
        # Corners
        draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)

    def _build_rows(self) -> List[_ShelfRow]:
        # Group filtered items by normalized category
        items = getattr(self.host, "filtered_items", []) or []
        groups: Dict[str, Tuple[str, List[dict]]] = {}
        for item in items:
            raw = (
                item.get("Category")
                or item.get("category")
                or item.get("Type")
                or item.get("type")
                or "Uncategorized"
            )
            display = self._normalize_category_display(raw)
            key = display.casefold()
            bucket = groups.get(key)
            if bucket is None:
                groups[key] = (display, [item])
            else:
                bucket[1].append(item)

        ordered: List[_ShelfRow] = []
        allowed_keys = [c.casefold() for c in self.allowed_categories]
        # First, add allowed in given order if present
        for ak in allowed_keys:
            if ak in groups:
                disp, lst = groups.pop(ak)
                ordered.append(_ShelfRow(ak, disp, len(lst), lst))
        # Then add any remaining alphabetically
        for key, (disp, lst) in sorted(groups.items(), key=lambda kv: kv[0]):
            ordered.append(_ShelfRow(key, disp, len(lst), lst))
        return ordered

    @staticmethod
    def _normalize_category_display(value: object) -> str:
        text = str(value or "").strip()
        if not text:
            return "Uncategorized"
        return text

    # ----- Interaction & item drawing -----------------------------------
    def _find_row_by_y(self, y: int) -> Optional[_ShelfRow]:
        for row in self._rows:
            if row.y1 <= y <= row.y2:
                return row
        return None

    def _on_click(self, event):
        if getattr(self.host, "view_mode", "") != "shelf":
            return
        y = self.canvas.canvasy(event.y)
        row = self._find_row_by_y(y)
        if row is None:
            return
        row.expanded = not row.expanded
        # Collapse others for simplicity and speed
        for other in self._rows:
            if other is not row:
                other.expanded = False
        self._request_redraw()

    def _measure_items_height(self, inner_width: int, row: _ShelfRow) -> int:
        padding = 16
        tile_h = 30
        min_tile_w = 180
        cols = max(1, inner_width // min_tile_w)
        rows = (len(row.items) + cols - 1) // cols
        return padding * 2 + rows * tile_h + (rows - 1) * 6

    def _draw_row_items(self, x: int, y: int, right: int, row: _ShelfRow):
        inner_width = right - x
        padding = 16
        tile_h = 30
        min_tile_w = 180
        gap_x = 10
        gap_y = 6
        cols = max(1, inner_width // min_tile_w)
        col_w = (inner_width - padding * 2 - (cols - 1) * gap_x) // cols
        # Draw chips (rectangle + text) with one canvas item per chip + text
        items_tag = ("shelf", f"items:{row.category_key}")
        ox = x + padding
        oy = y + padding
        for idx, item in enumerate(row.items):
            r, c = divmod(idx, cols)
            iy = oy + r * (tile_h + gap_y)
            ix = ox + c * (col_w + gap_x)
            # background chip (semi‑transparent)
            tag = f"obj:{row.category_key}:{idx}"
            rect = self.canvas.create_rectangle(
                ix, iy, ix + col_w, iy + tile_h,
                fill="#2a2a2a",
                outline="#000000",
                width=1,
                tags=items_tag + (tag,),
            )
            name = str(item.get("Name") or item.get("name") or "Unnamed")
            self.canvas.create_text(
                ix + col_w // 2,
                iy + tile_h // 2,
                text=name,
                fill="#dddddd",
                font=("Segoe UI", 12),
                anchor="center",
                tags=items_tag + (tag,),
            )
            # Map tag to item and bind click
            self._item_by_tag[tag] = item
        # Bind once per draw call for all new item tags
        # Use a generic pattern and resolve via current tag under cursor
        self.canvas.tag_bind("shelf", "<Button-1>", self._on_item_click)

    def _on_item_click(self, event):
        # Determine if an item chip was clicked and open its editor
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        items = self.canvas.find_overlapping(x, y, x, y)
        for item_id in reversed(items):  # topmost first
            tags = self.canvas.gettags(item_id)
            for t in tags:
                if t.startswith("obj:"):
                    it = self._item_by_tag.get(t)
                    if it is not None:
                        self._show_item_detail(it)
                        return "break"
        return None

    # ----- Detail panel --------------------------------------------------
    def _ensure_detail_panel(self):
        if self._detail_panel and self._detail_panel.winfo_exists():
            return
        panel = ctk.CTkFrame(
            self.frame,
            fg_color="#171717",
            corner_radius=12,
            border_width=1,
            border_color="#2a2a2a",
            height=160,
        )
        # Dock to the bottom; full width, fixed height
        panel.place(relx=0.0, rely=1.0, relwidth=1.0, anchor="sw", x=0, y=-10)
        header = ctk.CTkFrame(panel, fg_color="#1f1f1f", corner_radius=10)
        header.pack(fill="x", padx=10, pady=(10, 6))
        self._detail_title = ctk.CTkLabel(header, text="", font=("Segoe UI", 16, "bold"))
        self._detail_title.pack(fill="x", padx=10, pady=(8, 4))
        self._detail_meta = ctk.CTkLabel(header, text="", font=("Segoe UI", 12))
        self._detail_meta.pack(fill="x", padx=10, pady=(0, 8))

        close_btn = ctk.CTkButton(
            header,
            text="Close",
            width=70,
            corner_radius=16,
            command=self._hide_item_detail,
        )
        close_btn.pack(padx=10, pady=(0, 10), anchor="e")

        body = ctk.CTkScrollableFrame(panel, fg_color="#171717", corner_radius=10)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._detail_body = body
        try:
            self._detail_body.bind("<MouseWheel>", self._on_detail_mousewheel, add=True)
        except Exception:
            pass
        # Description (HTML if available, else plain textbox)
        if HTMLLabel is not None:
            try:
                self._detail_html_label = HTMLLabel(
                    body,
                    html="",
                    background="#171717",
                    foreground="#F0F0F0",
                )
                self._detail_html_label.pack(fill="x", padx=10, pady=(10, 12))
            except Exception:
                self._detail_html_label = None
        if self._detail_html_label is None:
            self._detail_desc = ctk.CTkTextbox(body, height=160, wrap="word")
            self._detail_desc.pack(fill="x", padx=10, pady=(10, 12))
            self._detail_desc.configure(state="disabled")
        self._detail_panel = panel

    def _hide_item_detail(self):
        if self._detail_panel and self._detail_panel.winfo_exists():
            self._detail_panel.place_forget()

    def _show_item_detail(self, item: dict):
        self._ensure_detail_panel()
        if not self._detail_panel:
            return
        name = str(item.get("Name") or item.get("name") or "Unnamed")
        category = str(
            item.get("Category") or item.get("category") or item.get("Type") or item.get("type") or ""
        )
        self._detail_title.configure(text=name)
        self._detail_meta.configure(text=category)
        # Description: support RTF-JSON -> HTML if possible
        raw_desc = item.get("Description") or item.get("description") or item.get("Text") or item.get("text") or ""
        if isinstance(raw_desc, dict):
            html_text = rtf_to_html(raw_desc)
            if self._detail_html_label is not None:
                try:
                    self._detail_html_label.set_html(html_text)
                except Exception:
                    plain = format_multiline_text(raw_desc)
                    if self._detail_desc is None:
                        self._detail_desc = ctk.CTkTextbox(self._detail_body, height=160, wrap="word")
                        self._detail_desc.pack(fill="x", padx=10, pady=(10, 12))
                    self._detail_desc.configure(state="normal")
                    self._detail_desc.delete("1.0", "end")
                    self._detail_desc.insert("1.0", plain or "(no description)")
                    self._detail_desc.configure(state="disabled")
            else:
                plain = format_multiline_text(raw_desc)
                self._detail_desc.configure(state="normal")
                self._detail_desc.delete("1.0", "end")
                self._detail_desc.insert("1.0", plain or "(no description)")
                self._detail_desc.configure(state="disabled")
        else:
            text_val = str(raw_desc)
            if self._detail_html_label is not None:
                safe = text_val.replace("\n", "<br>")
                self._detail_html_label.set_html(f"<p>{safe}</p>")
            else:
                self._detail_desc.configure(state="normal")
                self._detail_desc.delete("1.0", "end")
                self._detail_desc.insert("1.0", text_val or "(no description)")
                self._detail_desc.configure(state="disabled")
        # Stats grid
        for child in list(self._detail_body.winfo_children()):
            # keep the textbox; it's already in children
            pass
        # Rebuild stats area below the textbox
        self._rebuild_stats(body=self._detail_body, item=item)
        # Ensure panel is visible (bottom dock)
        self._detail_panel.place(relx=0.0, rely=1.0, relwidth=1.0, anchor="sw", x=0, y=-10)

    def _rebuild_stats(self, body: ctk.CTkScrollableFrame, item: dict):
        # Remove any previous stat frames except the textbox
        kids = list(body.winfo_children())
        # First child is the description textbox; clear the rest
        for child in kids[1:]:
            child.destroy()
        # Optional longtext stats block
        stats_long = item.get("Stats") or item.get("stats") or item.get("Rules") or item.get("rules")
        if stats_long:
            stats_block = ctk.CTkFrame(body, fg_color="#1f1f1f", corner_radius=10)
            stats_block.pack(fill="x", padx=10, pady=(0, 10))
            ctk.CTkLabel(stats_block, text="Rules & Stats", font=("Segoe UI", 14, "bold")).pack(
                anchor="w", padx=10, pady=(8, 4)
            )
            # Render as HTML if available, else plain text
            if isinstance(stats_long, dict) and HTMLLabel is not None:
                try:
                    html_text = rtf_to_html(stats_long)
                    HTMLLabel(stats_block, html=html_text, background="#1f1f1f", foreground="#F0F0F0").pack(
                        fill="x", padx=10, pady=(0, 10)
                    )
                except Exception:
                    # fallback to plain
                    txt = ctk.CTkTextbox(stats_block, height=120, wrap="word")
                    txt.pack(fill="x", padx=10, pady=(0, 10))
                    txt.insert("1.0", format_multiline_text(stats_long))
                    txt.configure(state="disabled")
            else:
                txt = ctk.CTkTextbox(stats_block, height=120, wrap="word")
                txt.pack(fill="x", padx=10, pady=(0, 10))
                txt.insert("1.0", format_multiline_text(stats_long))
                txt.configure(state="disabled")
        section = ctk.CTkFrame(body, fg_color="#1f1f1f", corner_radius=10)
        section.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkLabel(section, text="Stats", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=10, pady=(8, 4)
        )

        grid = ctk.CTkFrame(section, fg_color="#1b1b1b", corner_radius=8)
        grid.pack(fill="x", padx=10, pady=(0, 10))
        # Choose common keys first, then include simple numeric fields
        common_keys = [
            "Damage", "Armor", "AC", "DR", "Range", "Weight", "Cost", "Price", "Value",
            "Rarity", "Durability", "Charges", "Quantity", "Quality",
        ]
        shown = set()
        row = 0
        for key in common_keys:
            val = item.get(key)
            if val is None:
                continue
            self._add_stat_row(grid, row, key, val)
            shown.add(key)
            row += 1
        # Add other small/simple fields
        exclude = {"Name", "name", "Category", "category", "Type", "type", "Description", "description", "Text", "text", "Portrait", "Image", "image"}
        for k, v in item.items():
            if k in shown or k in exclude:
                continue
            if isinstance(v, (int, float)) or (isinstance(v, str) and len(v) <= 40):
                self._add_stat_row(grid, row, k, v)
                row += 1

    @staticmethod
    def _add_stat_row(parent, row: int, key: str, value):
        k = ctk.CTkLabel(parent, text=str(key), font=("Segoe UI", 12, "bold"))
        v = ctk.CTkLabel(parent, text=str(value), font=("Segoe UI", 12))
        k.grid(row=row, column=0, sticky="w", padx=(10, 8), pady=4)
        v.grid(row=row, column=1, sticky="w", padx=(0, 10), pady=4)

