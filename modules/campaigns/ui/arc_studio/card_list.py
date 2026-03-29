from __future__ import annotations

import customtkinter as ctk

from modules.campaigns.ui.arc_studio.constants import color_for_status
from modules.generic.editor.styles import EDITOR_PALETTE


class ArcCardList(ctk.CTkScrollableFrame):
    """Scrollable arc cards with selection callback."""

    def __init__(self, master, on_select):
        super().__init__(master, fg_color=EDITOR_PALETTE["surface_soft"])
        self._on_select = on_select
        self._cards: list[ctk.CTkFrame] = []

    def render(self, arcs: list[dict], selected_index: int | None, search_text: str = ""):
        for child in self.winfo_children():
            child.destroy()
        self._cards = []

        lowered_search = (search_text or "").strip().casefold()
        visible_count = 0
        for index, arc in enumerate(arcs):
            name = str(arc.get("name") or f"Arc {index + 1}").strip()
            summary = str(arc.get("objective") or arc.get("summary") or "").strip()
            thread = str(arc.get("thread") or "").strip()
            status = str(arc.get("status") or "Planned").strip()
            scenarios = [str(item).strip() for item in (arc.get("scenarios") or []) if str(item).strip()]

            searchable = " ".join([name, summary, thread, status, " ".join(scenarios)]).casefold()
            if lowered_search and lowered_search not in searchable:
                continue

            visible_count += 1
            is_selected = selected_index == index
            card = ctk.CTkFrame(
                self,
                fg_color=EDITOR_PALETTE["surface"] if is_selected else EDITOR_PALETTE["surface_soft"],
                border_width=1,
                border_color=EDITOR_PALETTE["accent"] if is_selected else EDITOR_PALETTE["border"],
                corner_radius=10,
            )
            card.pack(fill="x", padx=6, pady=5)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=10, pady=(8, 4))
            ctk.CTkLabel(top, text=f"{index + 1}. {name}", font=("Arial", 13, "bold"), anchor="w").pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(
                top,
                text=status or "Planned",
                text_color="#FFFFFF",
                fg_color=color_for_status(status),
                corner_radius=10,
                padx=8,
                pady=2,
            ).pack(side="right")

            ctk.CTkLabel(
                card,
                text=summary or "No objective yet.",
                text_color=EDITOR_PALETTE["text"],
                anchor="w",
                justify="left",
                wraplength=300,
            ).pack(fill="x", padx=10)

            meta = f"{len(scenarios)} scenarios"
            if thread:
                meta = f"{meta} • Thread: {thread[:42]}{'…' if len(thread) > 42 else ''}"
            ctk.CTkLabel(card, text=meta, text_color=EDITOR_PALETTE["muted_text"], anchor="w").pack(fill="x", padx=10, pady=(2, 8))

            self._bind_click(card, index)
            self._cards.append(card)

        if visible_count == 0:
            ctk.CTkLabel(self, text="No arcs match this filter.", text_color=EDITOR_PALETTE["muted_text"]).pack(anchor="w", padx=10, pady=10)

    def _bind_click(self, root: ctk.CTkBaseClass, index: int):
        root.bind("<Button-1>", lambda _e, i=index: self._on_select(i))
        for child in root.winfo_children():
            self._bind_click(child, index)
