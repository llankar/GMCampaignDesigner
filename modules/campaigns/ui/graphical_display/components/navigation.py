"""Navigation helpers for campaign."""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Sequence

import customtkinter as ctk

from modules.scenarios.gm_screen.dashboard.styles.dashboard_theme import DASHBOARD_THEME
from ..data import CampaignGraphArc, CampaignGraphScenario


class _CanvasSelector(ctk.CTkFrame):
    def __init__(self, parent, *, height: int, bg_color: str):
        """Initialize the _CanvasSelector instance."""
        super().__init__(parent, fg_color="transparent")
        self._bg_color = bg_color
        self.canvas = tk.Canvas(
            self,
            height=height,
            bg=bg_color,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="x", expand=True)
        self.canvas.bind("<Configure>", self._render)
        self.after_idle(self._render)

    def _render(self, *_args, **_kwargs) -> None:
        """Render the operation."""
        raise NotImplementedError


class ArcSelectorStrip(_CanvasSelector):
    """Graphical selector that previews every arc while keeping only one arc expanded."""

    def __init__(
        self,
        parent,
        *,
        arcs: Sequence[CampaignGraphArc],
        selected_index: int,
        on_select: Callable[[int], None],
    ):
        """Initialize the ArcSelectorStrip instance."""
        self._arcs = list(arcs)
        self._selected_index = selected_index
        self._on_select = on_select
        super().__init__(parent, height=124, bg_color=DASHBOARD_THEME.panel_alt_bg)

    def _render(self, *_args, **_kwargs) -> None:
        """Render the operation."""
        canvas = getattr(self, "canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return

        canvas.delete("all")
        width = max(canvas.winfo_width(), 420)
        height = max(canvas.winfo_height(), 124)
        canvas.create_rectangle(0, 0, width, height, fill=self._bg_color, outline="")

        count = max(len(self._arcs), 1)
        margin = 20
        gap = 12
        card_width = max(min((width - (margin * 2) - (gap * (count - 1))) / count, 220), 118)
        total_width = card_width * count + gap * max(count - 1, 0)
        start_x = max((width - total_width) / 2, margin)

        for index, arc in enumerate(self._arcs):
            x1 = start_x + index * (card_width + gap)
            x2 = x1 + card_width
            y1 = 18
            y2 = height - 18
            selected = index == self._selected_index
            tag = f"arc:{index}"
            fill = DASHBOARD_THEME.button_fg if selected else DASHBOARD_THEME.panel_bg
            outline = DASHBOARD_THEME.accent_soft if selected else DASHBOARD_THEME.card_border
            title_color = "#f8fbff" if selected else DASHBOARD_THEME.text_primary
            meta_color = "#d6e9ff" if selected else DASHBOARD_THEME.text_secondary

            canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=2, tags=(tag,))
            canvas.create_text(
                x1 + 14,
                y1 + 18,
                text=f"Arc {index + 1}",
                fill="#8fb0dd",
                anchor="w",
                font=("Segoe UI", 10, "bold"),
                tags=(tag,),
            )
            canvas.create_text(
                x1 + 14,
                y1 + 42,
                text=_truncate(arc.name, 24),
                fill=title_color,
                anchor="w",
                width=max(card_width - 28, 40),
                font=("Segoe UI", 12, "bold"),
                tags=(tag,),
            )
            canvas.create_text(
                x1 + 14,
                y2 - 18,
                text=f"{arc.status} \u2022 {len(arc.scenarios)} scenarios",
                fill=meta_color,
                anchor="sw",
                font=("Segoe UI", 9, "bold"),
                tags=(tag,),
            )
            canvas.tag_bind(tag, "<Button-1>", lambda _e=None, idx=index: self._on_select(idx))
            canvas.tag_bind(tag, "<Enter>", lambda _e=None: canvas.configure(cursor="hand2"))
            canvas.tag_bind(tag, "<Leave>", lambda _e=None: canvas.configure(cursor=""))


