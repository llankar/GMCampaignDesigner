"""Shelf view implementation for object entities."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

import customtkinter as ctk
from PIL import Image


@dataclass
class ShelfSectionState:
    """Keep track of widgets and metadata for a shelf section."""

    category: str
    norm: str
    items: List[dict]
    container: Optional[ctk.CTkFrame] = None
    header_frame: Optional[ctk.CTkFrame] = None
    body_holder: Optional[ctk.CTkFrame] = None
    grid_frame: Optional[ctk.CTkFrame] = None
    pin_button: Optional[ctk.CTkButton] = None
    collapse_button: Optional[ctk.CTkButton] = None
    initialized: bool = False
    collapsed: bool = False
    pinned: bool = False
    loaded_count: int = 0
    crate_widgets: Dict[str, ctk.CTkFrame] = field(default_factory=dict)
    crate_order: List[str] = field(default_factory=list)
    crate_index: Dict[str, int] = field(default_factory=dict)
    spec_data_cache: Dict[str, List[Tuple[str, str, bool]]] = field(default_factory=dict)
    item_map: Dict[str, dict] = field(default_factory=dict)
    collapsed_strip: Optional[ctk.CTkFrame] = None
    collapsed_title: Optional[ctk.CTkLabel] = None
    collapsed_detail: Optional[ctk.CTkLabel] = None
    shelf_rows: Dict[int, ctk.CTkFrame] = field(default_factory=dict)
    display_cache: Dict[str, dict] = field(default_factory=dict)
    wrap_targets: Dict[str, List[ctk.CTkLabel]] = field(default_factory=dict)
    current_wrap: int = 0
    wrap_refresh_job: Optional[str] = None
    compact: bool = False
    column_count: int = 0
    configured_columns: int = 0
    uniform_id: str = ""
    section_overlay: Optional[ctk.CTkFrame] = None
    section_overlay_title: Optional[ctk.CTkLabel] = None
    section_overlay_count: Optional[ctk.CTkLabel] = None
    section_overlay_summary: Optional[ctk.CTkLabel] = None
    layout_freeze: bool = False
    pending_resize: bool = False
    active_spec_id: Optional[str] = None
    spec_overlay: Optional[ctk.CTkFrame] = None
    spec_overlay_body: Optional[ctk.CTkFrame] = None


class ObjectShelfView:
    """Encapsulates the supply crate shelf experience for object entities."""

    def __init__(self, host, allowed_categories: Sequence[str]):
        self.host = host
        self.allowed_categories = [c for c in allowed_categories]
        self.frame = ctk.CTkFrame(host, fg_color="transparent")
        self._background_image_source = None
        self._background_image = None
        self._background_label: Optional[ctk.CTkLabel] = None
        self._initialize_background()
        self.search_frame: Optional[ctk.CTkFrame] = None
        self.search_entry: Optional[ctk.CTkEntry] = None
        self.search_button: Optional[ctk.CTkButton] = None
        self._build_search_bar()
        self.summary_bar = ctk.CTkFrame(
            self.frame,
            fg_color="#242424",
            corner_radius=12,
            border_width=1,
            border_color="#404040",
        )
        summary_pady = (6, 0) if self.search_frame else (10, 0)
        self.summary_bar.pack(fill="x", padx=10, pady=summary_pady)
        self.summary_label = ctk.CTkLabel(
            self.summary_bar,
            text="",
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        )
        self.summary_label.pack(fill="x", padx=12, pady=6)

        self.container = ctk.CTkScrollableFrame(
            self.frame,
            fg_color="transparent",
            corner_radius=0,
        )
        self.container.pack(fill="both", expand=True, padx=10, pady=10)
        canvas = getattr(self.container, "_parent_canvas", None)
        if canvas is not None:
            canvas.bind("<Configure>", lambda _e: self._on_canvas_change())
            canvas.bind_all("<MouseWheel>", self._on_mousewheel, add=True)
        inner = getattr(self.container, "_scrollable_frame", None)
        if inner is not None:
            inner.bind("<Configure>", lambda _e: self._on_canvas_change())

        self.return_top = ctk.CTkButton(
            self.frame,
            text="Return to top",
            command=self.scroll_to_top,
            corner_radius=20,
            fg_color="#1F6AA5",
            hover_color="#125280",
            width=140,
        )
        self.return_top.place_forget()

        self.sections: List[ShelfSectionState] = []
        self.sections_by_norm: Dict[str, ShelfSectionState] = {}
        self._pinned_categories: set[str] = set()
        self._focused_base_id: Optional[str] = None
        self._visibility_job: Optional[str] = None
        self._header_colors = ("#3c2f23", "#23282f")
        self._fonts = {
            "name": ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            "name_compact": ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            "body": ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            "spec_header": ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            "spec_title": ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            "spec_body": ctk.CTkFont(family="Segoe UI", size=12),
        }
        self._last_known_selection: Set[str] = set()

    def _initialize_background(self):
        """Create and manage the background image for the shelf view."""

        image_path = Path(__file__).resolve().parents[2] / "assets" / "objects_shelves_background.jpg"
        if not image_path.exists():
            return
        try:
            with Image.open(image_path) as img:
                self._background_image_source = img.convert("RGBA")
        except Exception:
            self._background_image_source = None
            return

        self._background_image = ctk.CTkImage(
            light_image=self._background_image_source,
            dark_image=self._background_image_source,
        )
        self._background_label = ctk.CTkLabel(
            self.frame,
            text="",
            image=self._background_image,
        )
        self._background_label.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._background_label.lower()
        self.frame.bind("<Configure>", self._on_frame_resize, add=True)

    def _on_frame_resize(self, event):
        """Resize the background image to keep it filling the frame."""

        if not self._background_label or not self._background_image_source:
            return
        width = max(int(event.width), 1)
        height = max(int(event.height), 1)
        self._background_image = ctk.CTkImage(
            light_image=self._background_image_source,
            dark_image=self._background_image_source,
            size=(width, height),
        )
        self._background_label.configure(image=self._background_image)

    def _build_search_bar(self):
        """Create a shelf-level search input that leverages the host filter."""

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
        """Invoke the host filter when the search entry is submitted."""

        var = getattr(self.host, "search_var", None)
        if var is None or not hasattr(self.host, "filter_items"):
            return "break" if event is not None else None
        self.host.filter_items(var.get())
        return "break" if event is not None else None

    def _current_search_query(self) -> str:
        """Return the trimmed search query if one is active."""

        var = getattr(self.host, "search_var", None)
        if var is None:
            return ""
        try:
            value = var.get()
        except Exception:
            return ""
        return (value or "").strip()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def is_available(self) -> bool:
        return self.host.model_wrapper.entity_type == "objects"

    def is_visible(self) -> bool:
        return bool(self.frame.winfo_manager())

    def show(self, before_widget):
        self.frame.pack(
            fill="both", expand=True, padx=5, pady=5, before=before_widget
        )

    def hide(self):
        self.frame.pack_forget()
        self.stop_visibility_monitor()
        self.return_top.place_forget()

    def populate(self):
        if not self.is_available():
            return
        self._rebuild_sections()
        self.refresh_selection()
        self.update_summary()
        self._on_canvas_change()
        try:
            self.host.after_idle(self._check_visible_shelves)
        except Exception:
            self._check_visible_shelves()

    def refresh_selection(self):
        if not self.is_available():
            return
        selected = self._get_current_selection()
        for state in self.sections:
            for base_id, crate in state.crate_widgets.items():
                self._set_crate_selected(base_id, base_id in selected, crate)
        self._last_known_selection = set(selected)

    def _get_current_selection(self) -> Set[str]:
        selected = getattr(self.host, "selected_iids", set())
        try:
            return set(selected)
        except TypeError:
            return set(list(selected))

    def _sync_selection_delta(self, previous: Set[str], current: Set[str], highlight_target: Optional[str] = None):
        removed = previous - current
        added = current - previous
        for base_id in removed:
            self._set_crate_selected(base_id, False)
        for base_id in added:
            self._set_crate_selected(base_id, True, highlight=(base_id == highlight_target))
        self._last_known_selection = set(current)

    def update_summary(self):
        if not self.is_available():
            return
        pinned = len(self._pinned_categories)
        total = len(self.host.filtered_items)
        filters: List[str] = []
        query = self._current_search_query()
        if query:
            filters.append(f"Search: \"{query}\"")
        if self.host.filtered_items != self.host.items and not query:
            filters.append("Additional filters active")
        filter_text = " | ".join(filters) if filters else "No active filters"
        self.summary_label.configure(
            text=f"Pinned categories: {pinned}  |  Visible items: {total}  |  {filter_text}"
        )

    def start_visibility_monitor(self):
        self.stop_visibility_monitor()
        if not self.is_available():
            return
        self._visibility_job = self.host.after(200, self._monitor_visibility)

    def stop_visibility_monitor(self):
        if self._visibility_job is not None:
            try:
                self.host.after_cancel(self._visibility_job)
            except Exception:
                pass
            self._visibility_job = None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _rebuild_sections(self):
        if not self.container:
            return
        for state in self.sections:
            if state.wrap_refresh_job:
                try:
                    self.host.after_cancel(state.wrap_refresh_job)
                except Exception:
                    pass
                state.wrap_refresh_job = None
            self._hide_spec_overlay(state)
        for child in self.container.winfo_children():
            child.destroy()
        self.sections = []
        self.sections_by_norm = {}
        self._focused_base_id = None

        grouped = self._group_items_by_category()
        if not grouped:
            self._pinned_categories.clear()
            ctk.CTkLabel(
                self.container,
                text="No objects available for shelf view.",
                font=("Segoe UI", 14, "bold"),
                anchor="center",
            ).pack(fill="x", pady=40)
            return

        for data in grouped:
            state = ShelfSectionState(
                category=data["display"],
                norm=data["norm"],
                items=data["items"],
            )
            self._create_section_widgets(state)
            self.sections.append(state)
            self.sections_by_norm[state.norm] = state
        self._pinned_categories.intersection_update(self.sections_by_norm.keys())
        for norm in list(self._pinned_categories):
            state = self.sections_by_norm.get(norm)
            if state:
                state.pinned = True
                state.collapsed = False
                self._update_section_controls(state)
                self._ensure_section_loaded(state)
        self._expand_sections_for_search()

    def _expand_sections_for_search(self):
        """Ensure all sections are open and populated when a search is active."""

        if not self.sections:
            return
        if not self._current_search_query():
            return
        for state in self.sections:
            if state.collapsed:
                state.collapsed = False
            self._update_section_controls(state)
            self._ensure_section_loaded(state)

    def _group_items_by_category(self):
        groups: Dict[str, Dict[str, object]] = {}
        for item in self.host.filtered_items:
            norm, display = self._normalize_category(item.get("Category", ""))
            record = groups.setdefault(norm, {"display": display, "items": []})
            if not record["display"] and display:
                record["display"] = display
            record["items"].append(item)
        ordered = []
        allowed_norms = [c.lower() for c in self.allowed_categories]
        for allowed in allowed_norms:
            if allowed in groups:
                record = groups.pop(allowed)
                ordered.append(
                    {
                        "norm": allowed,
                        "display": record["display"] or allowed.title(),
                        "items": record["items"],
                    }
                )
        for norm, record in sorted(
            groups.items(), key=lambda kv: (kv[1]["display"] or kv[0]).lower()
        ):
            ordered.append(
                {
                    "norm": norm,
                    "display": record["display"] or norm.title(),
                    "items": record["items"],
                }
            )
        return ordered

    def _normalize_category(self, value):
        text = self.host.clean_value(value) or "Uncategorized"
        norm = text.strip().lower() or "uncategorized"
        display = text.strip() or "Uncategorized"
        return norm, display

    def _create_section_widgets(self, state: ShelfSectionState):
        container = ctk.CTkFrame(
            self.container,
            fg_color="#1a1a1a",
            corner_radius=14,
            border_width=1,
            border_color="#2d2d2d",
        )
        container.pack(fill="x", expand=True, pady=(0, 16))
        body_holder = ctk.CTkFrame(
            container,
            fg_color="#141414",
            corner_radius=12,
            border_width=1, 
            border_color="#262626",
        )
        body_holder.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        collapsed_strip = self._build_collapsed_strip(state, container, before_widget=body_holder)
        grid_frame = ctk.CTkFrame(body_holder, fg_color="#141414")
        grid_frame.pack(fill="both", expand=True, padx=12, pady=(12, 12))
        state.grid_frame = grid_frame
        state.compact = len(state.items) > 40
        state.column_count = max(1, self._determine_column_count(state))
        state.uniform_id = f"shelf_{id(state)}"
        self._apply_column_configuration(state)
        grid_frame.bind(
            "<Configure>",
            lambda event, st=state: self._on_grid_resize(st, event.width),
        )

        state.container = container
        state.body_holder = body_holder
        state.collapsed_strip = collapsed_strip
        state.header_frame = collapsed_strip
        state.grid_frame = grid_frame
        state.initialized = False
        state.collapsed = True
        state.loaded_count = 0
        state.crate_widgets = {}
        state.crate_order = []
        state.crate_index = {}
        state.spec_data_cache = {}
        state.item_map = {}
        state.shelf_rows = {}
        state.display_cache = {}
        state.wrap_targets = {}
        state.current_wrap = 0
        state.wrap_refresh_job = None
        state.layout_freeze = False
        state.pending_resize = False
        state.active_spec_id = None
        state.spec_overlay = None
        state.spec_overlay_body = None
        state.section_overlay_summary = None
        if state.body_holder:
            state.body_holder.pack_forget()
        self._update_section_controls(state)

    def _update_section_controls(self, state: ShelfSectionState):
        self._update_pin_button(state)
        self._update_collapse_button(state)

    def _format_category_display(self, state: ShelfSectionState) -> str:
        if state.category and state.category.strip():
            return state.category.strip()
        if state.norm and state.norm.strip():
            return state.norm.strip().replace("_", " ").title()
        return "Uncategorized"

    def _apply_column_configuration(self, state: ShelfSectionState):
        grid = state.grid_frame
        if not grid:
            return
        uniform = state.uniform_id or f"shelf_{id(state)}"
        state.uniform_id = uniform
        if state.configured_columns > state.column_count:
            for col in range(state.column_count, state.configured_columns):
                grid.grid_columnconfigure(col, weight=0)
        for col in range(state.column_count):
            grid.grid_columnconfigure(col, weight=1, uniform=uniform)
        state.configured_columns = state.column_count

    def _on_grid_resize(self, state: ShelfSectionState, width: int):
        if state.layout_freeze:
            state.pending_resize = True
            return
        desired = self._determine_column_count(state, width)
        if desired <= 0:
            return
        if desired == state.column_count:
            self._update_wrap_lengths(state)
            return
        state.column_count = desired
        self._apply_column_configuration(state)
        if state.initialized:
            self._reposition_section_widgets(state)
        else:
            self._update_wrap_lengths(state)

    def _freeze_layout(self, state: ShelfSectionState):
        if not state:
            return
        state.layout_freeze = True

    def _thaw_layout(self, state: ShelfSectionState):
        if not state:
            return
        if not state.layout_freeze:
            return
        state.layout_freeze = False
        if state.pending_resize:
            state.pending_resize = False
            width = state.grid_frame.winfo_width() if state.grid_frame else 0
            self._on_grid_resize(state, width)

    def _determine_column_count(self, state: ShelfSectionState, width: Optional[int] = None) -> int:
        return 7

    def _reposition_section_widgets(self, state: ShelfSectionState):
        columns = max(1, state.column_count or 1)
        active_rows: Set[int] = set()
        self._freeze_layout(state)
        try:
            for index, base_id in enumerate(state.crate_order):
                state.crate_index[base_id] = index
                crate = state.crate_widgets.get(base_id)
                if crate and crate.winfo_exists():
                    row_group = index // columns
                    row = row_group * 2
                    self._ensure_shelf_row(state, row_group, columns, row)
                    col = index % columns
                    crate.grid_configure(row=row, column=col, padx=8, pady=(10, 6), sticky="nsew")
                    active_rows.add(row_group)
            for row_group, strip in list(state.shelf_rows.items()):
                if row_group not in active_rows:
                    if strip and strip.winfo_exists():
                        strip.destroy()
                    state.shelf_rows.pop(row_group, None)
            self._update_wrap_lengths(state)
        finally:
            self._thaw_layout(state)

    def _update_pin_button(self, state: ShelfSectionState):
        if not state.pin_button:
            return
        if state.pinned:
            state.pin_button.configure(
                text="★",
                fg_color="#b68e54",
                hover_color="#d6a863",
                text_color="#1a1109",
            )
        else:
            state.pin_button.configure(
                text="☆",
                fg_color="#3b2515",
                hover_color="#6a4a2d",
                text_color="#f7f0e4",
            )

    def _update_collapse_button(self, state: ShelfSectionState):
        if not state.collapse_button:
            return
        symbol = ">" if state.collapsed else "v"
        state.collapse_button.configure(text=symbol)
        body = state.body_holder
        if state.collapsed:
            if body and body.winfo_exists():
                body.pack_forget()
        else:
            if body and body.winfo_exists():
                body.pack(fill="both", expand=True, padx=6, pady=(0, 6))
                if state.initialized:
                    self._ensure_section_loaded(state)
        self._update_collapsed_strip_text(state)

    def _toggle_section_collapse(self, state: ShelfSectionState):
        if state.pinned and not state.collapsed:
            return
        state.collapsed = not state.collapsed
        if state.pinned:
            state.collapsed = False
        if state.collapsed:
            self._collapse_section(state)
        else:
            self._ensure_section_loaded(state)
        self._update_collapse_button(state)
        if state.collapsed:
            self._dispose_specs(state)
        self.update_summary()

    def _collapse_section(self, state: ShelfSectionState):
        if not state.body_holder:
            return
        self._freeze_layout(state)
        if state.wrap_refresh_job:
            try:
                self.host.after_cancel(state.wrap_refresh_job)
            except Exception:
                pass
            state.wrap_refresh_job = None
        for crate in state.crate_widgets.values():
            if crate and crate.winfo_exists():
                crate.grid_remove()
        for strip in state.shelf_rows.values():
            if strip and strip.winfo_exists():
                strip.destroy()
        state.shelf_rows.clear()
        state.loaded_count = 0
        self._hide_spec_overlay(state)
        self._thaw_layout(state)

    def _toggle_section_pin(self, state: ShelfSectionState):
        state.pinned = not state.pinned
        if state.pinned:
            self._pinned_categories.add(state.norm)
            state.collapsed = False
        else:
            self._pinned_categories.discard(state.norm)
        self._update_pin_button(state)
        self._update_collapse_button(state)
        if not state.initialized:
            self._ensure_section_loaded(state)
        self.update_summary()

    def _ensure_section_loaded(self, state: ShelfSectionState):
        if state.collapsed:
            return
        if not state.initialized:
            state.initialized = True
            state.loaded_count = 0
            self._load_section_batch(state, batch_size=self._suggest_batch_size(state))
        else:
            self._maybe_load_more_crates(state, force=True)

    def _suggest_batch_size(self, state: ShelfSectionState) -> int:
        columns = state.column_count or self._determine_column_count(state)
        columns = max(1, columns)
        return max(24, min(96, columns * 6))

    def _prepare_item_display(self, state: ShelfSectionState, item: dict) -> dict:
        base_id = self.host._get_base_id(item)
        cached = state.display_cache.get(base_id)
        if cached:
            state.item_map[base_id] = item
            return cached
        clean_value = self.host.clean_value
        unique = getattr(self.host, "unique_field", "")
        raw_name = item.get(unique, "Unnamed") if unique else item.get("Name", "Unnamed")
        name = clean_value(raw_name) or "Unnamed"
        description = clean_value(item.get("Description", "--")) or "--"
        size_source = item.get("Size")
        secondary_label = "Size"
        if not size_source:
            stats_value = item.get("Stats")
            if stats_value not in (None, ""):
                size_source = stats_value
                secondary_label = "Stats"
        if not size_source:
            size_source = "--"
        secondary_value = clean_value(size_source) or "--"
        content_lines = [f"Desc: {description}"]
        content_lines.append(f"{secondary_label}: {secondary_value}")
        display = {
            "base_id": base_id,
            "name_text": name.upper(),
            "description": description,
            "secondary_label": secondary_label,
            "secondary_value": secondary_value,
            "content_text": "\n".join(content_lines),
        }
        state.display_cache[base_id] = display
        state.item_map[base_id] = item
        return display

    def _register_wrap_targets(
        self, state: ShelfSectionState, base_id: str, labels: Sequence[Optional[ctk.CTkLabel]]
    ):
        targets = [label for label in labels if label]
        if not targets:
            return
        state.wrap_targets[base_id] = targets

    def _prepare_spec_data(self, state: ShelfSectionState, item: dict) -> List[Tuple[str, str, bool]]:
        base_id = self.host._get_base_id(item)
        cached = state.spec_data_cache.get(base_id)
        if cached:
            return cached
        clean_value = self.host.clean_value
        result: List[Tuple[str, str, bool]] = []
        seen: Set[str] = set()
        default_order = ("Description", "Stats", "Secrets")
        for key in default_order:
            raw = item.get(key)
            text = clean_value(raw)
            if text in (None, ""):
                continue
            text = str(text)
            is_stats = key.lower() == "stats"
            if is_stats:
                text = self._normalize_stats_text(text)
            result.append((str(key), text, is_stats))
            seen.add(key.lower())
        unique_field = getattr(self.host, "unique_field", None)
        for key, raw in item.items():
            key_str = str(key)
            key_lower = key_str.lower()
            if key_lower in seen:
                continue
            if unique_field and key == unique_field:
                continue
            text = clean_value(raw)
            if text in (None, ""):
                continue
            text = str(text)
            is_stats = key_lower == "stats"
            if is_stats:
                text = self._normalize_stats_text(text)
            result.append((key_str, text, is_stats))
            seen.add(key_lower)
        state.spec_data_cache[base_id] = result
        return result

    @staticmethod
    def _normalize_stats_text(text: str) -> str:
        normalized = text.replace("\r", "\n").split("\n")
        lines = [segment.strip() for segment in normalized if segment.strip()]
        return " ".join(lines) if lines else text

    def _update_wrap_lengths(self, state: ShelfSectionState, *, immediate: bool = False):
        if not immediate:
            if state.wrap_refresh_job:
                return
            try:
                state.wrap_refresh_job = self.host.after_idle(
                    lambda st=state: self._update_wrap_lengths(st, immediate=True)
                )
                return
            except Exception:
                # Fallback to immediate update if scheduling fails
                pass
        state.wrap_refresh_job = None
        if not state.wrap_targets:
            return
        grid = state.grid_frame
        if not grid or not grid.winfo_exists():
            return
        width = grid.winfo_width()
        if width <= 0:
            width = grid.winfo_reqwidth()
        columns = max(1, state.column_count or 1)
        if width <= 0 or columns <= 0:
            return
        column_width = max(80, (width // columns) - 16)
        wrap_length = max(60, column_width - 20)
        if wrap_length == state.current_wrap:
            return
        state.current_wrap = wrap_length
        for labels in state.wrap_targets.values():
            for label in labels:
                if label and label.winfo_exists():
                    label.configure(wraplength=wrap_length)

    def _load_section_batch(self, state: ShelfSectionState, batch_size=24):
        if state.collapsed:
            return
        self._freeze_layout(state)
        try:
            start = state.loaded_count
            end = min(start + batch_size, len(state.items))
            columns = max(1, state.column_count or 4)
            for index in range(start, end):
                item = state.items[index]
                display = self._prepare_item_display(state, item)
                base_id = display["base_id"]
                crate = state.crate_widgets.get(base_id)
                if not crate or not crate.winfo_exists():
                    crate = self._create_crate_widget(state, item, display)
                    state.crate_widgets[base_id] = crate
                    state.crate_order.append(base_id)
                    state.crate_index[base_id] = len(state.crate_order) - 1
                else:
                    state.crate_index[base_id] = index
                row_group = index // columns
                row = row_group * 2
                col = index % columns
                self._ensure_shelf_row(state, row_group, columns, row)
                crate.grid(row=row, column=col, padx=8, pady=(10, 6), sticky="nsew")
            state.loaded_count = end
            self._update_section_overlay_text(state)
            if state.loaded_count < len(state.items):
                state.grid_frame.after(200, lambda st=state: self._maybe_load_more_crates(st))
            self._update_wrap_lengths(state)
        finally:
            self._thaw_layout(state)

    def _ensure_shelf_row(
        self,
        state: ShelfSectionState,
        row_group: int,
        columns: int,
        row: int,
    ) -> ctk.CTkFrame:
        grid = state.grid_frame
        if not grid:
            return None
        strip = state.shelf_rows.get(row_group)
        strip_pad = (6, 8) if row_group == 0 else (4, 8)
        if strip and strip.winfo_exists():
            strip.grid_configure(
                row=row,
                column=0,
                columnspan=columns,
                padx=6,
                pady=strip_pad,
                sticky="nsew",
            )
            strip.lower()
            return strip
        grid.grid_rowconfigure(row, weight=1, minsize=90)
        strip = ctk.CTkFrame(
            grid,
            fg_color="#120d08",
            corner_radius=16,
            border_width=0,
        )
        strip.grid(
            row=row,
            column=0,
            columnspan=columns,
            padx=6,
            pady=strip_pad,
            sticky="nsew",
        )
        strip.grid_propagate(False)
        strip.lower()
        plank = ctk.CTkFrame(
            strip,
            fg_color="#1d140d",
            corner_radius=14,
            border_width=1,
            border_color="#2c1f14",
        )
        plank.pack(fill="both", expand=True, padx=6, pady=(4, 6))
        plank.pack_propagate(False)
        top_edge = ctk.CTkFrame(plank, fg_color="#5f4330", height=2, corner_radius=4)
        top_edge.pack(fill="x", padx=12, pady=(4, 3))
        top_edge.pack_propagate(False)
        slat = ctk.CTkFrame(plank, fg_color="#281b12", height=2, corner_radius=6)
        slat.pack(fill="x", padx=10, pady=(0, 4))
        slat.pack_propagate(False)
        shadow = ctk.CTkFrame(plank, fg_color="#080707", height=2, corner_radius=4)
        shadow.pack(fill="x", padx=18, pady=(0, 4))
        shadow.pack_propagate(False)
        for relx in (0.04, 0.96):
            post = ctk.CTkFrame(plank, fg_color="#3b2a1d", corner_radius=6, width=12)
            post.place(relx=relx, rely=0.2, anchor="n", relheight=0.5)
            rivet = ctk.CTkFrame(plank, fg_color="#715236", width=10, height=2, corner_radius=5)
            rivet.place(relx=relx, rely=0.12, anchor="n")
        state.shelf_rows[row_group] = strip
        return strip

    def _build_collapsed_strip(
        self,
        state: ShelfSectionState,
        container: ctk.CTkFrame,
        before_widget: Optional[ctk.CTkFrame] = None,
    ):
        strip = ctk.CTkFrame(
            container,
            fg_color="#1a1a1a",
            corner_radius=0,
            border_width=0,
        )
        strip.configure(cursor="hand2")
        strip.bind("<Button-1>", lambda _e, st=state: self._toggle_section_collapse(st))
        strip.bind("<Return>", lambda _e, st=state: self._toggle_section_collapse(st))
        strip.bind("<space>", lambda _e, st=state: self._toggle_section_collapse(st))

        def _focus_strip(_event, frame=strip):
            try:
                frame.focus_set()
            except Exception:
                pass

        strip.bind("<Enter>", _focus_strip)
        strip.bind("<FocusIn>", _focus_strip)

        strip.grid_columnconfigure(1, weight=1)

        plank = ctk.CTkFrame(
            strip,
            fg_color="#3c291a",
            corner_radius=12,
            border_width=1,
            border_color="#25170e",
        )
        plank.grid(row=0, column=0, padx=(6, 0), pady=6, sticky="ns")
        plank.grid_propagate(False)

        surface = ctk.CTkFrame(
            plank,
            fg_color="#52341e",
            corner_radius=10,
            border_width=0,
            height=2
        )
        surface.pack(fill="both", expand=True, padx=3, pady=3)
        surface.pack_propagate(False)

        bottom_band = ctk.CTkFrame(surface, fg_color="#1a120c", height=6, corner_radius=3)
        bottom_band.place(relx=0.5, rely=0.92, anchor="s", relwidth=0.88)

        left_post = ctk.CTkFrame(surface, fg_color="#3b2515", corner_radius=5, width=18)
        left_post.place(relx=0.08, rely=0.5, anchor="center", relheight=0.72)

        right_post = ctk.CTkFrame(surface, fg_color="#3b2515", corner_radius=5, width=18)
        right_post.place(relx=0.92, rely=0.5, anchor="center", relheight=0.72)

        info_frame = ctk.CTkFrame(
            strip,
            fg_color="#1a1a1a",
            corner_radius=10,
            border_width=1,
            border_color="#262626",
            height=2
        )
        info_frame.grid(row=0, column=1, sticky="nsew", padx=12, pady=6)
        info_frame.grid_columnconfigure(0, weight=0)
        info_frame.grid_columnconfigure(1, weight=1)

        title = ctk.CTkLabel(
            info_frame,
            text="",
            font=("Segoe UI", 13, "bold"),
            anchor="w",
            justify="left",
            text_color="#f7f0e4",
        )
        title.grid(row=0, column=0, sticky="w", padx=(12, 6), pady=8)

        detail = ctk.CTkLabel(
            info_frame,
            text="",
            font=("Segoe UI", 11),
            anchor="w",
            justify="left",
            text_color="#e5d4bb",
        )
        detail.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=8)

        pin_button = ctk.CTkButton(
            info_frame,
            text="☆",
            width=28,
            height=2,
            corner_radius=14,
            fg_color="#3b2515",
            hover_color="#6a4a2d",
            text_color="#f7f0e4",
            font=("Segoe UI", 16),
            command=lambda st=state: self._toggle_section_pin(st),
        )
        pin_button.grid(row=0, column=2, padx=(6, 6), pady=8)

        collapse_button = ctk.CTkButton(
            info_frame,
            text=">",
            width=34,
            height=2,
            corner_radius=14,
            fg_color="#2d2d2d",
            hover_color="#1F6AA5",
            command=lambda st=state: self._toggle_section_collapse(st),
        )
        collapse_button.grid(row=0, column=3, padx=(0, 10), pady=8)

        interactive = [strip, plank, surface, left_post, right_post, bottom_band, info_frame, title, detail]
        for widget in interactive:
            widget.bind(
                "<Button-1>",
                lambda _e, st=state: self._toggle_section_collapse(st),
                add="+",
            )

        pack_kwargs = {"fill": "x", "padx": 6, "pady": (6, 0)}
        if before_widget and before_widget.winfo_exists() and before_widget.winfo_manager():
            strip.pack(before=before_widget, **pack_kwargs)
        else:
            strip.pack(**pack_kwargs)

        state.collapsed_strip = strip
        state.collapsed_title = title
        state.collapsed_detail = detail
        state.pin_button = pin_button
        state.collapse_button = collapse_button
        state.header_frame = strip
        self._update_collapsed_strip_text(state)
        return strip

    def _build_section_overlay(self, state: ShelfSectionState, parent: ctk.CTkFrame):
        overlay = ctk.CTkFrame(
            parent,
            fg_color="#2b1b11",
            corner_radius=12,
            border_width=1,
            border_color="#432d1d",
        )
        overlay.place(relx=0.5, y=12, anchor="n", relwidth=0.9)
        overlay.grid_columnconfigure(1, weight=1)
        overlay.lift()
        overlay.grid_rowconfigure(0, weight=1)
        overlay.grid_rowconfigure(1, weight=1)

        title = ctk.CTkLabel(
            overlay,
            text="",
            font=("Segoe UI", 15, "bold"),
            anchor="w",
            justify="left",
            text_color="#f7f0e4",
        )
        title.grid(row=0, column=0, sticky="w", padx=(16, 8), pady=10)

        count = ctk.CTkLabel(
            overlay,
            text="",
            font=("Segoe UI", 13),
            anchor="e",
            text_color="#eadbc2",
        )
        count.grid(row=0, column=1, sticky="e", padx=(8, 16), pady=10)

        summary = ctk.CTkLabel(
            overlay,
            text="",
            font=("Segoe UI", 12),
            anchor="w",
            justify="left",
            text_color="#d8c2a1",
        )
        summary.grid(row=1, column=0, columnspan=2, sticky="w", padx=(16, 16), pady=(0, 10))

        state.section_overlay_title = title
        state.section_overlay_count = count
        state.section_overlay = overlay
        state.section_overlay_summary = summary
        self._update_section_overlay_text(state)
        return overlay

    def _update_collapsed_strip_text(self, state: ShelfSectionState):
        if not state.collapsed_title or not state.collapsed_detail:
            return
        count = len(state.items)
        noun = "item" if count == 1 else "items"
        status_bits: List[str] = []
        if state.pinned:
            status_bits.append("Pinned")
        status_bits.append("Closed" if state.collapsed else "Open")
        action_text = "click to reopen" if state.collapsed else "click to collapse"
        category_text = self._format_category_display(state).upper()
        state.collapsed_title.configure(text=category_text)
        detail_parts = [f"{count} {noun}"]
        if status_bits:
            detail_parts.extend(status_bits)
        detail_parts.append(action_text)
        detail_text = " • ".join(detail_parts)
        state.collapsed_detail.configure(text=detail_text)
        self._update_section_overlay_text(state)

    def _update_section_overlay_text(self, state: ShelfSectionState):
        total = len(state.items)
        noun = "item" if total == 1 else "items"
        displayed = state.loaded_count if state.initialized and not state.collapsed else state.loaded_count
        displayed = min(displayed, total)
        category_display = self._format_category_display(state)
        if state.section_overlay_title:
            state.section_overlay_title.configure(text=category_display.upper())
        if state.section_overlay_count:
            if state.collapsed and not state.initialized:
                shown_text = f"{total} {noun}"
            elif displayed and displayed < total:
                shown_text = f"{displayed} / {total} {noun}"
            else:
                shown_text = f"{total} {noun}"
            state.section_overlay_count.configure(text=shown_text)
        if state.section_overlay_summary:
            if state.section_overlay_count:
                summary_count = state.section_overlay_count.cget("text") or ""
            else:
                summary_count = f"{total} {noun}"
            summary_bits = [category_display]
            if summary_count:
                summary_bits.append(summary_count)
            summary_text = " • ".join(summary_bits)
            state.section_overlay_summary.configure(text=summary_text)

    def _maybe_load_more_crates(self, state: ShelfSectionState, force=False):
        if state.collapsed or state.loaded_count >= len(state.items):
            return
        canvas = getattr(self.container, "_parent_canvas", None)
        if canvas is None:
            return
        if not force:
            visible_bottom = canvas.canvasy(canvas.winfo_height())
            if state.grid_frame.winfo_ismapped():
                bottom = state.grid_frame.winfo_y() + state.grid_frame.winfo_height()
                if bottom - visible_bottom > 400:
                    return
        self._load_section_batch(state, batch_size=self._suggest_batch_size(state))

    def _create_crate_widget(self, state: ShelfSectionState, item, display: dict):
        base_id = display["base_id"]
        crate = ctk.CTkFrame(
            state.grid_frame,
            fg_color="#1d1d1d",
            corner_radius=10,
            border_width=2,
            border_color="#2d2d2d",
        )
        crate.configure(cursor="hand2")
        compact = state.compact
        name_font = self._fonts["name_compact"] if compact else self._fonts["name"]
        name_label = ctk.CTkLabel(
            crate,
            text=display["name_text"],
            font=name_font,
            anchor="w",
        )
        name_label.pack(fill="x", padx=10, pady=(10, 4))
        interactive_children = [name_label]
        wrap_targets: List[ctk.CTkLabel] = []
        body_font = self._fonts["body"]
        wrap_length = state.current_wrap or 260
        content_text = display["content_text"]
        if compact:
            desc_label = ctk.CTkLabel(
                crate,
                text=content_text,
                font=body_font,
                anchor="w",
                justify="left",
                wraplength=wrap_length,
            )
            desc_label.pack(fill="x", padx=10, pady=(0, 8))
            interactive_children.append(desc_label)
            wrap_targets.append(desc_label)
        else:
            stats_frame = ctk.CTkFrame(
                crate,
                fg_color="#151515",
                corner_radius=8,
                border_width=1,
                border_color="#303030",
            )
            stats_frame.pack(fill="x", padx=10, pady=4)
            content_label = ctk.CTkLabel(
                stats_frame,
                text=content_text,
                font=body_font,
                anchor="w",
                justify="left",
                wraplength=wrap_length,
            )
            content_label.pack(fill="x", padx=8, pady=(6, 6))
            interactive_children.append(stats_frame)
            interactive_children.extend(stats_frame.winfo_children())
            wrap_targets.append(content_label)

        crate.bind(
            "<Button-1>",
            lambda e, st=state, bid=base_id: self._handle_crate_primary(e, st, bid),
        )
        crate.bind("<Double-Button-1>", lambda _e, it=item: self.host._edit_item(it))
        crate.bind("<Return>", lambda _e, st=state, bid=base_id: self._toggle_spec_sheet(st, bid))
        crate.bind("<space>", lambda _e, bid=base_id: self._toggle_crate_selection(bid))
        crate.bind("<FocusIn>", lambda _e, bid=base_id: self._focus_crate(bid))
        crate.bind(
            "<Key-Left>",
            lambda _e, st=state, bid=base_id: self._move_crate_focus(st, bid, -1),
        )
        crate.bind(
            "<Key-Right>",
            lambda _e, st=state, bid=base_id: self._move_crate_focus(st, bid, 1),
        )
        crate.bind(
            "<Key-Up>",
            lambda _e, st=state, bid=base_id: self._move_crate_focus(
                st, bid, -1 * max(1, st.column_count or 4)
            ),
        )
        crate.bind(
            "<Key-Down>",
            lambda _e, st=state, bid=base_id: self._move_crate_focus(
                st, bid, max(1, st.column_count or 4)
            ),
        )
        crate.bind("<Enter>", lambda _e: crate.focus_set())
        crate.pack_propagate(False)

        for child in interactive_children:
            child.bind(
                "<Button-1>",
                lambda e, st=state, bid=base_id: self._handle_crate_primary(e, st, bid),
                add="+",
            )
            child.bind(
                "<Double-Button-1>",
                lambda _e, it=item: self.host._edit_item(it),
                add="+",
            )
        self._register_wrap_targets(state, base_id, wrap_targets)
        return crate

    def _handle_crate_primary(self, event, state: ShelfSectionState, base_id):
        widget = event.widget
        if isinstance(widget, ctk.CTkButton):
            return
        self._on_crate_click(state, base_id)
        self._toggle_spec_sheet(state, base_id)

    def _on_crate_click(self, _state: ShelfSectionState, base_id):
        previous = self._get_current_selection()
        self.host.selected_iids = {base_id}
        self.host._apply_selection_to_tree()
        self.host._refresh_grid_selection()
        current = self._get_current_selection()
        self._sync_selection_delta(previous, current, highlight_target=base_id)
        self.host._update_bulk_controls()

    def _toggle_crate_selection(self, base_id):
        previous = self._get_current_selection()
        if base_id in self.host.selected_iids:
            self.host.selected_iids.remove(base_id)
        else:
            self.host.selected_iids.add(base_id)
        self.host._apply_selection_to_tree()
        self.host._refresh_grid_selection()
        current = self._get_current_selection()
        self._sync_selection_delta(previous, current, highlight_target=base_id)
        self.host._update_bulk_controls()

    def _focus_crate(self, base_id):
        previous = self._focused_base_id
        if previous and previous != base_id:
            self._set_crate_selected(previous, previous in self.host.selected_iids)
        self._focused_base_id = base_id
        self._set_crate_selected(base_id, base_id in self.host.selected_iids, highlight=True)

    def _move_crate_focus(self, state: ShelfSectionState, base_id, delta):
        index = state.crate_index.get(base_id)
        if index is None:
            if base_id not in state.crate_order:
                return
            index = state.crate_order.index(base_id)
            state.crate_index[base_id] = index
        target = max(0, min(index + delta, len(state.crate_order) - 1))
        target_id = state.crate_order[target]
        crate = state.crate_widgets.get(target_id)
        if crate and crate.winfo_exists():
            crate.focus_set()

    def _toggle_spec_sheet(self, state: ShelfSectionState, base_id):
        if state.active_spec_id == base_id:
            self._hide_spec_overlay(state)
            return
        item = state.item_map.get(base_id)
        if not item:
            item = next(
                (it for it in state.items if self.host._get_base_id(it) == base_id),
                None,
            )
            if item:
                state.item_map[base_id] = item
        if not item:
            return
        display = state.display_cache.get(base_id)
        if not display:
            display = self._prepare_item_display(state, item)
        spec_data = self._prepare_spec_data(state, item)
        crate = state.crate_widgets.get(base_id)
        if crate and crate.winfo_exists():
            try:
                self.host.after_idle(lambda cr=crate: self._scroll_widget_into_view(cr))
            except Exception:
                self._scroll_widget_into_view(crate)
        self._show_spec_overlay(state, base_id, display, spec_data)

    def _show_spec_overlay(
        self,
        state: ShelfSectionState,
        base_id: str,
        display: Dict[str, str],
        spec_data: Sequence[Tuple[str, str, bool]],
    ):
        self._hide_spec_overlay(state)
        overlay = ctk.CTkFrame(
            state.body_holder,
            fg_color="#0f0f0f",
            corner_radius=14,
            border_width=1,
            border_color="#2f2f2f",
        )
        overlay.place(relx=0.5, rely=0.02, anchor="n", relwidth=0.96, relheight=0.96)
        overlay.lift()
        title_bar = ctk.CTkFrame(
            overlay,
            fg_color="#171717",
            corner_radius=10,
            border_width=1,
            border_color="#2c2c2c",
        )
        title_bar.pack(fill="x", padx=12, pady=(12, 8))
        name_label = ctk.CTkLabel(
            title_bar,
            text=display.get("name_text", ""),
            font=self._fonts["name"],
            anchor="w",
        )
        name_label.pack(side="left", fill="x", expand=True, padx=(12, 8), pady=8)
        close_button = ctk.CTkButton(
            title_bar,
            text="Close",
            width=80,
            command=lambda st=state: self._hide_spec_overlay(st),
        )
        close_button.pack(side="right", padx=(8, 12), pady=8)

        label_text = display.get("secondary_label", "Details")
        value_text = display.get("secondary_value", "--")
        summary_text = f"{label_text}: {value_text}"
        summary_label = ctk.CTkLabel(
            overlay,
            text=summary_text,
            font=self._fonts["body"],
            justify="left",
            anchor="w",
        )
        summary_label.pack(fill="x", padx=20, pady=(0, 6))

        content = ctk.CTkScrollableFrame(
            overlay,
            fg_color="#101010",
            corner_radius=10,
        )
        content.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._build_spec_sheet_content(content, spec_data)

        overlay.bind("<Escape>", lambda _e, st=state: self._hide_spec_overlay(st))
        overlay.after(10, overlay.focus_set)
        state.spec_overlay = overlay
        state.spec_overlay_body = content
        state.active_spec_id = base_id

    def _build_spec_sheet_content(self, parent, spec_data: Sequence[Tuple[str, str, bool]]):
        for child in parent.winfo_children():
            child.destroy()
        wrap_labels: List[ctk.CTkLabel] = []
        for label_text, text, is_stats in spec_data:
            wrapper = ctk.CTkFrame(parent, fg_color="#161616", corner_radius=10)
            dense_spacing = bool(is_stats)
            pad_x = 10 if dense_spacing else 12
            pad_y = (3, 8) if dense_spacing else (5, 10)
            wrapper.pack(fill="x", padx=pad_x, pady=pad_y)
            title = ctk.CTkLabel(
                wrapper,
                text=label_text.upper(),
                font=self._fonts["spec_title"],
                anchor="w",
            )
            title_pad_x = 10 if dense_spacing else 12
            title_pad_y = (8, 3) if dense_spacing else (10, 4)
            title.pack(fill="x", padx=title_pad_x, pady=title_pad_y)
            body = ctk.CTkLabel(
                wrapper,
                text=text,
                font=self._fonts["spec_body"],
                justify="left",
                wraplength=780,
                anchor="w",
            )
            body_pad_x = 10 if dense_spacing else 12
            body_pad_y = (0, 8) if dense_spacing else (0, 10)
            body.pack(fill="x", padx=body_pad_x, pady=body_pad_y)
            wrap_labels.append(body)

        def _update_wrap(_event=None, labels=wrap_labels, widget=parent):
            width = max(280, widget.winfo_width() - 20)
            for label in labels:
                if label and label.winfo_exists():
                    label.configure(wraplength=width)

        parent.bind("<Configure>", _update_wrap, add="+")
        parent.after(50, _update_wrap)

    def _hide_spec_overlay(self, state: ShelfSectionState, destroy: bool = True):
        if not state:
            return
        overlay = state.spec_overlay
        if overlay and overlay.winfo_exists():
            overlay.place_forget()
            if destroy:
                overlay.destroy()
        state.spec_overlay = None
        state.spec_overlay_body = None
        state.active_spec_id = None

    def _dispose_specs(self, state: ShelfSectionState):
        self._hide_spec_overlay(state)

    def _scroll_widget_into_view(self, widget, padding: int = 20):
        if not widget or not widget.winfo_exists():
            return
        canvas = getattr(self.container, "_parent_canvas", None)
        inner = getattr(self.container, "_scrollable_frame", None)
        if canvas is None or inner is None:
            return
        try:
            widget.update_idletasks()
            inner.update_idletasks()
            canvas.update_idletasks()
        except Exception:
            return
        try:
            widget_top = widget.winfo_rooty() - inner.winfo_rooty()
        except Exception:
            return
        view_top = canvas.canvasy(0)
        view_height = canvas.winfo_height()
        if view_height <= 0:
            return
        view_bottom = view_top + view_height
        target_top = widget_top - padding
        target_bottom = widget_top + widget.winfo_height() + padding
        new_top = None
        if target_top < view_top:
            new_top = target_top
        elif target_bottom > view_bottom:
            new_top = target_bottom - view_height
        if new_top is None:
            return
        inner_height = max(1, inner.winfo_height())
        max_top = max(0, inner_height - view_height)
        new_top = min(max_top, max(0, new_top))
        canvas.yview_moveto(new_top / inner_height)

    def _set_crate_selected(self, base_id, selected=False, crate=None, highlight=False):
        target = crate
        if target is None:
            for state in self.sections:
                if base_id in state.crate_widgets:
                    candidate = state.crate_widgets.get(base_id)
                    if candidate and candidate.winfo_exists():
                        target = candidate
                        break
        if not target or not target.winfo_exists():
            return
        if selected or highlight:
            target.configure(border_color="#1F6AA5", border_width=3)
        else:
            target.configure(border_color="#2d2d2d", border_width=2)

    def _monitor_visibility(self):
        if self.host.view_mode != "shelf":
            self._visibility_job = None
            return
        self._check_visible_shelves()
        self._visibility_job = self.host.after(250, self._monitor_visibility)

    def _check_visible_shelves(self):
        if self.host.view_mode != "shelf":
            return
        canvas = getattr(self.container, "_parent_canvas", None)
        if canvas is None:
            return
        inner = getattr(self.container, "_scrollable_frame", None)
        inner_root_top = None
        if inner and inner.winfo_exists():
            inner_root_top = inner.winfo_rooty()
        visible_top = canvas.canvasy(0)
        visible_bottom = visible_top + canvas.winfo_height()
        threshold = 200
        for state in self.sections:
            container = state.container
            if (
                not container
                or not container.winfo_exists()
                or not container.winfo_ismapped()
            ):
                continue
            if inner_root_top is not None:
                container_root_top = container.winfo_rooty()
                top = container_root_top - inner_root_top
            else:
                top = container.winfo_y()
            bottom = top + container.winfo_height()
            body = state.body_holder
            if body and body.winfo_exists() and body.winfo_ismapped():
                body_offset = body.winfo_y()
                if inner_root_top is not None:
                    body_top = container_root_top + body_offset - inner_root_top
                else:
                    body_top = top + body_offset
                body_bottom = body_top + body.winfo_height()
                top = min(top, body_top)
                bottom = max(bottom, body_bottom)
            if bottom >= visible_top - threshold and top <= visible_bottom + threshold:
                self._ensure_section_loaded(state)
                self._maybe_load_more_crates(state)
            else:
                if state.active_spec_id and not state.pinned:
                    self._dispose_specs(state)
        self._update_return_button()

    def _on_canvas_change(self):
        self._update_return_button()
        canvas = getattr(self.container, "_parent_canvas", None)
        inner = getattr(self.container, "_scrollable_frame", None)
        if not canvas or not inner:
            return
        available = canvas.winfo_width()
        if available <= 0:
            return
        needs_update = inner.winfo_width() != available
        if needs_update:
            inner.configure(width=available)
        if needs_update:
            inner.update_idletasks()
            for state in self.sections:
                if state.grid_frame and state.grid_frame.winfo_exists():
                    state.grid_frame.update_idletasks()
                    padding = self._calculate_section_padding(state)
                    viewport_width = max(0, available - padding)
                    self._on_grid_resize(state, viewport_width)

    def _calculate_section_padding(self, state: ShelfSectionState) -> int:
        """Determine how much horizontal padding surrounds a section grid."""

        body_padding = self._horizontal_padding_for_widget(state.body_holder, 6)
        grid_padding = self._horizontal_padding_for_widget(state.grid_frame, 12)
        return body_padding + grid_padding

    @staticmethod
    def _horizontal_padding_for_widget(widget, default_per_side: int) -> int:
        """Return the total horizontal padding applied to a packed widget."""

        if not widget or not widget.winfo_exists():
            return default_per_side * 2
        try:
            info = widget.pack_info()
        except Exception:
            return default_per_side * 2
        raw = info.get("padx", default_per_side)
        padding = ObjectShelfView._coerce_padding_value(raw)
        if padding <= 0:
            padding = default_per_side * 2
        return padding

    @staticmethod
    def _coerce_padding_value(raw) -> int:
        """Normalize various tkinter padx representations into total pixels."""

        values: List[float] = []
        if isinstance(raw, (list, tuple)):
            items = raw
        elif isinstance(raw, str):
            cleaned = raw.replace("{", "").replace("}", "").split()
            items = cleaned if cleaned else [0]
        else:
            items = [raw]
        for item in items[:2]:
            try:
                values.append(float(item))
            except (TypeError, ValueError):
                continue
        if not values:
            return 0
        if len(values) == 1:
            return int(round(values[0] * 2))
        return int(round(values[0] + values[1]))

    def _on_mousewheel(self, event):
        if self.host.view_mode != "shelf":
            return
        canvas = getattr(self.container, "_parent_canvas", None)
        if canvas is None:
            return
        delta = -1 * (event.delta if event.delta else 0)
        canvas.yview_scroll(int(delta / 120), "units")
        self._check_visible_shelves()
        return "break"

    def scroll_to_top(self):
        canvas = getattr(self.container, "_parent_canvas", None)
        if canvas is not None:
            canvas.yview_moveto(0)
        self._update_return_button()

    def _update_return_button(self):
        if self.host.view_mode != "shelf":
            return
        canvas = getattr(self.container, "_parent_canvas", None)
        if canvas is None:
            self.return_top.place_forget()
            return
        y = canvas.canvasy(0)
        show = False
        if self.sections:
            if len(self.sections) > 2:
                third = self.sections[2]
                if third.header_frame:
                    third_y = third.header_frame.winfo_y()
                    show = y > third_y
        if show:
            height = self.frame.winfo_height() if self.frame else 0
            if height:
                self.return_top.place(relx=0.98, rely=0.92, anchor="se")
        else:
            self.return_top.place_forget()

