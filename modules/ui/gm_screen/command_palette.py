import tkinter as tk
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Sequence

import customtkinter as ctk


@dataclass(frozen=True)
class CommandPaletteItem:
    label: str
    category: str
    action: Callable[[], None]
    keywords: Sequence[str] = field(default_factory=tuple)


class CommandPalette(ctk.CTkToplevel):
    def __init__(self, master, items: Iterable[CommandPaletteItem], title: str = "Command Palette"):
        super().__init__(master)
        self.title(title)
        self.geometry("460x360")
        self.transient(master)
        self.grab_set()

        self._items: List[CommandPaletteItem] = list(items)
        self._filtered_items: List[CommandPaletteItem] = []

        self._entry = ctk.CTkEntry(self, placeholder_text="Type to search…")
        self._entry.pack(fill="x", padx=12, pady=(12, 6))

        bg_color, text_color, sel_bg = self._resolve_listbox_colors()
        self._listbox = tk.Listbox(
            self,
            activestyle="none",
            bg=bg_color,
            fg=text_color,
            highlightbackground=bg_color,
            selectbackground=sel_bg,
            selectforeground=text_color,
        )
        self._listbox.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self._entry.bind("<KeyRelease>", self._on_search)
        self._entry.bind("<Down>", self._focus_listbox)
        self._entry.bind("<Up>", self._focus_listbox)
        self._entry.bind("<Return>", self._execute_selection)
        self._entry.bind("<Escape>", self._close)
        self._listbox.bind("<Return>", self._execute_selection)
        self._listbox.bind("<Double-Button-1>", self._execute_selection)
        self._listbox.bind("<Escape>", self._close)

        self._populate_list(initial=True)
        self.after(10, self._entry.focus_force)

    def _resolve_listbox_colors(self):
        raw_bg = self._entry.cget("fg_color")
        raw_txt = self._entry.cget("text_color")
        appearance = ctk.get_appearance_mode()
        idx = 1 if appearance == "Dark" else 0
        bg_list = raw_bg if isinstance(raw_bg, (list, tuple)) else raw_bg.split()
        txt_list = raw_txt if isinstance(raw_txt, (list, tuple)) else raw_txt.split()
        bg_color = bg_list[idx]
        text_color = txt_list[idx]
        sel_bg = "#3a3a3a" if appearance == "Dark" else "#d9d9d9"
        return bg_color, text_color, sel_bg

    def _populate_list(self, initial: bool = False):
        query = self._entry.get().strip().lower()
        self._listbox.delete(0, "end")
        self._filtered_items.clear()

        for item in self._items:
            if initial or self._matches(item, query):
                self._listbox.insert("end", f"{item.category}: {item.label}")
                self._filtered_items.append(item)

        if self._filtered_items:
            self._listbox.selection_clear(0, "end")
            self._listbox.selection_set(0)
            self._listbox.activate(0)

    def _matches(self, item: CommandPaletteItem, query: str) -> bool:
        if not query:
            return True
        haystack = " ".join([item.label, item.category, *item.keywords]).lower()
        return all(part in haystack for part in query.split())

    def _on_search(self, _event=None):
        self._populate_list(initial=False)

    def _focus_listbox(self, _event=None):
        if self._filtered_items:
            if not self._listbox.curselection():
                self._listbox.selection_set(0)
                self._listbox.activate(0)
            self._listbox.focus_set()
        return "break"

    def _execute_selection(self, _event=None):
        if not self._filtered_items:
            return "break"
        selection = self._listbox.curselection()
        index = selection[0] if selection else 0
        item = self._filtered_items[index]
        self.destroy()
        item.action()
        return "break"

    def _close(self, _event=None):
        self.destroy()
        return "break"