class ScenarioSelectorStrip(ctk.CTkFrame):
    """Horizontal mission-card selector for scenarios inside the active arc."""

    def __init__(
        self,
        parent,
        *,
        scenarios: Sequence[CampaignGraphScenario],
        selected_index: int,
        on_select: Callable[[int], None],
    ):
        """Initialize the ScenarioSelectorStrip instance."""
        super().__init__(parent, fg_color=DASHBOARD_THEME.panel_alt_bg, corner_radius=18)
        self._scenarios = list(scenarios)
        self._selected_index = selected_index
        self._on_select = on_select
        self._scenario_signature: tuple[str, ...] = tuple(_scenario_signature(scenario) for scenario in self._scenarios)
        self._card_frames: list[ctk.CTkFrame] = []
        self._title_labels: list[ctk.CTkLabel] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(self, height=124, bg=DASHBOARD_THEME.panel_alt_bg, highlightthickness=0, bd=0)
        self.canvas.grid(row=0, column=0, sticky="ew")
        self.scrollbar = ctk.CTkScrollbar(self, orientation="horizontal", command=self.canvas.xview)
        self.scrollbar.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        self.canvas.configure(xscrollcommand=self.scrollbar.set)

        self.inner = ctk.CTkFrame(self.canvas, fg_color=DASHBOARD_THEME.panel_alt_bg)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._sync_scrollregion)
        self.canvas.bind("<Configure>", self._resize_window)
        self.after_idle(self._render)

    def set_selected_index(self, index: int) -> None:
        """Update the selected card without rebuilding the strip."""
        if not self._scenarios:
            self._selected_index = 0
            return

        new_index = max(0, min(index, len(self._scenarios) - 1))
        if new_index == self._selected_index and self._card_frames:
            return
        self._selected_index = new_index
        self._sync_selection_state()

    def set_scenarios(self, scenarios: Sequence[CampaignGraphScenario], selected_index: int) -> None:
        """Replace the scenario list when the arc changes."""
        scenario_list = list(scenarios)
        signature = tuple(_scenario_signature(scenario) for scenario in scenario_list)
        self._selected_index = max(0, min(selected_index, len(scenario_list) - 1)) if scenario_list else 0
        if signature == self._scenario_signature and len(scenario_list) == len(self._scenarios):
            self._scenarios = scenario_list
            self._sync_selection_state()
            return

        self._scenarios = scenario_list
        self._scenario_signature = signature
        self._render()

    def _render(self) -> None:
        """Render the operation."""
        canvas = getattr(self, "canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return

        self._card_frames = []
        self._title_labels = []
        for child in self.inner.winfo_children():
            child.destroy()

        many_scenarios = len(self._scenarios) >= 7
        card_width = 196 if many_scenarios else 224
        for index, scenario in enumerate(self._scenarios):
            selected = index == self._selected_index
            card = ctk.CTkFrame(
                self.inner,
                fg_color=DASHBOARD_THEME.button_fg if selected else DASHBOARD_THEME.panel_bg,
                corner_radius=14,
                border_width=2 if selected else 1,
                border_color=DASHBOARD_THEME.accent_soft if selected else DASHBOARD_THEME.card_border,
                width=card_width,
                height=104,
            )
            card.grid(row=0, column=index, sticky="nsw", padx=(0, 10), pady=8)
            card.grid_propagate(False)
            card.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                card,
                text=f"SCN {index + 1}",
                text_color="#8fb0dd",
                font=ctk.CTkFont(size=9, weight="bold"),
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))
            title_label = ctk.CTkLabel(
                card,
                text=_truncate_middle(scenario.title, 46 if not many_scenarios else 36),
                text_color="#f8fbff" if selected else DASHBOARD_THEME.text_primary,
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
                justify="left",
                wraplength=card_width - 24,
            )
            title_label.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))

            for clickable in (card, title_label):
                clickable.bind("<Button-1>", lambda _event, idx=index: self._on_select(idx))
                clickable.bind("<Enter>", lambda _event, target=card: target.configure(cursor="hand2"))
                clickable.bind("<Leave>", lambda _event, target=card: target.configure(cursor=""))

            self._card_frames.append(card)
            self._title_labels.append(title_label)

        self.after_idle(self._sync_scrollregion)
        self._sync_selection_state()

    def _sync_scrollregion(self, _event=None) -> None:
        """Synchronize scrollregion."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_selection_state(self) -> None:
        """Restyle existing cards to match the selected scenario."""
        for index, card in enumerate(self._card_frames):
            selected = index == self._selected_index
            card.configure(
                fg_color=DASHBOARD_THEME.button_fg if selected else DASHBOARD_THEME.panel_bg,
                border_width=2 if selected else 1,
                border_color=DASHBOARD_THEME.accent_soft if selected else DASHBOARD_THEME.card_border,
            )
            if index < len(self._title_labels):
                self._title_labels[index].configure(
                    text_color="#f8fbff" if selected else DASHBOARD_THEME.text_primary,
                )

    def _resize_window(self, event) -> None:
        """Internal helper for resize window."""
        self.canvas.itemconfigure(self.canvas_window, height=event.height)


def _truncate(value: str, limit: int) -> str:
    """Internal helper for truncate."""
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    ellipsis = "..."
    return text[: max(limit - len(ellipsis), 0)].rstrip() + ellipsis


def _truncate_middle(value: str, limit: int) -> str:
    """Internal helper for truncate middle."""
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    ellipsis = "..."
    if limit <= len(ellipsis):
        return ellipsis[:limit]
    remaining = limit - len(ellipsis)
    head = max(remaining // 2, 1)
    tail = max(remaining - head, 1)
    return f"{text[:head].rstrip()}{ellipsis}{text[-tail:].lstrip()}"


def _scenario_signature(scenario: CampaignGraphScenario) -> str:
    """Build a stable signature for selector rebuild detection."""
    return str(getattr(scenario, "title", "") or "").strip()
