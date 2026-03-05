import tkinter as tk

import customtkinter as ctk


class MultiLinkSelector(ctk.CTkFrame):
    """Search + multi-select widget for event entity links."""

    def __init__(self, master, *, label, load_options):
        super().__init__(master)
        self._load_options = load_options

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text=label).grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.search_entry = ctk.CTkEntry(self, placeholder_text="Rechercher...")
        self.search_entry.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        self.search_entry.bind("<KeyRelease>", self._on_search)

        self.listbox = tk.Listbox(self, selectmode=tk.MULTIPLE, exportselection=False, height=5)
        self.listbox.grid(row=2, column=0, sticky="ew")

        self._all_options = []
        self.refresh_options()

    def refresh_options(self, query=""):
        self._all_options = list(self._load_options(query) or [])
        self.listbox.delete(0, tk.END)
        for option in self._all_options:
            self.listbox.insert(tk.END, option)

    def set_values(self, values):
        wanted = {str(value).strip() for value in (values or []) if str(value).strip()}
        self.listbox.selection_clear(0, tk.END)
        for index, option in enumerate(self._all_options):
            if option in wanted:
                self.listbox.selection_set(index)

    def get_values(self):
        indexes = self.listbox.curselection()
        return [self.listbox.get(index) for index in indexes]

    def _on_search(self, _event=None):
        selected_before = set(self.get_values())
        query = self.search_entry.get().strip()
        self.refresh_options(query=query)
        self.set_values(selected_before)
