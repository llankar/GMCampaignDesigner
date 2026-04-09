"""Base panel widget contract for GM Screen 2."""

from __future__ import annotations

import customtkinter as ctk

from modules.scenarios.gm_screen2.domain.models import PanelPayload


class BasePanelView(ctk.CTkFrame):
    """Passive panel view with structured blocks."""

    PANEL_KEY = "base"

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._title_label = ctk.CTkLabel(self, text="", anchor="w")
        self._title_label.pack(fill="x", padx=8, pady=(8, 4))
        self._scroll = ctk.CTkScrollableFrame(self)
        self._scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def render_payload(self, payload: PanelPayload) -> None:
        """Render payload content without side effects."""
        self._title_label.configure(text=payload.title)
        for child in self._scroll.winfo_children():
            child.destroy()
        for section in payload.sections:
            self._render_section(section.heading, section.items)

    def _render_section(self, heading, items) -> None:
        section_frame = ctk.CTkFrame(self._scroll)
        section_frame.pack(fill="x", padx=2, pady=4)
        ctk.CTkLabel(section_frame, text=heading, anchor="w", font=ctk.CTkFont(weight="bold")).pack(fill="x", padx=8, pady=(8, 4))
        for item in items:
            if item.kind == "chip":
                ctk.CTkLabel(section_frame, text=f"• {item.title}").pack(anchor="w", padx=12, pady=2)
            elif item.kind == "card":
                card = ctk.CTkFrame(section_frame)
                card.pack(fill="x", padx=8, pady=4)
                ctk.CTkLabel(card, text=item.title, anchor="w", font=ctk.CTkFont(weight="bold")).pack(fill="x", padx=6, pady=(4, 0))
                ctk.CTkLabel(card, text=item.text, justify="left", anchor="w").pack(fill="x", padx=6, pady=(0, 4))
            else:
                text = item.text or item.title
                ctk.CTkLabel(section_frame, text=text, justify="left", anchor="w", wraplength=460).pack(fill="x", padx=12, pady=2)
