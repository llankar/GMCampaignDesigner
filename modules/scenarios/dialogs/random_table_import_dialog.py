"""Dialog for importing random table rows from text."""

import customtkinter as ctk
from tkinter import messagebox

from modules.scenarios.importers.random_table_text_parser import (
    RandomTableImportError,
    parse_random_table_text,
)


class RandomTableImportDialog(ctk.CTkToplevel):
    """Collect raw text rows and convert them into random table entries."""

    def __init__(self, master=None):
        super().__init__(master)
        self.title("Import Random Table Entries")
        self.geometry("540x360")
        self.resizable(True, True)
        self.result_entries = None

        self._build_ui()
        self.grab_set()
        self.focus_force()

    def _build_ui(self):
        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        info_text = (
            "Paste lines in the format 'X-X Name Description'.\n"
            "Example: 1-2 Tavern The PCs all belong to the same tavern"
        )
        ctk.CTkLabel(container, text=info_text, justify="left").pack(anchor="w")

        self.text_box = ctk.CTkTextbox(container, height=200, wrap="word")
        self.text_box.pack(fill="both", expand=True, pady=(6, 10))

        actions = ctk.CTkFrame(container)
        actions.pack(fill="x")
        ctk.CTkButton(actions, text="Import", command=self._import).pack(side="right", padx=(6, 0))
        ctk.CTkButton(actions, text="Cancel", command=self.destroy).pack(side="right")

    def _import(self):
        raw_text = self.text_box.get("1.0", "end")
        try:
            self.result_entries = parse_random_table_text(raw_text)
        except RandomTableImportError as exc:
            messagebox.showerror("Random Table Import", str(exc))
            return
        self.destroy()


__all__ = ["RandomTableImportDialog"]
