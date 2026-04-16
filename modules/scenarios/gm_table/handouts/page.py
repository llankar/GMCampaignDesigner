"""Handouts page for the GM Table workspace."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk

import customtkinter as ctk
from PIL import Image

from modules.scenarios.gm_table.handouts.service import HandoutItem, collect_scenario_handouts
from modules.ui.image_viewer import show_portrait

_CARD_WIDTH = 148
_CARD_HEIGHT = 164
_CARD_GAP = 6
_THUMBNAIL_SIZE = (128, 88)


class GMTableHandoutsPage(ctk.CTkFrame):
    """Display scenario-linked handouts in a compact responsive grid."""

    def __init__(
        self,
        master,
        *,
        scenario_name: str,
        scenario_item: dict,
        wrappers: dict[str, object],
        map_wrapper: object,
        initial_state: dict | None = None,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        state = dict(initial_state or {})
        self._scenario_name = str(scenario_name or "").strip()
        self._scenario_item = scenario_item if isinstance(scenario_item, dict) else {}
        self._wrappers = wrappers
        self._map_wrapper = map_wrapper

        self._query_var = tk.StringVar(value=str(state.get("query") or ""))
        self._status_var = tk.StringVar(value="")
        self._selected_id = str(state.get("selected_id") or "")

        self._handouts: list[HandoutItem] = []
        self._visible_cards: dict[str, ctk.CTkFrame] = {}
        self._thumbnail_cache: dict[str, tuple[float, ctk.CTkImage]] = {}
        self._placeholder_thumb = self._build_placeholder_thumb()
        self._column_count = 1

        title = "Handouts"
        if self._scenario_name:
            title = f"Handouts · {self._scenario_name}"
        ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 4))

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        controls.grid_columnconfigure(0, weight=1)

        search = ctk.CTkEntry(
            controls,
            textvariable=self._query_var,
            placeholder_text="Filter handouts…",
            height=30,
        )
        search.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        search.bind("<KeyRelease>", lambda _event: self._render_grid())

        ctk.CTkButton(controls, text="Refresh", width=88, height=30, command=self.refresh).grid(row=0, column=1)

        ctk.CTkLabel(
            self,
            textvariable=self._status_var,
            anchor="w",
            justify="left",
            text_color="#F59E0B",
            wraplength=460,
        ).grid(row=2, column=0, sticky="ew", pady=(0, 4))

        self._grid_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._grid_frame.grid(row=3, column=0, sticky="nsew")
        self.bind("<Configure>", self._on_resize)

        self.refresh()

    def refresh(self) -> None:
        """Reload scenario-linked handouts when links or assets changed."""
        self._status_var.set("")
        self._handouts = collect_scenario_handouts(
            self._scenario_item,
            self._wrappers,
            self._map_wrapper,
        )
        self._render_grid()

    def _on_resize(self, _event=None) -> None:
        width = max(self.winfo_width(), self._grid_frame.winfo_width())
        columns = self._compute_columns(width)
        if columns != self._column_count:
            self._column_count = columns
            self._render_grid()

    @staticmethod
    def _compute_columns(width: int) -> int:
        usable = max(width - 12, _CARD_WIDTH)
        return max(1, usable // (_CARD_WIDTH + _CARD_GAP))

    def _render_grid(self) -> None:
        for child in self._grid_frame.winfo_children():
            child.destroy()
        self._visible_cards.clear()

        query = self._query_var.get().strip().casefold()
        items = [
            handout
            for handout in self._handouts
            if not query
            or query in handout.title.casefold()
            or query in handout.entity_type.casefold()
            or query in Path(handout.path).name.casefold()
        ]

        if not items:
            ctk.CTkLabel(
                self._grid_frame,
                text="No scenario handouts found.",
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=4, pady=4)
            return

        for column in range(self._column_count):
            self._grid_frame.grid_columnconfigure(column, weight=1)

        for index, handout in enumerate(items):
            row = index // self._column_count
            column = index % self._column_count
            card = self._build_card(self._grid_frame, handout)
            card.grid(row=row, column=column, sticky="nsew", padx=3, pady=3)
            self._visible_cards[handout.id] = card

        self._highlight_selected()

    def _build_card(self, master, handout: HandoutItem) -> ctk.CTkFrame:
        """Create a compact clickable handout tile."""
        card = ctk.CTkFrame(master, corner_radius=10, width=_CARD_WIDTH, height=_CARD_HEIGHT)
        card.grid_propagate(False)
        card.grid_columnconfigure(0, weight=1)

        thumb, is_broken = self._get_thumbnail(handout.path)
        thumb_label = ctk.CTkLabel(card, text="", image=thumb)
        thumb_label.grid(row=0, column=0, padx=5, pady=(5, 2), sticky="n")

        ctk.CTkLabel(
            card,
            text=handout.title,
            anchor="w",
            justify="left",
            wraplength=_CARD_WIDTH - 14,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=1, column=0, sticky="ew", padx=7)

        if handout.subtitle:
            ctk.CTkLabel(
                card,
                text=handout.subtitle,
                height=16,
                corner_radius=8,
                fg_color="#2F3A4E",
                text_color="#C9D3E6",
                font=ctk.CTkFont(size=10, weight="bold"),
            ).grid(row=2, column=0, sticky="w", padx=7, pady=(2, 1))

        warning_text = ""
        warning_color = "#EF4444"
        if is_broken:
            warning_text = "File unavailable"
        ctk.CTkLabel(
            card,
            text=warning_text,
            text_color=warning_color,
            anchor="w",
            font=ctk.CTkFont(size=10),
        ).grid(row=3, column=0, sticky="ew", padx=7, pady=(0, 4))

        self._bind_click_recursive(card, lambda _event, item=handout: self._open_handout(item))
        return card

    def _bind_click_recursive(self, widget, callback) -> None:
        widget.bind("<Button-1>", callback)
        for child in widget.winfo_children():
            self._bind_click_recursive(child, callback)

    def _get_thumbnail(self, resolved_path: str) -> tuple[ctk.CTkImage, bool]:
        candidate = Path(resolved_path)
        try:
            modified_at = candidate.stat().st_mtime
        except OSError:
            return self._placeholder_thumb, True

        cache_key = str(candidate.resolve())
        cached = self._thumbnail_cache.get(cache_key)
        if cached and cached[0] == modified_at:
            return cached[1], False

        try:
            with Image.open(candidate) as img:
                render = img.convert("RGB")
                render.thumbnail(_THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            ctk_image = ctk.CTkImage(light_image=render, dark_image=render, size=render.size)
        except Exception:
            return self._placeholder_thumb, True

        self._thumbnail_cache[cache_key] = (modified_at, ctk_image)
        return ctk_image, False

    @staticmethod
    def _build_placeholder_thumb() -> ctk.CTkImage:
        placeholder = Image.new("RGB", _THUMBNAIL_SIZE, color="#293241")
        return ctk.CTkImage(light_image=placeholder, dark_image=placeholder, size=_THUMBNAIL_SIZE)

    def _open_handout(self, handout: HandoutItem) -> None:
        resolved_path = str(Path(handout.path).resolve())
        if not Path(resolved_path).exists():
            self._status_var.set(f"⚠ Missing file: {Path(resolved_path).name}")
            self._render_grid()
            return

        self._selected_id = handout.id
        self._status_var.set("")
        self._highlight_selected()
        show_portrait(resolved_path, title=handout.title)

    def _highlight_selected(self) -> None:
        for handout_id, card in self._visible_cards.items():
            selected = handout_id == self._selected_id
            card.configure(
                border_width=1 if selected else 0,
                border_color="#D9A441" if selected else "#344054",
                fg_color="#1F2937" if selected else "#121826",
            )

    def get_state(self) -> dict:
        """Return serializable page state for workspace persistence."""
        return {
            "query": self._query_var.get().strip(),
            "selected_id": self._selected_id,
        }
