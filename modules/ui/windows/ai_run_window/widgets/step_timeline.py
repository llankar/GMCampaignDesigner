"""Utilities for AI run window step timeline."""

from __future__ import annotations

import customtkinter as ctk


class StepTimeline(ctk.CTkTextbox):
    def __init__(self, master, **kwargs):
        """Initialize the StepTimeline instance."""
        super().__init__(master, **kwargs)
        self.configure(state="disabled")

    def render_items(self, items: list[dict]) -> None:
        """Render items."""
        lines = []
        for item in items:
            # Process each item from items.
            status = item.get("status", "pending")
            icon = "○"
            if status == "done":
                icon = "✓"
            elif status == "active":
                icon = "▶"
            elif status == "error":
                icon = "✗"
            phase = item.get("phase") or ""
            message = item.get("message") or ""
            lines.append(f"{icon} {phase} {message}".strip())

        self.configure(state="normal")
        self.delete("1.0", "end")
        self.insert("1.0", "\n".join(lines) if lines else "No AI activity yet.")
        self.configure(state="disabled")
