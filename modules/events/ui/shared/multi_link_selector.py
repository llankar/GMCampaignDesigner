import tkinter as tk

import customtkinter as ctk

from modules.events.ui.full.event_editor.palette import get_event_editor_palette


class MultiLinkSelector(ctk.CTkFrame):
    """Search + multi-select widget for event entity links."""

    def __init__(self, master, *, label, load_options, helper_text=""):
        self._palette = get_event_editor_palette()
        super().__init__(
            master,
            fg_color=self._palette.panel_alt_bg,
            corner_radius=16,
            border_width=1,
            border_color=self._palette.border,
        )
        self._load_options = load_options

        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=14, pady=(12, 6), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text=label,
            text_color=self._palette.text_primary,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        self.selection_count = ctk.CTkLabel(
            header,
            text="0 selected",
            text_color=self._palette.text_secondary,
            fg_color=self._palette.muted_chip,
            corner_radius=999,
            padx=10,
            pady=4,
        )
        self.selection_count.grid(row=0, column=1, sticky="e")

        if helper_text:
            ctk.CTkLabel(
                self,
                text=helper_text,
                text_color=self._palette.text_secondary,
                justify="left",
                wraplength=320,
            ).grid(row=1, column=0, padx=14, pady=(0, 8), sticky="w")
            search_row = 2
        else:
            search_row = 1

        self.search_entry = ctk.CTkEntry(
            self,
            placeholder_text="Search...",
            fg_color=self._palette.input_bg,
            border_color=self._palette.input_border,
            text_color=self._palette.text_primary,
        )
        self.search_entry.grid(row=search_row, column=0, padx=14, pady=(0, 8), sticky="ew")
        self.search_entry.bind("<KeyRelease>", self._on_search)

        list_frame = ctk.CTkFrame(self, fg_color=self._palette.input_bg, corner_radius=14)
        list_frame.grid(row=search_row + 1, column=0, padx=14, pady=(0, 14), sticky="nsew")
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(search_row + 1, weight=1)

        self.listbox = tk.Listbox(
            list_frame,
            selectmode=tk.MULTIPLE,
            exportselection=False,
            height=6,
            **self._tk_listbox_theme(),
        )
        self.listbox.grid(row=0, column=0, sticky="nsew")
        self.listbox.bind("<<ListboxSelect>>", lambda _event: self._update_selection_count())

        self._all_options = []
        self.refresh_options()

    def _tk_listbox_theme(self):
        return {
            "bg": self._palette.input_bg,
            "fg": self._palette.text_primary,
            "selectbackground": self._palette.accent,
            "selectforeground": "#FFFFFF",
            "highlightbackground": self._palette.input_border,
            "highlightcolor": self._palette.input_border,
            "highlightthickness": 1,
            "relief": "flat",
            "bd": 0,
            "activestyle": "none",
        }

    def refresh_options(self, query=""):
        self._all_options = list(self._load_options(query) or [])
        self.listbox.delete(0, tk.END)
        for option in self._all_options:
            self.listbox.insert(tk.END, option)
        self._update_selection_count()

    def set_values(self, values):
        wanted = {str(value).strip() for value in (values or []) if str(value).strip()}
        self.listbox.selection_clear(0, tk.END)
        for index, option in enumerate(self._all_options):
            if option in wanted:
                self.listbox.selection_set(index)
        self._update_selection_count()

    def get_values(self):
        indexes = self.listbox.curselection()
        return [self.listbox.get(index) for index in indexes]

    def _update_selection_count(self):
        count = len(self.listbox.curselection())
        suffix = "item" if count == 1 else "items"
        self.selection_count.configure(text=f"{count} {suffix}")

    def _on_search(self, _event=None):
        selected_before = set(self.get_values())
        query = self.search_entry.get().strip()
        self.refresh_options(query=query)
        self.set_values(selected_before)
