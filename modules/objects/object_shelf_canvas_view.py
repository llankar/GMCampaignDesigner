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
from modules.helpers.theme_manager import (
    get_theme,
    register_theme_change_listener,
    THEME_MEDIEVAL,
    THEME_SF,
)
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
        # React to theme changes (swap background)
        try:
            self._unsub_theme = register_theme_change_listener(lambda _t: self._on_theme_changed())
        except Exception:
            self._unsub_theme = None

        # Shelf rows and drawing cache
        self._rows: List[_ShelfRow] = []
        self._panel_cache: Dict[Tuple[int, int], ImageTk.PhotoImage] = {}
        self._shelf_cache: Dict[Tuple[int, int], ImageTk.PhotoImage] = {}
        self._crate_cache: Dict[Tuple[int, int], ImageTk.PhotoImage] = {}
        self._item_by_tag: Dict[str, dict] = {}
        self._detail_panel: Optional[ctk.CTkFrame] = None
        self._detail_body: Optional[ctk.CTkScrollableFrame] = None
        self._detail_title: Optional[ctk.CTkLabel] = None
        self._detail_meta: Optional[ctk.CTkLabel] = None
        self._detail_desc: Optional[object] = None  # can be CTkLabel or CTkTextbox
        self._detail_html_label = None

        # New: fixed-height lower bar that never adapts to its content
        self._fixed_panel: Optional[ctk.CTkFrame] = None
        self._fixed_header: Optional[ctk.CTkFrame] = None
        self._fixed_body: Optional[ctk.CTkScrollableFrame] = None
        self._fixed_title: Optional[ctk.CTkLabel] = None
        self._fixed_meta: Optional[ctk.CTkLabel] = None
        self._fixed_desc: Optional[object] = None
        self._fixed_html_label = None
        self._fixed_bar_height: int = 160  # thin bar, constant height

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
        # Optional: stop listening when hidden
        # (kept active to reflect theme changes when shown again)

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
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        theme = get_theme()
        filename = "objects_shelves_background.jpg"
        if theme == THEME_MEDIEVAL:
            filename = "objects_shelves_background_medieval.png"
        elif theme == THEME_SF:
            filename = "objects_shelves_background_sf.png"
        image_path = assets_dir / filename
        if image_path.exists():
            try:
                with Image.open(image_path) as img:
                    self._bg_source = img.convert("RGBA")
            except Exception:
                self._bg_source = None
        else:
            # Fall back to default if themed image missing
            fallback = assets_dir / "objects_shelves_background.jpg"
            try:
                if fallback.exists():
                    with Image.open(fallback) as img:
                        self._bg_source = img.convert("RGBA")
            except Exception:
                self._bg_source = None
        # Force a redraw to show new background
        try:
            self._request_redraw()
        except Exception:
            pass

    def _on_theme_changed(self):
        # Invalidate cached background and reload per theme
        self._bg_source = None
        self._bg_photo = None
        self._bg_item = None
        self._load_background()

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
        # Scroll only the detail area's own scrollable canvas (fixed or legacy)
        candidates = []
        fb = getattr(self, "_fixed_body", None)
        if fb is not None and hasattr(fb, "winfo_exists") and fb.winfo_exists():
            candidates.append(fb)
        db = getattr(self, "_detail_body", None)
        if db is not None and hasattr(db, "winfo_exists") and db.winfo_exists():
            candidates.append(db)
        candidates.append(getattr(event, "widget", None))
        for c in candidates:
            if c is None:
                continue
            inner_canvas = getattr(c, "_parent_canvas", None)
            if inner_canvas is not None:
                delta = -1 * (event.delta if getattr(event, "delta", 0) else 0)
                try:
                    inner_canvas.yview_scroll(int(delta / 120), "units")
                except Exception:
                    pass
                return "break"
        return "break"

    def _update_detail_body_height(self, max_panel_height: int = 150, min_body_height: int = 40):
        """Adjust detail scroll area height based on content, capping total panel height.

        The overall detail panel should not exceed ``max_panel_height``. We compute
        available height for the scrollable body by subtracting the header height
        and known paddings, then clamp the body height to that. The scrollable
        frame itself is resized so it doesn't reserve unnecessary empty space.
        """
        body = getattr(self, "_detail_body", None)
        if not body or not body.winfo_exists():
            return

        inner = getattr(body, "_scrollable_frame", None)
        if inner and inner.winfo_exists():
            inner.update_idletasks()
            desired_content = inner.winfo_reqheight()
        else:
            body.update_idletasks()
            desired_content = body.winfo_reqheight()

        header = getattr(self, "_detail_header", None)
        header_h = 0
        header_pad = 10  # from header.pack(pady=(6,4))
        if header and header.winfo_exists():
            header.update_idletasks()
            header_h = max(header.winfo_height(), header.winfo_reqheight())

        body_pad_bottom = 4  # from body.pack(pady=(0,4))
        available_for_body = max_panel_height - (header_h + header_pad + body_pad_bottom)
        available_for_body = max(min_body_height, available_for_body)

        # When the body hasn't been laid out yet (width/height ~ 0), force-start
        # at the cap to avoid a visible grow-from-thin flicker.
        if body.winfo_width() <= 1 or body.winfo_height() <= 1:
            desired = int(available_for_body)
        else:
            desired = int(min(desired_content, available_for_body))

        # Apply the computed height directly to the scrollable frame so it
        # shrinks to match content instead of keeping the default tall request.
        try:
            body.configure(height=desired)
        except Exception:
            pass
        body._desired_height = desired

        panel = getattr(self, "_detail_panel", None)
        if panel and panel.winfo_exists():
            total = header_h + header_pad + desired + body_pad_bottom
            total = min(max_panel_height, max(total, header_h + header_pad + body_pad_bottom))
            try:
                panel.configure(height=total)
            except Exception:
                pass

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
        # Draw wood-like shelf plank (fast cached image) and label, then return
        try:
            shelf_img = self._get_shelf_image(panel_w, panel_h)
            self.canvas.create_image(
                x1 + 16, y1, image=shelf_img, anchor="nw", tags=("shelf", f"row:{row.category_key}")
            )
            label = f"{row.display.upper()} • {row.count} items"
            self.canvas.create_text(
                x1 + 16 + panel_w // 2,
                y1 + panel_h // 2,
                text=label,
                fill=("#FFFFFF" if get_theme() == THEME_MEDIEVAL else "#050300"),
                font=("Segoe UI", 14, "bold"),
                anchor="center",
                tags=("shelf", f"row:{row.category_key}"),
            )
            return
        except Exception:
            # Fallback to previous panel style if shelf image fails
            pass
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
            x1 + 16 + panel_w // 2,
            y1 + int(panel_h * 0.75),
            text=label,
            fill=("#FFFFFF" if get_theme() == THEME_MEDIEVAL else "#050300"),
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

    def _get_shelf_image(self, width: int, height: int) -> ImageTk.PhotoImage:
        """Cached wood-like plank image for shelf rows.

        Uses a simple warm gradient with subtle plank lines for a shelf look.
        """
        key = (width, height)
        cached = self._shelf_cache.get(key)
        if cached is not None:
            return cached
        width = max(1, int(width))
        height = max(1, int(height))
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Base rounded plank
        base_fill = (96, 64, 32, 230)  # warm brown
        border = (35, 22, 10, 240)
        self._rounded_rect(draw, (0, 0, width, height), 14, fill=base_fill, outline=border, width=2)
        # Light gradient from top to bottom for depth
        for i in range(height):
            alpha = int(28 * (1 - i / max(1, height)))
            draw.line([(2, i + 1), (width - 3, i + 1)], fill=(255, 235, 205, alpha))
        # Plank seams
        seam_color = (60, 40, 20, 70)
        plank_h = max(16, height // 2)
        y = 3 + plank_h
        while y < height - 3:
            draw.line([(6, y), (width - 6, y)], fill=seam_color, width=1)
            y += plank_h
        # Screw heads at corners
        screw = (30, 25, 18, 180)
        for sx, sy in [(10, 10), (width - 12, 10), (10, height - 12), (width - 12, height - 12)]:
            draw.ellipse((sx, sy, sx + 4, sy + 4), fill=screw)
        photo = ImageTk.PhotoImage(img)
        self._shelf_cache[key] = photo
        return photo

    def _get_crate_image(self, width: int, height: int) -> ImageTk.PhotoImage:
        """Cached crate tile image for object items.

        Designed to be used as a single canvas image per item for speed.
        """
        key = (width, height)
        cached = self._crate_cache.get(key)
        if cached is not None:
            return cached
        width = max(8, int(width))
        height = max(8, int(height))
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Outer box
        base = (58, 39, 22, 235)
        border = (20, 12, 6, 240)
        self._rounded_rect(draw, (0, 0, width, height), 6, fill=base, outline=border, width=2)
        # Inner slats
        slat_color = (85, 58, 34, 220)
        pad = 4
        slat_h = max(6, height // 3)
        y = pad
        for _ in range(3):
            if y + slat_h > height - pad:
                break
            draw.rectangle((pad, y, width - pad, y + slat_h), fill=slat_color)
            y += slat_h + 2
        # Cross braces
        brace = (40, 26, 14, 140)
        draw.line([(pad + 1, pad + 1), (width - pad - 1, height - pad - 1)], fill=brace, width=2)
        draw.line([(pad + 1, height - pad - 1), (width - pad - 1, pad + 1)], fill=brace, width=2)
        photo = ImageTk.PhotoImage(img)
        self._crate_cache[key] = photo
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
        tile_h = 36
        min_tile_w = 180
        cols = max(1, inner_width // min_tile_w)
        rows = (len(row.items) + cols - 1) // cols
        return padding * 2 + rows * tile_h + (rows - 1) * 6

    def _draw_row_items(self, x: int, y: int, right: int, row: _ShelfRow):
        inner_width = right - x
        padding = 16
        tile_h = 36
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
            crate_img = self._get_crate_image(col_w, tile_h)
            self.canvas.create_image(
                ix, iy,
                image=crate_img,
                anchor="nw",
                tags=items_tag + (tag,),
            )
            name = str(item.get("Name") or item.get("name") or "Unnamed")
            self.canvas.create_text(
                ix + col_w // 2,
                iy + tile_h // 2,
                text=name,
                fill="#fff7e6",
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
                        # Use the new fixed-height lower bar with its own scrollbar
                        self._show_item_detail_fixed(it)
                        return "break"
        return None

    # ----- Fixed lower bar (new implementation) -------------------------
    def _ensure_fixed_detail_bar(self):
        if self._fixed_panel and self._fixed_panel.winfo_exists():
            return
        panel = ctk.CTkFrame(
            self.frame,
            fg_color="#171717",
            corner_radius=12,
            border_width=1,
            border_color="#2a2a2a",
            height=self._fixed_bar_height,
        )
        # Prevent geometry propagation so children don't change the panel size
        try:
            panel.pack_propagate(False)
            panel.grid_propagate(False)
        except Exception:
            pass
        # Dock to bottom with a constant height; never adapts to content
        panel.configure(height=self._fixed_bar_height)
        panel.place(relx=0.0, rely=1.0, relwidth=1.0, anchor="sw", x=0, y=-8)
        # Header
        header = ctk.CTkFrame(panel, fg_color="#1f1f1f", corner_radius=10)
        header.pack(fill="x", padx=10, pady=(6, 4))
        title = ctk.CTkLabel(header, text="", font=("Segoe UI", 14, "bold"))
        title.pack(side="left", padx=10, pady=(4, 2))
        meta = ctk.CTkLabel(header, text="", font=("Segoe UI", 12))
        meta.pack(side="left", padx=(8, 10), pady=(4, 2))
        close_btn = ctk.CTkButton(header, text="Close", width=70, corner_radius=16, command=self._hide_fixed_detail_bar)
        close_btn.pack(side="right", padx=10, pady=(4, 2))
        # Scrollable content area: fills remaining height inside fixed panel
        body = ctk.CTkScrollableFrame(panel, fg_color="#171717", corner_radius=10)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        try:
            body.bind("<MouseWheel>", self._on_detail_mousewheel, add=True)
        except Exception:
            pass
        self._fixed_panel = panel
        self._fixed_header = header
        self._fixed_body = body
        self._fixed_title = title
        self._fixed_meta = meta

    def _hide_fixed_detail_bar(self):
        if self._fixed_panel and self._fixed_panel.winfo_exists():
            self._fixed_panel.place_forget()

    def _show_item_detail_fixed(self, item: dict):
        # Build bar if needed and keep constant size; also hide legacy panel
        self._ensure_fixed_detail_bar()
        try:
            self._hide_item_detail()
        except Exception:
            pass
        if not self._fixed_panel or not self._fixed_body:
            return
        # Title & meta
        name = str(item.get("Name") or item.get("name") or "Unnamed")
        category = str(
            item.get("Category") or item.get("category") or item.get("Type") or item.get("type") or ""
        )
        if self._fixed_title:
            self._fixed_title.configure(text=name)
        if self._fixed_meta:
            self._fixed_meta.configure(text=category)

        # Clear previous content except header
        for child in list(self._fixed_body.winfo_children()):
            child.destroy()

        # Description: prefer HTML if available
        raw_desc = item.get("Description") or item.get("description") or item.get("Text") or item.get("text") or ""
        self._fixed_html_label = None
        self._fixed_desc = None
        if isinstance(raw_desc, dict) and HTMLLabel is not None:
            try:
                html_text = rtf_to_html(raw_desc)
                hl = HTMLLabel(self._fixed_body, html=html_text, background="#171717", foreground="#F0F0F0")
                hl.pack(fill="x", padx=10, pady=(4, 8))
                self._fixed_html_label = hl
            except Exception:
                pass
        if self._fixed_html_label is None:
            # Plain label that wraps to container width
            lbl = ctk.CTkLabel(
                self._fixed_body,
                text=(format_multiline_text(raw_desc) if isinstance(raw_desc, dict) else str(raw_desc)),
                anchor="w",
                justify="left",
                font=("Segoe UI", 12),
            )
            lbl.pack(fill="x", padx=10, pady=(4, 8))
            def _wrap(_e=None, l=lbl, p=self._fixed_body):
                try:
                    l.configure(wraplength=max(100, p.winfo_width() - 40))
                except Exception:
                    pass
            try:
                self._fixed_body.bind("<Configure>", _wrap, add=True)
                self._fixed_body.after_idle(_wrap)
            except Exception:
                _wrap()
            self._fixed_desc = lbl

        # Optional stats (reusing existing renderer but targeting fixed body)
        try:
            self._rebuild_stats(body=self._fixed_body, item=item)
        except Exception:
            pass

        # Finally, ensure bar is visible at bottom with constant height
        try:
            self._fixed_panel.configure(height=self._fixed_bar_height)
        except Exception:
            pass
        self._fixed_panel.place(relx=0.0, rely=1.0, relwidth=1.0, anchor="sw", x=0, y=-8)
        try:
            self._fixed_panel.lift()
        except Exception:
            pass

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
        )
        # Dock to the bottom; full width, fixed height
        panel.place(relx=0.0, rely=1.0, relwidth=1.0, anchor="sw", x=0, y=-10)
        header = ctk.CTkFrame(panel, fg_color="#1f1f1f", corner_radius=10)
        header.pack(fill="x", padx=10, pady=(6, 4))
        self._detail_header = header
        self._detail_title = ctk.CTkLabel(header, text="", font=("Segoe UI", 16, "bold"))
        self._detail_title.pack(fill="x", padx=10, pady=(4, 0))
        self._detail_meta = ctk.CTkLabel(header, text="", font=("Segoe UI", 12))
        self._detail_meta.pack(fill="x", padx=10, pady=(0, 4))

        close_btn = ctk.CTkButton(
            header,
            text="Close",
            width=70,
            corner_radius=16,
            command=self._hide_item_detail,
        )
        # Keep the header compact: place the close button at the top-right
        # so it shares the same row as the title instead of creating extra height.
        try:
            close_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=6)
        except Exception:
            # Fallback to packing on the right if placing is unavailable
            close_btn.pack(padx=10, pady=(0, 6), anchor="e")

        # Detail body auto-sizes to content; we cap height dynamically later
        body = ctk.CTkScrollableFrame(
            panel,
            fg_color="#171717",
            corner_radius=10,
        )
        body.pack(fill="x", expand=False, padx=10, pady=(0, 4))
        self._detail_body = body
        try:
            self._detail_body.bind("<MouseWheel>", self._on_detail_mousewheel, add=True)
        except Exception:
            pass
        try:
            # Recompute body height whenever its size may change
            body.bind("<Configure>", lambda _e: self._update_detail_body_height(), add=True)
        except Exception:
            pass
        # Description (HTML if available, else wrapped label that autosizes)
        if HTMLLabel is not None:
            try:
                self._detail_html_label = HTMLLabel(
                    body,
                    html="",
                    background="#171717",
                    foreground="#F0F0F0",
                )
                self._detail_html_label.pack(fill="x", padx=10, pady=(6, 8))
            except Exception:
                self._detail_html_label = None
        if self._detail_html_label is None:
            # Use a label that wraps to container width and grows with content
            self._detail_desc = ctk.CTkLabel(
                body,
                text="",
                anchor="w",
                justify="left",
                font=("Segoe UI", 12),
            )
            self._detail_desc.pack(fill="x", padx=10, pady=(6, 8))
            # Bind wraplength to container width for natural height
            def _resize_wrap(_e=None, lbl=self._detail_desc, parent=body):
                try:
                    wrap = max(100, parent.winfo_width() - 40)
                    lbl.configure(wraplength=wrap)
                except Exception:
                    pass
            try:
                body.bind("<Configure>", _resize_wrap, add=True)
                body.after_idle(_resize_wrap)
            except Exception:
                _resize_wrap()
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
                        self._detail_desc = ctk.CTkLabel(
                            self._detail_body,
                            text="",
                            anchor="w",
                            justify="left",
                            font=("Segoe UI", 12),
                        )
                        self._detail_desc.pack(fill="x", padx=10, pady=(6, 8))
                    self._detail_desc.configure(text=(plain or "(no description)"))
            else:
                plain = format_multiline_text(raw_desc)
                if isinstance(self._detail_desc, ctk.CTkLabel):
                    self._detail_desc.configure(text=(plain or "(no description)"))
                else:
                    # Fallback if a textbox exists from previous content
                    try:
                        self._detail_desc.configure(state="normal")
                        self._detail_desc.delete("1.0", "end")
                        self._detail_desc.insert("1.0", plain or "(no description)")
                        self._detail_desc.configure(state="disabled")
                    except Exception:
                        pass
        else:
            text_val = str(raw_desc)
            if self._detail_html_label is not None:
                safe = text_val.replace("\n", "<br>")
                self._detail_html_label.set_html(f"<p>{safe}</p>")
            else:
                if isinstance(self._detail_desc, ctk.CTkLabel):
                    self._detail_desc.configure(text=(text_val or "(no description)"))
                else:
                    try:
                        self._detail_desc.configure(state="normal")
                        self._detail_desc.delete("1.0", "end")
                        self._detail_desc.insert("1.0", text_val or "(no description)")
                        self._detail_desc.configure(state="disabled")
                    except Exception:
                        pass
        # Stats grid
        for child in list(self._detail_body.winfo_children()):
            # keep the textbox; it's already in children
            pass
        # Rebuild stats area below the textbox
        self._rebuild_stats(body=self._detail_body, item=item)
        # Ensure panel is visible (bottom dock) and height fits content
        self._detail_panel.place(relx=0.0, rely=1.0, relwidth=1.0, anchor="sw", x=0, y=-2)
        self._update_detail_body_height()

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
            stats_block.pack(fill="x", padx=10, pady=(0, 6))
            ctk.CTkLabel(stats_block, text="Rules & Stats", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=10, pady=(6, 4))
            # Render as HTML if available, else plain text
            if isinstance(stats_long, dict) and HTMLLabel is not None:
                try:
                    html_text = rtf_to_html(stats_long)
                    HTMLLabel(stats_block, html=html_text, background="#1f1f1f", foreground="#F0F0F0").pack(
                        fill="x", padx=10, pady=(0, 10)
                    )
                except Exception:
                    # fallback to plain label that wraps and autosizes
                    lbl = ctk.CTkLabel(
                        stats_block,
                        text=format_multiline_text(stats_long),
                        anchor="w",
                        justify="left",
                        font=("Segoe UI", 12),
                    )
                    lbl.pack(fill="x", padx=10, pady=(0, 6))
                    def _wrap(_e=None, l=lbl, p=stats_block):
                        try:
                            l.configure(wraplength=max(100, p.winfo_width() - 40))
                        except Exception:
                            pass
                    try:
                        stats_block.bind("<Configure>", _wrap, add=True)
                        stats_block.after_idle(_wrap)
                    except Exception:
                        _wrap()
            else:
                lbl = ctk.CTkLabel(
                    stats_block,
                    text=format_multiline_text(stats_long),
                    anchor="w",
                    justify="left",
                    font=("Segoe UI", 12),
                )
                lbl.pack(fill="x", padx=10, pady=(0, 6))
                def _wrap2(_e=None, l=lbl, p=stats_block):
                    try:
                        l.configure(wraplength=max(100, p.winfo_width() - 40))
                    except Exception:
                        pass
                try:
                    stats_block.bind("<Configure>", _wrap2, add=True)
                    stats_block.after_idle(_wrap2)
                except Exception:
                    _wrap2()
        # Build compact stats rows first; only render section if there is content
        common_keys = [
            "Damage", "Armor", "AC", "DR", "Range", "Weight", "Cost", "Price", "Value",
            "Rarity", "Durability", "Charges", "Quantity", "Quality",
        ]
        stats_rows = []
        shown = set()
        for key in common_keys:
            val = item.get(key)
            if val is None:
                continue
            stats_rows.append((key, val))
            shown.add(key)
        # Add other small/simple fields
        exclude = {"Name", "name", "Category", "category", "Type", "type", "Description", "description", "Text", "text", "Portrait", "Image", "image"}
        for k, v in item.items():
            if k in shown or k in exclude:
                continue
            if isinstance(v, (int, float)) or (isinstance(v, str) and len(v) <= 40):
                stats_rows.append((k, v))
        if stats_rows:
            section = ctk.CTkFrame(body, fg_color="#1f1f1f", corner_radius=10)
            section.pack(fill="x", padx=10, pady=(0, 6))
            ctk.CTkLabel(section, text="Stats", font=("Segoe UI", 14, "bold")).pack(
                anchor="w", padx=10, pady=(8, 4)
            )
            grid = ctk.CTkFrame(section, fg_color="#1b1b1b", corner_radius=8)
            grid.pack(fill="x", padx=10, pady=(0, 6))
            for row, (k, v) in enumerate(stats_rows):
                self._add_stat_row(grid, row, k, v)

    @staticmethod
    def _add_stat_row(parent, row: int, key: str, value):
        k = ctk.CTkLabel(parent, text=str(key), font=("Segoe UI", 12, "bold"))
        v = ctk.CTkLabel(parent, text=str(value), font=("Segoe UI", 12))
        k.grid(row=row, column=0, sticky="w", padx=(10, 8), pady=4)
        v.grid(row=row, column=1, sticky="w", padx=(0, 10), pady=4)
