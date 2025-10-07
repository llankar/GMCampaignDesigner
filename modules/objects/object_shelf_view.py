"""Shelf view implementation for object entities."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import customtkinter as ctk


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
    count_label: Optional[ctk.CTkLabel] = None
    pin_button: Optional[ctk.CTkButton] = None
    collapse_button: Optional[ctk.CTkButton] = None
    initialized: bool = False
    collapsed: bool = False
    pinned: bool = False
    loaded_count: int = 0
    crate_widgets: Dict[str, ctk.CTkFrame] = field(default_factory=dict)
    crate_order: List[str] = field(default_factory=list)
    open_specs: Dict[str, ctk.CTkFrame] = field(default_factory=dict)


class ObjectShelfView:
    """Encapsulates the supply crate shelf experience for object entities."""

    def __init__(self, host, allowed_categories: Sequence[str]):
        self.host = host
        self.allowed_categories = [c for c in allowed_categories]
        self.frame = ctk.CTkFrame(host, fg_color="#181818")
        self.summary_bar = ctk.CTkFrame(
            self.frame,
            fg_color="#242424",
            corner_radius=12,
            border_width=1,
            border_color="#404040",
        )
        self.summary_bar.pack(fill="x", padx=10, pady=(10, 0))
        self.summary_label = ctk.CTkLabel(
            self.summary_bar,
            text="",
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        )
        self.summary_label.pack(fill="x", padx=12, pady=6)

        self.container = ctk.CTkScrollableFrame(
            self.frame,
            fg_color="#151515",
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
        selected = getattr(self.host, "selected_iids", set())
        for state in self.sections:
            for base_id, crate in state.crate_widgets.items():
                self._set_crate_selected(base_id, base_id in selected, crate)

    def update_summary(self):
        if not self.is_available():
            return
        pinned = len(self._pinned_categories)
        total = len(self.host.filtered_items)
        filters: List[str] = []
        query = ""
        if hasattr(self.host, "search_var") and self.host.search_var is not None:
            query = self.host.search_var.get().strip()
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
            for spec in list(state.open_specs.values()):
                if spec and spec.winfo_exists():
                    spec.destroy()
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
        header = ctk.CTkFrame(
            container,
            fg_color=self._header_colors,
            corner_radius=14,
            border_width=0,
        )
        header.pack(fill="x")
        header.configure(cursor="hand2")
        header.bind("<Button-1>", lambda _e, st=state: self._toggle_section_collapse(st))

        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", padx=12, pady=6)
        title = ctk.CTkLabel(
            title_frame,
            text=state.category.upper(),
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        )
        title.pack(side="left")
        count_label = ctk.CTkLabel(
            title_frame,
            text="0",
            font=("Segoe UI", 12, "bold"),
        )
        count_label.pack(side="left", padx=8)
        pin_button = ctk.CTkButton(
            header,
            text="Pin",
            corner_radius=18,
            width=80,
            command=lambda st=state: self._toggle_section_pin(st),
            fg_color="#2d2d2d",
            hover_color="#1F6AA5",
        )
        pin_button.pack(side="left", padx=6, pady=4)
        collapse_button = ctk.CTkButton(
            header,
            text="Collapse",
            corner_radius=18,
            width=100,
            command=lambda st=state: self._toggle_section_collapse(st),
            fg_color="#2d2d2d",
            hover_color="#1F6AA5",
        )
        collapse_button.pack(side="left", padx=(0, 10), pady=4)

        body_holder = ctk.CTkFrame(
            container,
            fg_color="#141414",
            corner_radius=12,
            border_width=1,
            border_color="#262626",
        )
        body_holder.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        grid_frame = ctk.CTkFrame(body_holder, fg_color="#141414")
        grid_frame.pack(fill="both", expand=True, padx=12, pady=12)
        for col in range(4):
            grid_frame.grid_columnconfigure(col, weight=1, uniform="shelf")

        state.container = container
        state.header_frame = header
        state.count_label = count_label
        state.pin_button = pin_button
        state.collapse_button = collapse_button
        state.body_holder = body_holder
        state.grid_frame = grid_frame
        state.initialized = False
        state.collapsed = True
        state.loaded_count = 0
        state.crate_widgets = {}
        state.crate_order = []
        state.open_specs = {}
        if state.body_holder:
            state.body_holder.pack_forget()
        self._update_section_controls(state)

    def _update_section_controls(self, state: ShelfSectionState):
        if state.count_label:
            state.count_label.configure(text=str(len(state.items)))
        self._update_pin_button(state)
        self._update_collapse_button(state)

    def _update_pin_button(self, state: ShelfSectionState):
        if not state.pin_button:
            return
        if state.pinned:
            state.pin_button.configure(text="Pinned", fg_color="#1F6AA5")
        else:
            state.pin_button.configure(text="Pin", fg_color="#2d2d2d")

    def _update_collapse_button(self, state: ShelfSectionState):
        if not state.collapse_button:
            return
        label = "Show Items" if state.collapsed else "Hide Items"
        state.collapse_button.configure(text=label)
        if state.body_holder:
            if state.collapsed:
                state.body_holder.pack_forget()
            else:
                state.body_holder.pack(fill="both", expand=True, padx=6, pady=(0, 6))
                if state.initialized:
                    self._ensure_section_loaded(state)

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
        for crate in state.crate_widgets.values():
            if crate and crate.winfo_exists():
                crate.grid_remove()
        state.loaded_count = 0

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
            self._load_section_batch(state)
        else:
            self._maybe_load_more_crates(state, force=True)

    def _load_section_batch(self, state: ShelfSectionState, batch_size=24):
        if state.collapsed:
            return
        start = state.loaded_count
        end = min(start + batch_size, len(state.items))
        columns = 4
        for index in range(start, end):
            item = state.items[index]
            base_id = self.host._get_base_id(item)
            crate = state.crate_widgets.get(base_id)
            if not crate or not crate.winfo_exists():
                crate = self._create_crate_widget(state, item)
                state.crate_widgets[base_id] = crate
                state.crate_order.append(base_id)
            row_group = index // columns
            row = row_group * 2
            col = index % columns
            crate.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
        state.loaded_count = end
        if state.loaded_count < len(state.items):
            state.grid_frame.after(150, lambda st=state: self._maybe_load_more_crates(st))

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
        self._load_section_batch(state)

    def _create_crate_widget(self, state: ShelfSectionState, item):
        base_id = self.host._get_base_id(item)
        crate = ctk.CTkFrame(
            state.grid_frame,
            fg_color="#1d1d1d",
            corner_radius=10,
            border_width=2,
            border_color="#2d2d2d",
        )
        crate.configure(cursor="hand2")
        name = self.host.clean_value(item.get(self.host.unique_field, "Unnamed")) or "Unnamed"
        name_label = ctk.CTkLabel(
            crate,
            text=name.upper(),
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        )
        name_label.pack(fill="x", padx=10, pady=(10, 4))
        weight = self.host.clean_value(item.get("Weight", "--")) or "--"
        cost = self.host.clean_value(item.get("Cost", "--")) or "--"
        stats_frame = ctk.CTkFrame(
            crate,
            fg_color="#151515",
            corner_radius=8,
            border_width=1,
            border_color="#303030",
        )
        stats_frame.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(
            stats_frame,
            text=f"Weight: {weight}",
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        ).pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(
            stats_frame,
            text=f"Cost: {cost}",
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        ).pack(fill="x", padx=8, pady=(0, 6))

        actions = ctk.CTkFrame(crate, fg_color="#1d1d1d")
        actions.pack(fill="x", padx=10, pady=(4, 10))
        open_btn = ctk.CTkButton(
            actions,
            text="Open",
            width=70,
            command=lambda it=item: self.host._edit_item(it),
            fg_color="#1F6AA5",
            hover_color="#125280",
        )
        open_btn.pack(side="left", padx=(0, 6))
        delete_btn = ctk.CTkButton(
            actions,
            text="Delete",
            width=70,
            command=lambda bid=base_id: self.host.delete_item(bid),
            fg_color="#8B1A1A",
            hover_color="#a83232",
        )
        delete_btn.pack(side="left", padx=(6, 0))

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
            lambda _e, st=state, bid=base_id: self._move_crate_focus(st, bid, -4),
        )
        crate.bind(
            "<Key-Down>",
            lambda _e, st=state, bid=base_id: self._move_crate_focus(st, bid, 4),
        )
        crate.bind("<Enter>", lambda _e: crate.focus_set())
        crate.pack_propagate(False)

        for child in (name_label, stats_frame):
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
        return crate

    def _handle_crate_primary(self, event, state: ShelfSectionState, base_id):
        widget = event.widget
        if isinstance(widget, ctk.CTkButton):
            return
        self._on_crate_click(state, base_id)
        self._toggle_spec_sheet(state, base_id)

    def _on_crate_click(self, _state: ShelfSectionState, base_id):
        self.host.selected_iids = {base_id}
        self.host._apply_selection_to_tree()
        self.host._refresh_grid_selection()
        self.refresh_selection()
        self.host._update_bulk_controls()

    def _toggle_crate_selection(self, base_id):
        if base_id in self.host.selected_iids:
            self.host.selected_iids.remove(base_id)
        else:
            self.host.selected_iids.add(base_id)
        self.host._apply_selection_to_tree()
        self.host._refresh_grid_selection()
        self.refresh_selection()
        self.host._update_bulk_controls()

    def _focus_crate(self, base_id):
        previous = self._focused_base_id
        if previous and previous != base_id:
            self._set_crate_selected(previous, previous in self.host.selected_iids)
        self._focused_base_id = base_id
        self._set_crate_selected(base_id, base_id in self.host.selected_iids, highlight=True)

    def _move_crate_focus(self, state: ShelfSectionState, base_id, delta):
        if base_id not in state.crate_order:
            return
        index = state.crate_order.index(base_id)
        target = max(0, min(index + delta, len(state.crate_order) - 1))
        target_id = state.crate_order[target]
        crate = state.crate_widgets.get(target_id)
        if crate and crate.winfo_exists():
            crate.focus_set()

    def _toggle_spec_sheet(self, state: ShelfSectionState, base_id):
        if base_id in state.open_specs:
            frame = state.open_specs.pop(base_id)
            if frame and frame.winfo_exists():
                frame.destroy()
            return
        item = next(
            (it for it in state.items if self.host._get_base_id(it) == base_id),
            None,
        )
        if not item:
            return
        frame = ctk.CTkFrame(state.grid_frame, fg_color="#101010", corner_radius=10)
        self._build_spec_sheet_content(frame, item)
        if base_id not in state.crate_order:
            state.crate_order.append(base_id)
        index = state.crate_order.index(base_id)
        columns = 4
        row_group = index // columns
        spec_row = row_group * 2 + 1
        frame.grid(row=spec_row, column=0, columnspan=columns, sticky="nsew", padx=8, pady=(0, 12))
        state.open_specs[base_id] = frame

    def _build_spec_sheet_content(self, frame, item):
        frame.pack_propagate(False)
        header = ctk.CTkLabel(
            frame,
            text="SPEC SHEET",
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        )
        header.pack(fill="x", padx=12, pady=(12, 4))
        fields = ["Description", "Stats", "Secrets"]
        seen = set()
        for key in fields:
            value = item.get(key)
            if value:
                self._add_spec_field(frame, key, value)
                seen.add(key)
        for key, value in item.items():
            if key in seen or key == self.host.unique_field:
                continue
            if value in (None, ""):
                continue
            self._add_spec_field(frame, key, value)

    def _add_spec_field(self, parent, label, value):
        wrapper = ctk.CTkFrame(parent, fg_color="#141414", corner_radius=8)
        wrapper.pack(fill="x", padx=10, pady=(4, 10))
        title = ctk.CTkLabel(
            wrapper,
            text=str(label).upper(),
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        )
        title.pack(fill="x", padx=10, pady=(6, 2))
        text = self.host.clean_value(value)
        body = ctk.CTkLabel(
            wrapper,
            text=text,
            font=("Segoe UI", 10),
            justify="left",
            wraplength=720,
            anchor="w",
        )
        body.pack(fill="x", padx=10, pady=(0, 8))

    def _dispose_specs(self, state: ShelfSectionState):
        for base_id, frame in list(state.open_specs.items()):
            if frame and frame.winfo_exists():
                frame.destroy()
        state.open_specs.clear()

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
        visible_top = canvas.canvasy(0)
        visible_bottom = visible_top + canvas.winfo_height()
        threshold = 200
        for state in self.sections:
            if not state.header_frame or not state.header_frame.winfo_ismapped():
                continue
            top = state.header_frame.winfo_y()
            bottom = top + state.header_frame.winfo_height()
            if bottom >= visible_top - threshold and top <= visible_bottom + threshold:
                self._ensure_section_loaded(state)
                self._maybe_load_more_crates(state)
            else:
                if not state.pinned:
                    self._dispose_specs(state)
        self._update_return_button()

    def _on_canvas_change(self):
        self._update_return_button()

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

