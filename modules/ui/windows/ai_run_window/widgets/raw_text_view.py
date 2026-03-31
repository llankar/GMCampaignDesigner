"""View for AI run window raw text."""

from __future__ import annotations

import customtkinter as ctk


class RawTextView(ctk.CTkFrame):
    def __init__(self, master, *, empty_message: str = "No data yet") -> None:
        """Initialize the RawTextView instance."""
        super().__init__(master)
        self._empty_message = empty_message

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._copy_button = ctk.CTkButton(self, text="Copy", width=120, command=self._copy_text)
        self._copy_button.grid(row=0, column=0, sticky="e", padx=8, pady=(8, 4))

        self._textbox = ctk.CTkTextbox(self)
        self._textbox.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._render_read_only(self._empty_message)

    def set_copy_label(self, label: str) -> None:
        """Set copy label."""
        self._copy_button.configure(text=label)

    def render_text(self, text: str | None) -> None:
        """Render text."""
        payload = (text or "").strip()
        self._render_read_only(payload if payload else self._empty_message)

    def _copy_text(self) -> None:
        """Copy text."""
        content = self._textbox.get("1.0", "end").strip()
        if not content or content == self._empty_message:
            return
        self.clipboard_clear()
        self.clipboard_append(content)

    def _render_read_only(self, content: str) -> None:
        """Render read only."""
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.insert("1.0", content)
        self._textbox.configure(state="disabled")
