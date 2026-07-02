"""Handouts page for the GM Table workspace."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk

import customtkinter as ctk
from PIL import Image

from modules.scenarios.gm_table.handouts.service import HandoutItem, collect_scenario_handouts
from modules.scenarios.gm_table.reveal import reveal_handout
from modules.ui.image_viewer import (
    DEFAULT_REVEAL_ANIMATION,
    REVEAL_ANIMATION_OPTIONS,
    normalize_reveal_animation,
)

_CARD_WIDTH = 148
_CARD_HEIGHT = 164
_CARD_GAP = 6
_THUMBNAIL_SIZE = (128, 88)
_PAGE_TEXT = "#E5EDF8"
_PAGE_MUTED = "#9AA7BD"
_PAGE_SURFACE = "#111927"
_PAGE_SURFACE_ALT = "#172235"
_PAGE_BORDER = "#2D3A52"
_PAGE_ACCENT = "#22D3EE"
_ANIMATION_LABELS = tuple(label for label, _value in REVEAL_ANIMATION_OPTIONS)
_ANIMATION_BY_LABEL = {label: value for label, value in REVEAL_ANIMATION_OPTIONS}
_LABEL_BY_ANIMATION = {value: label for label, value in REVEAL_ANIMATION_OPTIONS}


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
        on_reveal_complete=None,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        state = dict(initial_state or {})
        self._scenario_name = str(scenario_name or "").strip()
        self._scenario_item = scenario_item if isinstance(scenario_item, dict) else {}
        self._wrappers = wrappers
        self._map_wrapper = map_wrapper
        self._on_reveal_complete = on_reveal_complete

        self._query_var = tk.StringVar(value=str(state.get("query") or ""))
        self._status_var = tk.StringVar(value="")
        self._selected_id = str(state.get("selected_id") or "")
        self._animation_var = tk.StringVar(value=self._animation_label(state.get("animation")))

        self._handouts: list[HandoutItem] = []
        self._visible_cards: dict[str, ctk.CTkFrame] = {}
        self._thumbnail_cache: dict[str, tuple[float, ctk.CTkImage]] = {}
        self._placeholder_thumb = self._build_placeholder_thumb()
        self._column_count = 1
        self._card_menu = tk.Menu(self, tearoff=0)

        title = "Handouts"
        if self._scenario_name:
            title = f"Handouts · {self._scenario_name}"
        ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
            text_color=_PAGE_TEXT,
        ).grid(row=0, column=0, sticky="ew", pady=(0, 6))

        controls = ctk.CTkFrame(
            self,
            fg_color=_PAGE_SURFACE_ALT,
            corner_radius=14,
            border_width=1,
            border_color=_PAGE_BORDER,
        )
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        controls.grid_columnconfigure(0, weight=1)

        search = ctk.CTkEntry(
            controls,
            textvariable=self._query_var,
            placeholder_text="Filter handouts…",
            height=34,
            fg_color=_PAGE_SURFACE,
            border_color=_PAGE_BORDER,
            text_color=_PAGE_TEXT,
            placeholder_text_color=_PAGE_MUTED,
        )
        search.grid(row=0, column=0, sticky="ew", padx=(10, 8), pady=10)
        search.bind("<KeyRelease>", lambda _event: self._render_grid())

        ctk.CTkButton(
            controls,
            text="Refresh",
            width=88,
            height=34,
            fg_color="#1F6F86",
            hover_color="#2589A4",
            text_color="#F8FAFC",
            corner_radius=10,
            command=self.refresh,
        ).grid(row=0, column=1, pady=10)
        ctk.CTkOptionMenu(
            controls,
            values=list(_ANIMATION_LABELS),
            variable=self._animation_var,
            width=136,
            height=34,
            fg_color=_PAGE_SURFACE,
            button_color="#1F6F86",
            button_hover_color="#2589A4",
            text_color=_PAGE_TEXT,
            corner_radius=10,
        ).grid(row=0, column=2, sticky="e", padx=(8, 10), pady=10)

        ctk.CTkLabel(
            self,
            textvariable=self._status_var,
            anchor="w",
            justify="left",
            text_color="#FCA5A5",
            wraplength=460,
        ).grid(row=2, column=0, sticky="ew", pady=(0, 6))

        self._grid_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=_PAGE_SURFACE,
            corner_radius=14,
            border_width=1,
            border_color=_PAGE_BORDER,
        )
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
                text_color=_PAGE_MUTED,
            ).grid(row=0, column=0, sticky="ew", padx=12, pady=12)
            return

        for column in range(self._column_count):
            self._grid_frame.grid_columnconfigure(column, weight=1)

        for index, handout in enumerate(items):
            row = index // self._column_count
            column = index % self._column_count
            card = self._build_card(self._grid_frame, handout)
            card.grid(row=row, column=column, sticky="nsew", padx=6, pady=6)
            self._visible_cards[handout.id] = card

        self._highlight_selected()

    def _build_card(self, master, handout: HandoutItem) -> ctk.CTkFrame:
        """Create a compact clickable handout tile."""
        card = ctk.CTkFrame(
            master,
            corner_radius=12,
            width=_CARD_WIDTH,
            height=_CARD_HEIGHT,
            fg_color="#121826",
            border_width=1,
            border_color="#233047",
        )
        card.grid_propagate(False)
        card.grid_columnconfigure(0, weight=1)

        thumb, is_broken = self._get_thumbnail(handout.path)
        thumb_label = ctk.CTkLabel(card, text="", image=thumb, fg_color="#0B1220", corner_radius=10)
        thumb_label.grid(row=0, column=0, padx=7, pady=(7, 3), sticky="n")

        ctk.CTkLabel(
            card,
            text=handout.title,
            anchor="w",
            justify="left",
            wraplength=_CARD_WIDTH - 14,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=_PAGE_TEXT,
        ).grid(row=1, column=0, sticky="ew", padx=8)

        if handout.subtitle:
            ctk.CTkLabel(
                card,
                text=handout.subtitle,
                height=16,
                corner_radius=8,
                fg_color="#243249",
                text_color="#C9D3E6",
                font=ctk.CTkFont(size=10, weight="bold"),
            ).grid(row=2, column=0, sticky="w", padx=8, pady=(3, 1))

        warning_text = ""
        warning_color = "#FCA5A5"
        if is_broken:
            warning_text = "File unavailable"
        ctk.CTkLabel(
            card,
            text=warning_text,
            text_color=warning_color,
            anchor="w",
            font=ctk.CTkFont(size=10),
        ).grid(row=3, column=0, sticky="ew", padx=7, pady=(0, 4))

        ctk.CTkButton(
            card,
            text="Reveal",
            width=70,
            height=24,
            fg_color="#1F6F86",
            hover_color="#2589A4",
            text_color="#F8FAFC",
            corner_radius=8,
            command=lambda item=handout: self._open_handout(item),
        ).grid(row=4, column=0, sticky="w", padx=7, pady=(0, 7))

        self._bind_click_recursive(card, lambda _event, item=handout: self._open_handout(item))
        self._bind_context_menu_recursive(card, handout)
        return card

    def _bind_click_recursive(self, widget, callback) -> None:
        if isinstance(widget, ctk.CTkButton):
            return
        widget.bind("<Button-1>", callback)
        for child in widget.winfo_children():
            self._bind_click_recursive(child, callback)

    def _bind_context_menu_recursive(self, widget, handout: HandoutItem) -> None:
        widget.bind("<Button-3>", lambda event, item=handout: self._show_handout_menu(event, item), add="+")
        for child in widget.winfo_children():
            self._bind_context_menu_recursive(child, handout)

    def _show_handout_menu(self, event, handout: HandoutItem) -> str:
        """Open a handout context menu with player reveal actions."""
        menu = self._card_menu
        menu.delete(0, "end")
        menu.add_command(label="Reveal", command=lambda item=handout: self._open_handout(item))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

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
        placeholder = Image.new("RGB", _THUMBNAIL_SIZE, color="#172235")
        return ctk.CTkImage(light_image=placeholder, dark_image=placeholder, size=_THUMBNAIL_SIZE)

    @staticmethod
    def _animation_label(value) -> str:
        animation = normalize_reveal_animation(value)
        return _LABEL_BY_ANIMATION.get(animation, _ANIMATION_LABELS[0])

    def _selected_animation(self) -> str:
        variable = getattr(self, "_animation_var", None)
        if variable is None or not hasattr(variable, "get"):
            return DEFAULT_REVEAL_ANIMATION
        selected = variable.get()
        animation = _ANIMATION_BY_LABEL.get(selected, selected)
        return normalize_reveal_animation(animation)

    def _open_handout(self, handout: HandoutItem) -> None:
        resolved_path = str(Path(handout.path).resolve())
        if not Path(resolved_path).exists():
            self._status_var.set(f"⚠ Missing file: {Path(resolved_path).name}")
            self._render_grid()
            return

        self._selected_id = handout.id
        self._status_var.set("")
        self._highlight_selected()
        try:
            reveal_handout(handout, animation=self._selected_animation())
        finally:
            self._notify_reveal_complete()

    def _notify_reveal_complete(self) -> None:
        """Let the owner refresh table overlay geometry after a player reveal opens."""
        callback = getattr(self, "_on_reveal_complete", None)
        if not callable(callback):
            return
        try:
            callback()
        except Exception:
            # Reveals should remain resilient even if the parent table is closing.
            pass

    def reveal(self) -> None:
        """Reveal the selected handout from the workspace panel action."""
        handout = self._selected_handout()
        if handout is None:
            self._status_var.set("Select a handout to reveal first.")
            return
        self._open_handout(handout)

    def _selected_handout(self) -> HandoutItem | None:
        """Return the currently selected handout, if it still exists."""
        if not self._selected_id:
            return None
        return next(
            (handout for handout in self._handouts if handout.id == self._selected_id),
            None,
        )

    def _highlight_selected(self) -> None:
        for handout_id, card in self._visible_cards.items():
            selected = handout_id == self._selected_id
            card.configure(
                border_width=1 if selected else 0,
                border_color=_PAGE_ACCENT if selected else "#233047",
                fg_color="#182338" if selected else "#121826",
            )

    def get_state(self) -> dict:
        """Return serializable page state for workspace persistence."""
        return {
            "query": self._query_var.get().strip(),
            "selected_id": self._selected_id,
            "animation": self._selected_animation(),
        }
